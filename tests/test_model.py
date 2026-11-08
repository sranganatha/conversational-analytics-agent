import io
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from conversational_analytics_agent.contracts import ContractError
from conversational_analytics_agent.model import MAX_RESPONSE_BYTES, OllamaModel


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.model = OllamaModel("http://ollama:11434", "test-model")
        self.reply = {"done": True, "done_reason": "stop", "message": {
            "role": "assistant", "content": '{"value":120}'}, "prompt_eval_count": 30, "eval_count": 5}

    def assert_code(self, code, function, *arguments):
        with self.assertRaises(ContractError) as caught:
            function(*arguments)
        self.assertEqual(caught.exception.code, code)

    def generate(self, reply=None):
        with patch.object(self.model, "_request", return_value=self.reply if reply is None else reply):
            return self.model.generate([{"role": "user", "content": "Question"}], {"type": "object"}, 5)

    def test_only_explicit_local_endpoints_are_accepted(self):
        for endpoint in ("https://external.example", "http://user:secret@ollama", "file:///tmp/model",
                         "http://ollama/path", "http://ollama?redirect=external"):
            self.assert_code("INVALID_MODEL_ENDPOINT", OllamaModel, endpoint, "model")

    def test_model_identity_must_match_exact_digest(self):
        tags = {"models": [{"name": "test-model", "digest": "expected"}]}
        with patch.object(self.model, "_request", return_value=tags):
            self.assertEqual(self.model.preflight("expected")["digest"], "expected")
            self.assert_code("MODEL_IDENTITY_MISMATCH", self.model.preflight, "changed")

    def test_actual_usage_is_preserved_and_missing_usage_is_unknown(self):
        result, usage = self.generate()
        self.assertEqual(result, {"value": 120})
        self.assertEqual(usage["eval_count"], 5)
        del self.reply["eval_count"]
        _, usage = self.generate()
        self.assertIsNone(usage["eval_count"])

    def test_truncation_empty_and_malformed_outputs_are_distinct(self):
        self.assert_code("MODEL_TRUNCATED", self.generate, {**self.reply, "done_reason": "length"})
        self.assert_code("MODEL_INCOMPLETE", self.generate, {**self.reply, "done": False})
        self.assert_code("MODEL_EMPTY_RESPONSE", self.generate,
                         {**self.reply, "message": {"role": "assistant", "content": ""}})
        self.assert_code("MODEL_SCHEMA_ERROR", self.generate,
                         {**self.reply, "message": {"role": "assistant", "content": "not JSON"}})
        self.assert_code("MODEL_SCHEMA_ERROR", self.generate,
                         {**self.reply, "message": {"role": "assistant", "content": "[]"}})

    def test_request_disables_streaming_and_sets_generation_limits(self):
        with patch.object(self.model, "_request", return_value=self.reply) as request:
            self.model.generate([{"role": "user", "content": "Question"}], {"type": "object"}, 5)
        body = request.call_args.args[1]
        self.assertFalse(body["stream"])
        self.assertEqual(body["options"]["num_predict"], 512)
        self.assertEqual(body["options"]["num_ctx"], 4096)
        self.assertEqual(request.call_args.args[2], 5)

    def test_prompt_budget_prevents_transport(self):
        with patch.object(self.model, "_request") as request:
            self.assert_code("PROMPT_LIMIT", self.model.generate,
                             [{"role": "user", "content": "x" * 16001}], {}, 5)
            request.assert_not_called()

    def test_response_byte_limit_and_invalid_envelope(self):
        for raw, code in ((b"x" * (MAX_RESPONSE_BYTES + 1), "MODEL_RESPONSE_LIMIT"),
                          (b"not json", "MODEL_SCHEMA_ERROR"), (b"[]", "MODEL_SCHEMA_ERROR")):
            with patch.object(self.model._opener, "open", return_value=io.BytesIO(raw)):
                self.assert_code(code, self.model._request, "/api/chat", {}, 5)

    def test_transport_errors_are_redacted_and_not_retried(self):
        for error, code in ((TimeoutError("private details"), "MODEL_TIMEOUT"),
                            (URLError("private details"), "MODEL_UNAVAILABLE"),
                            (HTTPError("http://ollama", 503, "private details", {}, None), "MODEL_HTTP_ERROR")):
            with patch.object(self.model._opener, "open", side_effect=error) as transport:
                self.assert_code(code, self.model._request, "/api/chat", {}, 5)
                transport.assert_called_once()


if __name__ == "__main__":
    unittest.main()
