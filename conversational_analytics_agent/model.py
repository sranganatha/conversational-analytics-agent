"""One bounded Ollama structured-output client, with no retries or fallbacks."""

import json
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from .contracts import ContractError, integer, require, text

MAX_RESPONSE_BYTES = 65536
MAX_PROMPT_CHARS = 16000


class OllamaModel:
    def __init__(self, base_url: str, model: str):
        parsed = urlparse(base_url)
        require(parsed.scheme == "http" and parsed.hostname in {"ollama", "localhost", "127.0.0.1"}
                and not parsed.username and not parsed.password and parsed.path in ("", "/")
                and not parsed.query and not parsed.fragment, "INVALID_MODEL_ENDPOINT")
        self.base_url = base_url.rstrip("/")
        self.model = text(model, 150)
        self.identity: dict[str, Any] = {"model": model, "digest": None}
        self._opener = build_opener(ProxyHandler({}))

    def _request(self, path: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        require(timeout > 0, "TURN_TIMEOUT")
        request = Request(self.base_url + path, data=json.dumps(body).encode() if body else None,
                          headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            require(len(raw) <= MAX_RESPONSE_BYTES, "MODEL_RESPONSE_LIMIT")
            value = json.loads(raw)
            require(type(value) is dict, "MODEL_SCHEMA_ERROR")
            return value
        except ContractError:
            raise
        except HTTPError as exc:
            raise ContractError("MODEL_HTTP_ERROR") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ContractError("MODEL_TIMEOUT") from exc
        except URLError as exc:
            raise ContractError("MODEL_TIMEOUT" if isinstance(exc.reason, TimeoutError) else "MODEL_UNAVAILABLE") from exc
        except (ValueError, UnicodeError) as exc:
            raise ContractError("MODEL_SCHEMA_ERROR") from exc

    def preflight(self, expected_digest: str) -> dict[str, Any]:
        text(expected_digest, 100)
        tags = self._request("/api/tags", None, 10)
        matches = [item for item in tags.get("models", []) if item.get("name") == self.model]
        require(len(matches) == 1 and matches[0].get("digest") == expected_digest, "MODEL_IDENTITY_MISMATCH")
        self.identity = {"model": self.model, "digest": expected_digest}
        return dict(self.identity)

    def generate(self, messages: list[dict[str, str]], schema: dict[str, Any], timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
        require(sum(len(message["content"]) for message in messages) <= MAX_PROMPT_CHARS, "PROMPT_LIMIT")
        started = time.monotonic()
        value = self._request("/api/chat", {"model": self.model, "messages": messages,
            "format": schema, "stream": False, "think": False, "keep_alive": "5m",
            "options": {"temperature": 0, "seed": 7, "num_predict": 512, "num_ctx": 4096}}, timeout)
        require(value.get("done") is True, "MODEL_INCOMPLETE")
        require(value.get("done_reason") != "length", "MODEL_TRUNCATED")
        require(value.get("done_reason") == "stop", "MODEL_INCOMPLETE")
        message = value.get("message")
        require(type(message) is dict and message.get("role") == "assistant", "MODEL_SCHEMA_ERROR")
        content = message.get("content")
        require(type(content) is str and content.strip(), "MODEL_EMPTY_RESPONSE")
        require(len(content) <= 6000, "MODEL_RESPONSE_LIMIT")
        try:
            result = json.loads(content)
        except ValueError as exc:
            raise ContractError("MODEL_SCHEMA_ERROR") from exc
        require(type(result) is dict, "MODEL_SCHEMA_ERROR")
        usage = {}
        for name in ("prompt_eval_count", "eval_count"):
            count = value.get(name)
            usage[name] = integer(count) if count is not None else None
        return result, {**self.identity, **usage, "elapsed_ms": round((time.monotonic() - started) * 1000, 2)}
