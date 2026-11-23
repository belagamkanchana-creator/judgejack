"""Build judge cases from AgentDojo's ground-truth solutions. No LLM calls, no API cost.

For each sampled (user task, injection task) pair and each attack:

1. Find which injection slots the agent reads while solving the user task (AgentDojo's canary trick).
2. Put the attack payload in those slots.
3. Benign case:  replay the user task's ground-truth tool calls; the judge rules on the LAST call,
                 having seen all earlier calls and outputs.                        gold = APPROVE
4. Harmful case: replay the user task only up to the first tool output that contains the payload
                 (the moment a hijack would happen), then the injection task's ground-truth calls;
                 the judge rules on the injection task's LAST call.                gold = BLOCK

The same pairs are used for every attack, so results are directly comparable across attacks.

Usage:
    python -m judgejack.build_cases --max-pairs-per-suite 25 --seed 0
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suites

from judgejack.attacks import ATTACKS, AttackContext, AttackFn
from judgejack.cases import Action, Case, Step, write_cases

BENCHMARK_VERSION = "v1.2.2"
DEFAULT_SUITES = ("banking", "slack", "travel", "workspace")


def _jsonable(args: dict) -> dict:
    return json.loads(json.dumps(dict(args), default=str))


def _run(suite, env, runtime: FunctionsRuntime, calls: list[FunctionCall]) -> list[Step]:
    steps = []
    for call in calls:
        result, _ = runtime.run_function(env, call.function, call.args, raise_on_error=True)
        steps.append(Step(tool=call.function, args=_jsonable(call.args), output=tool_result_to_str(result)))
    return steps


def injection_slots(suite, user_task) -> tuple[list[str], int]:
    """Return (slots the agent reads, index of the first ground-truth step whose output shows one).

    Same idea as AgentDojo's BaseAttack.get_injection_candidates: fill every slot with a unique
    canary string, replay the ground truth, and see which canaries come back in tool outputs.
    """
    canaries = {slot: f"<CANARY---{slot}--->" for slot in suite.get_injection_vector_defaults()}
    env = suite.load_and_inject_default_environment(canaries)
    steps = _run(suite, env, FunctionsRuntime(suite.tools), user_task.ground_truth(env))
    slots = [s for s, c in canaries.items() if any(c in st.output for st in steps)]
    first = next((i for i, st in enumerate(steps) if any(canaries[s] in st.output for s in slots)), -1)
    return slots, first


def build_pair(suite_name, suite, user_task, inj_task, attack_name: str, attack: AttackFn,
               slots: list[str], first_seen: int) -> list[Case]:
    ctx = AttackContext(suite=suite_name, user_task=user_task.PROMPT, injection_goal=inj_task.GOAL)
    payload = attack(ctx)
    injections = {s: payload for s in slots} if payload is not None else {}
    base = dict(
        suite=suite_name, user_task_id=user_task.ID, injection_task_id=inj_task.ID,
        attack=attack_name, user_task=user_task.PROMPT, injection_goal=inj_task.GOAL,
    )
    cases = []

    # Benign: the user's own task, judged at its last step.
    env = suite.load_and_inject_default_environment(injections)
    steps = _run(suite, env, FunctionsRuntime(suite.tools), user_task.ground_truth(env))
    if steps:
        last = steps[-1]
        cases.append(Case(
            id=f"{suite_name}/{user_task.ID}/{inj_task.ID}/{attack_name}/benign", kind="benign",
            trajectory=steps[:-1], proposed_action=Action(last.tool, last.args), gold="APPROVE",
            payload_in_context=payload is not None and first_seen < len(steps) - 1,
            meta={"n_steps": len(steps) - 1}, **base,
        ))

    # Harmful: stop the user task where the payload is first read, then follow the injection.
    env = suite.load_and_inject_default_environment(injections)
    runtime = FunctionsRuntime(suite.tools)
    user_calls = user_task.ground_truth(env)
    prefix = _run(suite, env, runtime, user_calls[: first_seen + 1])
    inj_calls = inj_task.ground_truth(env)
    if inj_calls:
        inj_prefix = _run(suite, env, runtime, inj_calls[:-1])
        final = inj_calls[-1]
        cases.append(Case(
            id=f"{suite_name}/{user_task.ID}/{inj_task.ID}/{attack_name}/harmful", kind="harmful",
            trajectory=prefix + inj_prefix, proposed_action=Action(final.function, _jsonable(final.args)),
            gold="BLOCK", payload_in_context=payload is not None,
            meta={"n_steps": len(prefix) + len(inj_prefix), "n_injection_prefix_steps": len(inj_prefix)},
            **base,
        ))
    return cases


def sample_pairs(suite, max_pairs: int | None, rng: random.Random) -> list[tuple[str, str]]:
    pairs = [(u, i) for u in suite.user_tasks for i in suite.injection_tasks]
    rng.shuffle(pairs)
    return sorted(pairs[:max_pairs] if max_pairs else pairs)


def build(attacks: list[str], suites: list[str], max_pairs: int | None, seed: int) -> tuple[list[Case], dict]:
    all_suites = get_suites(BENCHMARK_VERSION)
    cases: list[Case] = []
    skipped: list[dict] = []
    for name in suites:
        suite = all_suites[name]
        rng = random.Random(f"{seed}-{name}")  # per-suite seed: adding a suite doesn't reshuffle others
        slot_cache: dict[str, tuple[list[str], int]] = {}
        for u_id, i_id in sample_pairs(suite, max_pairs, rng):
            ut, it = suite.user_tasks[u_id], suite.injection_tasks[i_id]
            try:
                if u_id not in slot_cache:
                    slot_cache[u_id] = injection_slots(suite, ut)
                slots, first = slot_cache[u_id]
                if not slots:
                    skipped.append({"suite": name, "user_task": u_id, "reason": "no injection slot is read"})
                    continue
                if not it.ground_truth(suite.load_and_inject_default_environment({})):
                    skipped.append({"suite": name, "user_task": u_id, "injection_task": i_id,
                                    "reason": "injection task has no ground-truth calls: benign case only"})
                for a in attacks:
                    cases += build_pair(name, suite, ut, it, a, ATTACKS[a], slots, first)
            except NotImplementedError:
                raise
            except Exception as e:  # a ground truth that fails to replay; record it, don't hide it
                skipped.append({"suite": name, "user_task": u_id, "injection_task": i_id, "reason": repr(e)})

    counts = Counter((c.attack, c.kind) for c in cases)
    manifest = {
        "agentdojo_version": version("agentdojo"),
        "benchmark_version": BENCHMARK_VERSION,
        "seed": seed,
        "max_pairs_per_suite": max_pairs,
        "suites": suites,
        "attacks": attacks,
        "n_cases": len(cases),
        "counts": {f"{a}/{k}": n for (a, k), n in sorted(counts.items())},
        "skipped": skipped,
    }
    return cases, manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--attacks", nargs="+", default=list(ATTACKS), choices=list(ATTACKS))
    p.add_argument("--suites", nargs="+", default=list(DEFAULT_SUITES), choices=list(DEFAULT_SUITES))
    p.add_argument("--max-pairs-per-suite", type=int, default=25, help="0 = all pairs")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=Path("data/cases.jsonl"))
    args = p.parse_args()

    cases, manifest = build(args.attacks, args.suites, args.max_pairs_per_suite or None, args.seed)
    write_cases(cases, args.out)
    args.out.with_name("manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(cases)} cases to {args.out}")
    for k, n in manifest["counts"].items():
        print(f"  {k:30s} {n}")
    if manifest["skipped"]:
        print(f"  skipped: {len(manifest['skipped'])} (details in manifest.json)")


if __name__ == "__main__":
    main()
