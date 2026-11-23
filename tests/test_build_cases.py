"""Tests for the case builder and renderer (already implemented; these should pass)."""

import json

import pytest

from judgejack.build_cases import build
from judgejack.cases import Case, read_cases, write_cases
from judgejack.judges import render_case


@pytest.fixture(scope="module")
def built():
    cases, manifest = build(["clean", "L0"], ["banking"], max_pairs=6, seed=0)
    return cases, manifest


def test_gold_labels_follow_kind(built):
    cases, _ = built
    assert cases
    for c in cases:
        assert c.gold == ("APPROVE" if c.kind == "benign" else "BLOCK")


def test_same_pairs_for_every_attack(built):
    cases, _ = built
    pairs = lambda a: {(c.user_task_id, c.injection_task_id, c.kind) for c in cases if c.attack == a}
    assert pairs("clean") == pairs("L0")


def test_l0_payload_is_in_harmful_context_and_clean_has_none(built):
    cases, _ = built
    for c in cases:
        text = "\n".join(s.output for s in c.trajectory)
        if c.attack == "L0" and c.kind == "harmful":
            assert c.payload_in_context
            assert "<INFORMATION>" in text
        if c.attack == "clean":
            assert not c.payload_in_context
            assert "<INFORMATION>" not in text


def test_harmful_action_differs_from_benign_action(built):
    cases, _ = built
    by_pair = {}
    for c in cases:
        by_pair.setdefault((c.user_task_id, c.injection_task_id, c.attack), {})[c.kind] = c
    compared = 0
    for pair in by_pair.values():
        if "benign" in pair and "harmful" in pair:
            compared += 1
            assert pair["benign"].proposed_action != pair["harmful"].proposed_action
    assert compared > 0


def test_build_is_deterministic():
    a, _ = build(["clean"], ["banking"], max_pairs=4, seed=1)
    b, _ = build(["clean"], ["banking"], max_pairs=4, seed=1)
    assert [c.to_dict() for c in a] == [c.to_dict() for c in b]


def test_cases_round_trip_through_jsonl(built, tmp_path):
    cases, _ = built
    path = tmp_path / "cases.jsonl"
    write_cases(cases, path)
    assert [c.to_dict() for c in read_cases(path)] == [c.to_dict() for c in cases]
    json.loads(path.read_text().splitlines()[0])  # each line is valid JSON


def test_render_case_shows_everything_and_truncates(built):
    case: Case = next(c for c in built[0] if c.kind == "harmful" and c.attack == "L0")
    text = render_case(case)
    assert case.user_task in text
    assert case.proposed_action.tool in text
    assert text.count("<tool_output") == len(case.trajectory)

    short = render_case(case, max_output_chars=20)
    assert "[truncated" in short
