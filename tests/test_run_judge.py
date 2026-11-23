import json

from judgejack import backends
from judgejack.judges import JUDGE_PROMPTS, JUDGE_SYSTEM_PROMPT, parse_verdict
from judgejack.run_judge import flips, main


def test_prompts_name_the_tags_and_the_output_format():
    assert JUDGE_SYSTEM_PROMPT == JUDGE_PROMPTS["default"]
    for prompt in JUDGE_PROMPTS.values():
        for tag in ("<user_request>", "<trajectory>", "<proposed_action>"):
            assert tag in prompt
        assert '"verdict"' in prompt and "APPROVE" in prompt and "BLOCK" in prompt
    reason_first = JUDGE_PROMPTS["reason_first"]
    assert reason_first.index('"reason"') < reason_first.index('"verdict"', reason_first.index("{"))


def test_ollama_request_is_deterministic_and_has_room_for_long_cases():
    body = backends.ollama_request("llama3.2:3b", "sys", "user")
    assert body["options"]["temperature"] == 0 and body["options"]["num_ctx"] >= 8192
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["stream"] is False


def test_dummy_backend_replies_parse():
    assert parse_verdict(backends.make_backend("dummy:block")("s", "u")).verdict == "BLOCK"


def test_flips_pairs_clean_with_l0():
    def r(attack, verdict, ut="u1"):
        return {"suite": "s", "user_task_id": ut, "injection_task_id": "i", "attack": attack,
                "kind": "harmful", "verdict": verdict}
    results = [r("clean", "BLOCK"), r("L0", "APPROVE"), r("clean", None, "u2"), r("L0", "BLOCK", "u2")]
    assert flips(results, "harmful") == (2, 1, 1)


def test_run_resumes_and_writes_summary(tmp_path):
    out = tmp_path / "res"
    assert main(["--model", "dummy:approve", "--limit", "6", "--out-dir", str(out)]) == 0
    jsonl = next(out.glob("*.jsonl"))
    assert len(jsonl.read_text().splitlines()) == 6
    assert main(["--model", "dummy:approve", "--limit", "6", "--out-dir", str(out)]) == 0  # nothing re-run
    assert len(jsonl.read_text().splitlines()) == 6
    assert all(json.loads(line)["verdict"] == "APPROVE" for line in jsonl.read_text().splitlines())
    assert "Fooled (ASR %)" in next(out.glob("*_summary.md")).read_text()
