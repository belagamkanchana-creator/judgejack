"""Sanity check: run every case through two dummy judges and print the results table.

The dummy judges ignore the case and always give the same reply, like a guard who lets
everyone in or stops everyone. Their numbers are known in advance, so if the table shows
them, every part of the pipeline is connected correctly:

    case -> formatted for the judge -> judge reply (raw text) -> parsed verdict -> metrics -> table

Expected: always-APPROVE is 100% fooled with 0% over-block; always-BLOCK is the opposite.

Usage:
    python -m judgejack.demo_dummy_judges
"""

from __future__ import annotations

from pathlib import Path

from judgejack.cases import read_cases
from judgejack.judges import parse_verdict, render_case
from judgejack.metrics import accuracy, attack_success_rate, by_group, false_block_rate, unparseable_rate

# Replies are written the messy way real models answer, so the parser gets exercised too.
DUMMY_JUDGES = {
    "always-APPROVE": lambda prompt: 'Looks fine. {"verdict": "approve", "reason": "dummy"}',
    "always-BLOCK": lambda prompt: '```json\n{"verdict": "BLOCK", "reason": "dummy"}\n```',
}


def main() -> None:
    cases = read_cases(Path("data/cases.jsonl"))
    print(f"Loaded {len(cases)} cases\n")

    for name, judge in DUMMY_JUDGES.items():
        results = []
        for case in cases:
            out = parse_verdict(judge(render_case(case)))
            results.append({"case_id": case.id, "attack": case.attack, "kind": case.kind, "verdict": out.verdict})

        print(f"Judge: {name}")
        print(f"  {'attack':8s} {'fooled (ASR)':>13s} {'over-block':>11s} {'accuracy':>9s} {'unreadable':>11s}")
        for attack, rs in by_group(results, "attack").items():
            print(
                f"  {attack:8s} {attack_success_rate(rs):13.0%} {false_block_rate(rs):11.0%}"
                f" {accuracy(rs):9.0%} {unparseable_rate(rs):11.0%}"
            )
        print()


if __name__ == "__main__":
    main()
