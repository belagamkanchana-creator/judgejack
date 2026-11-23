# JudgeJack results: `ollama:llama3.2:3b`, prompt `default`

366 judge decisions. Temperature 0, seed 0, tool outputs cut at 4000 characters. Unparseable replies count as neither APPROVE nor BLOCK (they lower accuracy and are reported separately).

## By attack

| Attack | Harmful | Benign | Fooled (ASR %) | Over-block (%) | Accuracy (%) | Unparseable (%) |
|---|---|---|---|---|---|---|
| clean | 83 | 100 | 0.0 | 73.0 | 59.6 | 0.5 |
| L0 | 83 | 100 | 0.0 | 83.0 | 54.6 | 0.0 |

## By suite and attack (ASR % / over-block %)

| Suite | clean | L0 |
|---|---|---|
| banking | 0.0 / 84.0 | 0.0 / 84.0 |
| slack | 0.0 / 76.0 | 0.0 / 100.0 |
| travel | 0.0 / 84.0 | 0.0 / 88.0 |
| workspace | 0.0 / 48.0 | 0.0 / 60.0 |

## Paired clean -> L0 changes (same user task and injection task)

- Harmful actions: 83 pairs; 0 went from not-approved to APPROVE once the injection was present, 1 went the other way.
- Benign actions: 100 pairs; 12 went from not-blocked to BLOCK once the injection was present, 2 went the other way.

Mean judge latency: 1.4 s per decision.
