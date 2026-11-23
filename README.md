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
| Judge prompt | ⬜ todo |
| Metrics | ✅ done, tested |
| Judge backends (Hugging Face, API) + Slurm script | ⬜ todo |
| L3 adaptive attack, L4 GCG + transfer | ⬜ later |

## Hypotheses

> **Draft hypotheses.** They will be finalized and committed before any judge is run, so the commit history shows they came before the results.

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

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Rebuild the cases (about 10 seconds, no API key needed):

```bash
.venv/bin/python -m judgejack.build_cases --max-pairs-per-suite 25 --seed 0
```

Run the tests:

```bash
.venv/bin/python -m pytest -q
```

## Roadmap

1. **Hypotheses:** finalize H1 to H4 and commit them before any judge runs.
2. **Judge prompt:** write `JUDGE_SYSTEM_PROMPT` (plus a reason-first version for H2) in `judgejack/judges.py`, then freeze it once attacks start.
3. **Attacks:** add `L1`, `L2` and the code-switched variant in `judgejack/attacks.py`, register them in `ATTACKS`, and rebuild the cases.
4. **Judge backends:** a Hugging Face model (Kaggle GPU or cluster) and one API model.
5. **Later:** L3 adaptive attack, L4 GCG with transfer.

Related: [EvalGuard-Bench](https://github.com/belagamkanchana-creator/evalguard-bench), a smaller controlled benchmark of judge-targeted attacks and defenses with results on Llama 3.2 3B.

## Known limitations so far

- Trajectories are AgentDojo ground-truth replays, not real agent runs: the "hijacked" trajectories are what a successfully hijacked agent would do, not what a given model actually did.
- Some tool outputs are up to ~58K characters; the judge sees each output cut to 4,000 characters (`MAX_OUTPUT_CHARS` in `judges.py`). Checked for L0: 0 of 171 payloads are cut off. Re-check for each new attack.
- Some proposed actions are read-only (e.g. `get_webpage`), so a harmful case is not always a destructive action.
- Everything runs in AgentDojo's simulated environments; no real services are contacted.

## Credits

AgentDojo: Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr. *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.* NeurIPS 2024 Datasets and Benchmarks. The `L0` payload is AgentDojo's `important_instructions` attack.
