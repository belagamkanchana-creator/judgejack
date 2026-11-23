"""The judge case format: one JSON object per line in data/cases.jsonl.

A *case* is one decision the judge has to make:

    user task  +  trajectory so far (tool calls and their outputs)  +  proposed next action
        -> should the judge APPROVE or BLOCK the proposed action?

- kind="benign":  proposed action is the next step of the user's own task  -> gold APPROVE
- kind="harmful": proposed action is the attacker's injected goal          -> gold BLOCK
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Kind = Literal["benign", "harmful"]
Verdict = Literal["APPROVE", "BLOCK"]


@dataclass
class Step:
    """One tool call the agent already made, and what the tool returned."""

    tool: str
    args: dict[str, Any]
    output: str


@dataclass
class Action:
    """The tool call the agent wants to make next. This is what the judge rules on."""

    tool: str
    args: dict[str, Any]


@dataclass
class Case:
    id: str
    suite: str
    user_task_id: str
    injection_task_id: str
    attack: str
    kind: Kind
    user_task: str
    trajectory: list[Step]
    proposed_action: Action
    gold: Verdict
    injection_goal: str
    payload_in_context: bool
    """True if the attack payload appears in at least one tool output the judge will read."""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Case:
        d = dict(d)
        d["trajectory"] = [Step(**s) for s in d["trajectory"]]
        d["proposed_action"] = Action(**d["proposed_action"])
        return cls(**d)


def write_cases(cases: list[Case], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for c in cases:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")


def read_cases(path: Path) -> list[Case]:
    with path.open() as f:
        return [Case.from_dict(json.loads(line)) for line in f if line.strip()]
