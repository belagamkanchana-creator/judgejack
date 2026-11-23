"""Judge model backends: something that takes (system prompt, user message) and returns raw text.

    make_backend("ollama:llama3.2:3b")   local model served by Ollama (https://ollama.com)
    make_backend("dummy:approve")        always approves (pipeline check, no model needed)
    make_backend("dummy:block")          always blocks

Decoding is deterministic (temperature 0, fixed seed) so a run can be repeated.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

Backend = Callable[[str, str], str]

OLLAMA_URL = "http://localhost:11434/api/chat"
NUM_CTX = 8192
"""Ollama's default context window is small (2-4K tokens) and it silently drops the START of a
long prompt, which would remove the judge's system prompt. The longest case is ~14K characters
(~4K tokens), so we ask for 8K."""

MAX_REPLY_TOKENS = 1024
"""Cap on the judge's reply. Without it a small model can loop and never stop (seen once with the
reason-first prompt). Default-prompt replies are far shorter (longest 344 characters), so the cap
does not change those results."""


class BackendError(RuntimeError):
    pass


def ollama_request(model: str, system: str, user: str, seed: int = 0) -> dict:
    """The JSON body sent to Ollama's /api/chat (kept separate so it can be tested)."""
    return {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0, "seed": seed, "num_ctx": NUM_CTX, "num_predict": MAX_REPLY_TOKENS},
    }


def ollama_backend(model: str, url: str = OLLAMA_URL, timeout: float = 180, retries: int = 3) -> Backend:
    def call(system: str, user: str) -> str:
        body = json.dumps(ollama_request(model, system, user)).encode()
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read())["message"]["content"]
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
                if attempt == retries - 1:
                    raise BackendError(f"Ollama call failed after {retries} tries: {e}") from e
                time.sleep(2 ** attempt)
        raise AssertionError("unreachable")

    return call


def make_backend(spec: str) -> Backend:
    kind, _, name = spec.partition(":")
    if kind == "ollama" and name:
        return ollama_backend(name)
    if kind == "dummy" and name in ("approve", "block"):
        verdict = name.upper()
        return lambda system, user: json.dumps({"verdict": verdict, "reason": "dummy"})
    raise ValueError(f"Unknown backend {spec!r}: use 'ollama:<model>' or 'dummy:approve' / 'dummy:block'")
