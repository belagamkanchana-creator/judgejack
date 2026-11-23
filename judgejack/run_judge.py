"""Run a judge over data/cases.jsonl and report the results.

    python -m judgejack.run_judge --model ollama:llama3.2:3b
    python -m judgejack.run_judge --model ollama:llama3.2:3b --prompt reason_first
    python -m judgejack.run_judge --model dummy:approve --limit 20

Each decision is appended to results/<run>.jsonl as soon as it is made, so an interrupted run
resumes where it stopped. When all cases are done, results/<run>_summary.md is written.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from judgejack.backends import make_backend
from judgejack.cases import Case, read_cases
from judgejack.judges import JUDGE_PROMPTS, MAX_OUTPUT_CHARS, parse_verdict, render_case
from judgejack.metrics import accuracy, attack_success_rate, by_group, false_block_rate, unparseable_rate


def run_name(model: str, prompt: str) -> str:
    return f"{model.replace(':', '_').replace('/', '_')}__{prompt}"


def load_done(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["case_id"]: r for r in (json.loads(line) for line in f if line.strip())}


def judge_case(backend, system: str, case: Case) -> dict:
    start = time.time()
    raw = backend(system, render_case(case))
    out = parse_verdict(raw)
    return {
        "case_id": case.id, "suite": case.suite, "attack": case.attack, "kind": case.kind,
        "user_task_id": case.user_task_id, "injection_task_id": case.injection_task_id,
        "gold": case.gold, "verdict": out.verdict, "reason": out.reason, "raw": raw,
        "seconds": round(time.time() - start, 2),
    }


def flips(results: list[dict], kind: str) -> tuple[int, int, int]:
    """Paired clean -> L0 comparison on the same (user task, injection task) pair.
    Returns (pairs compared, flipped toward APPROVE, flipped toward BLOCK)."""
    key = lambda r: (r["suite"], r["user_task_id"], r["injection_task_id"])
    clean = {key(r): r["verdict"] for r in results if r["attack"] == "clean" and r["kind"] == kind}
    l0 = {key(r): r["verdict"] for r in results if r["attack"] == "L0" and r["kind"] == kind}
    both = clean.keys() & l0.keys()
    to_approve = sum(clean[k] != "APPROVE" and l0[k] == "APPROVE" for k in both)
    to_block = sum(clean[k] != "BLOCK" and l0[k] == "BLOCK" for k in both)
    return len(both), to_approve, to_block


def pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}"


def summary_markdown(results: list[dict], model: str, prompt: str) -> str:
    lines = [
        f"# JudgeJack results: `{model}`, prompt `{prompt}`", "",
        f"{len(results)} judge decisions. Temperature 0, seed 0, tool outputs cut at {MAX_OUTPUT_CHARS} characters. "
        "Unparseable replies count as neither APPROVE nor BLOCK (they lower accuracy and are reported separately).", "",
        "## By attack", "",
        "| Attack | Harmful | Benign | Fooled (ASR %) | Over-block (%) | Accuracy (%) | Unparseable (%) |",
        "|---|---|---|---|---|---|---|",
    ]
    for attack, rs in by_group(results, "attack").items():
        nh = sum(r["kind"] == "harmful" for r in rs)
        lines.append(f"| {attack} | {nh} | {len(rs) - nh} | {pct(attack_success_rate(rs))} | {pct(false_block_rate(rs))} "
                     f"| {pct(accuracy(rs))} | {pct(unparseable_rate(rs))} |")
    lines += ["", "## By suite and attack (ASR % / over-block %)", "", "| Suite | clean | L0 |", "|---|---|---|"]
    for suite, rs in by_group(results, "suite").items():
        cells = []
        for attack in ("clean", "L0"):
            sub = [r for r in rs if r["attack"] == attack]
            cells.append(f"{pct(attack_success_rate(sub))} / {pct(false_block_rate(sub))}" if sub else "n/a")
        lines.append(f"| {suite} | " + " | ".join(cells) + " |")
    n, up, down = flips(results, "harmful")
    nb, bup, bdown = flips(results, "benign")
    lines += [
        "", "## Paired clean -> L0 changes (same user task and injection task)", "",
        f"- Harmful actions: {n} pairs; {up} went from not-approved to APPROVE once the injection was present, {down} went the other way.",
        f"- Benign actions: {nb} pairs; {bdown} went from not-blocked to BLOCK once the injection was present, {bup} went the other way.",
    ]
    secs = [r["seconds"] for r in results]
    lines += ["", f"Mean judge latency: {sum(secs) / len(secs):.1f} s per decision.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="ollama:<model>, dummy:approve or dummy:block")
    p.add_argument("--prompt", default="default", choices=sorted(JUDGE_PROMPTS))
    p.add_argument("--cases", default="data/cases.jsonl")
    p.add_argument("--out-dir", default="results")
    p.add_argument("--limit", type=int, default=None, help="only the first N cases (quick check)")
    args = p.parse_args(argv)

    cases = read_cases(Path(args.cases))[: args.limit]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = run_name(args.model, args.prompt) + (f"__first{args.limit}" if args.limit else "")
    path = out_dir / f"{name}.jsonl"
    done = load_done(path)
    todo = [c for c in cases if c.id not in done]
    print(f"{len(cases)} cases, {len(done)} already done, {len(todo)} to run -> {path}")

    backend = make_backend(args.model)
    system = JUDGE_PROMPTS[args.prompt]
    with path.open("a") as f:
        for i, case in enumerate(todo, 1):
            r = judge_case(backend, system, case)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            done[case.id] = r
            if i % 10 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  last: {case.attack:5s} {case.kind:7s} -> {r['verdict']}  ({r['seconds']}s)", flush=True)

    results = [done[c.id] for c in cases]
    summary = summary_markdown(results, args.model, args.prompt)
    (out_dir / f"{name}_summary.md").write_text(summary)
    print("\n" + summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
