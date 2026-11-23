"""Spec for parse_verdict(). YOURS: these fail until you implement it in judgejack/judges.py.

Feel free to add cases you see from real models; that's exactly how a parser should grow.
"""

import pytest

from judgejack.judges import parse_verdict


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"verdict": "APPROVE", "reason": "matches the request"}', "APPROVE"),
        ('{"verdict": "BLOCK", "reason": "sends money to an unknown IBAN"}', "BLOCK"),
        ('```json\n{"verdict": "BLOCK", "reason": "x"}\n```', "BLOCK"),
        ('Let me think. The user asked to pay a bill.\n{"verdict": "APPROVE", "reason": "x"}', "APPROVE"),
        ('{"verdict": "block", "reason": "lowercase"}', "BLOCK"),
    ],
)
def test_parses_valid_verdicts(raw, expected):
    out = parse_verdict(raw)
    assert out.verdict == expected
    assert out.raw == raw


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "I am not sure.",
        '{"verdict": "MAYBE", "reason": "x"}',
        '{"reason": "no verdict field"}',
    ],
)
def test_unparseable_returns_none(raw):
    assert parse_verdict(raw).verdict is None


def test_keeps_reason():
    assert parse_verdict('{"verdict": "BLOCK", "reason": "unknown recipient"}').reason == "unknown recipient"
