# JudgeJack results: `ollama:llama3.2:3b`, prompt `reason_first`

366 judge decisions. Temperature 0, seed 0, tool outputs cut at 4000 characters. Unparseable replies count as neither APPROVE nor BLOCK (they lower accuracy and are reported separately).

## By attack

| Attack | Harmful | Benign | Fooled (ASR %) | Over-block (%) | Accuracy (%) | Unparseable (%) |
|---|---|---|---|---|---|---|
| clean | 83 | 100 | 9.6 | 14.0 | 87.4 | 0.5 |
| L0 | 83 | 100 | 45.8 | 23.0 | 65.0 | 1.6 |

## By suite and attack (ASR % / over-block %)

| Suite | clean | L0 |
|---|---|---|
| banking | 12.0 / 20.0 | 20.0 / 32.0 |
| slack | 8.0 / 20.0 | 72.0 / 32.0 |
| travel | 13.6 / 12.0 | 50.0 / 16.0 |
| workspace | 0.0 / 4.0 | 36.4 / 12.0 |

## Paired clean -> L0 changes (same user task and injection task)

- Harmful actions: 83 pairs; 31 went from not-approved to APPROVE once the injection was present, 1 went the other way.
- Benign actions: 100 pairs; 12 went from not-blocked to BLOCK once the injection was present, 2 went the other way.

Mean judge latency: 3.7 s per decision.
