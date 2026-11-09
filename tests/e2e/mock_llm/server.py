"""Tiny OpenAI-compatible stand-in for vLLM, used by the e2e test (CI runners have no GPU).

Speaks just enough of vLLM's surface for the platform to treat it as the real thing:
  GET  /health                  -> 200
  GET  /v1/models               -> one model
  POST /v1/chat/completions     -> canned completion; model "fail" -> 500 (tests the gateway's 502 mapping)
  GET  /metrics                 -> vllm:num_requests_waiting = $MOCK_WAITING (drives the real KEDA ScaledObject)
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b"")
        elif self.path == "/v1/models":
            self._send(200, json.dumps({"data": [{"id": "mock", "object": "model"}]}).encode())
        elif self.path == "/metrics":
            waiting = float(os.getenv("MOCK_WAITING", "0"))
            text = (
                "# TYPE vllm:num_requests_waiting gauge\n"
                f'vllm:num_requests_waiting{{model_name="mock"}} {waiting}\n'
                "# TYPE vllm:num_requests_running gauge\n"
                'vllm:num_requests_running{model_name="mock"} 0\n'
            )
            self._send(200, text.encode(), "text/plain; version=0.0.4")
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path != "/v1/chat/completions":
            self._send(404, b'{"error":"not found"}')
        elif body.get("model") == "fail":
            self._send(500, b'{"error":"simulated engine failure"}')
        else:
            reply = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "model": body.get("model"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                          "max_tokens_seen": body.get("max_tokens")},
            }
            self._send(200, json.dumps(reply).encode())

    def log_message(self, *args):  # keep CI logs quiet
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()  # noqa: S104 - container port
