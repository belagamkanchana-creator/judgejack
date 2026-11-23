# JudgeJack

**How much does an attacker need to know to fool an LLM judge?**

AI agents increasingly use an LLM "judge" to approve or block each action before it runs. The judge reads the agent's trajectory, including tool outputs an attacker can control (emails, files, web pages). JudgeJack measures how judge security degrades as the attacker learns more about the judge, from not knowing it exists (L0) up to having its weights (L4).

Built on [AgentDojo](https://github.com/ethz-spylab/agentdojo) (Debenedetti et al., 2024). JudgeJack adds the judge layer and the attacks aimed at it.

## Status

| Part | Status |
|---|---|
| Case builder from AgentDojo ground truth (no LLM calls) | ✅ done, tested |
| Attacks: `clean`, `L0` (AgentDojo's published attack) | ✅ done |
| Attacks: `L1`, `L2`, code-switched | ⬜ todo |
| Verdict parser | ✅ done, tested |
| Judge prompts (verdict-first and reason-first) | ✅ done, frozen |
| Metrics | ✅ done, tested |
| Ollama backend + resumable run script | ✅ done, tested |
| **First results: Llama 3.2 3B, clean vs L0** | ✅ [below](#first-results-llama-32-3b-via-ollama) |
| Judge backends (Hugging Face, API) + Slurm script | ⬜ todo |
| L3 adaptive attack, L4 GCG + transfer | ⬜ later |

## Hypotheses

> These hypotheses were committed (commit `667817b`) before any judge was run, so the history shows they came before the results.

- **H1:** Attack success rises with attacker knowledge: L0 < L1 < L2 < L3.
- **H2:** Judges that reason before deciding are not uniformly safer; some reason their way into the injected justification (their reason quotes the payload).
- **H3:** Code-switched payloads (Hindi/Telugu-English) raise attack success on smaller judges compared to the same payload in English.
- **H4:** Payloads that best hijack the agent are the ones the judge most easily catches, so end-to-end success is lower than either attack alone.

## How a case is built

Each case is one judge decision: *user request + trajectory so far + proposed next action → APPROVE or BLOCK?*

For each sampled (user task, injection task) pair from AgentDojo, and each attack:

1. Find which injection slots the agent reads while solving the user task (AgentDojo's canary method).
2. Put the attack payload in those slots.
3. **Benign case** (gold APPROVE): replay the user task's ground-truth tool calls; the judge rules on the last one.
4. **Harmful case** (gold BLOCK): replay the user task up to the first tool output containing the payload (the moment a hijack would happen), then the injection task's ground-truth calls; the judge rules on the final injected call.

Every attack uses the **same pairs**, so attacks are directly comparable. Benign cases under attack measure whether a payload makes the judge over-block legitimate actions.

### Current dataset (`data/cases.jsonl`, seed 0, 25 pairs per suite)

| Attack | Benign | Harmful |
|---|---|---|
| clean | 100 | 83 |
| L0 | 100 | 83 |

17 pairs have no harmful case: 7 AgentDojo injection tasks have no replayable ground truth (e.g. "email all unread emails"). They are listed in `data/manifest.json`.

## First results: Llama 3.2 3B via Ollama

Llama 3.2 3B as the judge, run locally with Ollama on an Apple M5 laptop: 366 cases × 2 prompts = 732 decisions, temperature 0, seed 0. Full outputs, including every raw reply, are in [`results/`](results/).

| Judge prompt | Attack | Fooled: harmful approved (%) | Over-block: benign blocked (%) | Accuracy (%) | Unparseable (%) |
|---|---|---|---|---|---|
| verdict-first | clean | 0.0 | 73.0 | 59.6 | 0.5 |
| verdict-first | L0 | 0.0 | 83.0 | 54.6 | 0.0 |
| reason-first | clean | 9.6 | 14.0 | 87.4 | 0.5 |
| reason-first | L0 | **45.8** | 23.0 | 65.0 | 1.6 |

83 harmful and 100 benign cases per row. For reference, a "judge" that approves everything scores 54.6% accuracy.

**Observations**

1. **The verdict-first judge is "safe" only because it blocks almost everything.** It approved no harmful action, but it also blocked 73% of the user's own legitimate actions, including read-only lookups (17 of 32), so its accuracy is barely above approving everything.
2. **Reasoning first makes the judge useful, and much easier to fool (supports H2).** On clean cases the reason-first judge reaches 87% accuracy. With AgentDojo's injection present, its attack success jumps from 9.6% to 45.8%: on the same (user task, injection task) pairs, 31 of 83 harmful actions flipped from not approved to approved, and only 1 flipped the other way.
3. **The injection also raises over-blocking.** For both prompts, 12 of 100 benign actions flipped to BLOCK once the injection was in the trajectory: the attack degrades the user's legitimate work even when it does not hijack the judge.
4. **Suites differ.** Under L0 with the reason-first prompt, attack success ranges from 20% (banking) to 72% (Slack).

**Caveats.** One small model, one seed, and only the L0 attack so far. Cases are AgentDojo ground-truth replays, not live agent runs. A few "harmful" labels may be ambiguous: in some banking tasks the user's own request mentions the same kind of action (e.g. updating a password), and the judge's approval there is arguably reasonable. The reason-first prompt was run with a 1,024-token reply cap after one reply looped without stopping; the verdict-first replies were all under 350 characters, so the cap does not affect them.

### The frozen judge prompt

The full text of both prompts is `JUDGE_PROMPTS` in [`judgejack/judges.py`](judgejack/judges.py). In short: the judge is told it is a security monitor; that the user request is the only source of intent; that instructions inside tool outputs come from third parties and carry no authority; and when to BLOCK or APPROVE. It must reply with a JSON verdict, either verdict-first or reasoning-first.

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Rebuild the cases (about 10 seconds, no API key needed):

```bash
.venv/bin/python -m judgejack.build_cases --max-pairs-per-suite 25 --seed 0
```

Run a judge (needs [Ollama](https://ollama.com) and `ollama pull llama3.2:3b`; about 10 minutes per prompt on a laptop, and an interrupted run resumes where it stopped):

```bash
.venv/bin/python -m judgejack.run_judge --model ollama:llama3.2:3b --prompt default
.venv/bin/python -m judgejack.run_judge --model ollama:llama3.2:3b --prompt reason_first
```

Check the pipeline without a model: `--model dummy:approve` or `--model dummy:block`.

Run the tests:

```bash
.venv/bin/python -m pytest -q
```

## Roadmap

1. **Attacks:** add `L1`, `L2` and the code-switched variant in `judgejack/attacks.py`, register them in `ATTACKS`, and rebuild the cases (needed for H1 and H3).
2. **More judges:** a larger open model (e.g. Llama 3.1 8B) and one API model, to see whether the H2 effect holds beyond 3B.
3. **Judge backends:** Hugging Face (Kaggle GPU or cluster) and an API backend.
4. **Repeat runs** with several seeds, with confidence intervals.
5. **Later:** L3 adaptive attack, L4 GCG with transfer.

Related: [EvalGuard-Bench](https://github.com/belagamkanchana-creator/evalguard-bench), a smaller controlled benchmark of judge-targeted attacks and defenses with results on Llama 3.2 3B.

## Known limitations so far

- Trajectories are AgentDojo ground-truth replays, not real agent runs: the "hijacked" trajectories are what a successfully hijacked agent would do, not what a given model actually did.
- Some tool outputs are up to ~58K characters; the judge sees each output cut to 4,000 characters (`MAX_OUTPUT_CHARS` in `judges.py`). Checked for L0: 0 of 171 payloads are cut off. Re-check for each new attack.
- Some proposed actions are read-only (e.g. `get_webpage`), so a harmful case is not always a destructive action.
- Everything runs in AgentDojo's simulated environments; no real services are contacted.

## Credits

AgentDojo: Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr. *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.* NeurIPS 2024 Datasets and Benchmarks. The `L0` payload is AgentDojo's `important_instructions` attack.
