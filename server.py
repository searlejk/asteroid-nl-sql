"""Web server for the asteroid question box.

    python3 server.py [port]         (default 8452) then open http://localhost:8452

API:
    GET  /api/info                 dataset facts, model name, strategies, example questions
    POST /api/ask {question, strategy?}  -> sql, columns, rows, answer, timings
"""
import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import db
import llm
import nlq

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, "web")

EXAMPLE_QUESTIONS = [
    "How many asteroids are there?",
    "How many asteroids will come within 1 million km of Earth in the next 10 years?",
    "What is the closest an asteroid will come to Earth in the next year?",
    "When will Apophis pass Earth, and how close will it get?",
    "Which asteroid has the highest chance of hitting Earth?",
    "How many potentially hazardous asteroids are bigger than 1 km?",
    "What is the largest asteroid?",
    "Which asteroids passed closer than the Moon in 2025?",
]

_provider = None
_provider_lock = threading.Lock()


def provider():
    global _provider
    with _provider_lock:
        if _provider is None:
            _provider = llm.make_provider()
        return _provider


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, obj, status=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/info":
            try:
                info = db.dataset_info()
                counts = db.run_query(
                    "SELECT (SELECT COUNT(*) FROM asteroids), (SELECT COUNT(*) FROM asteroids WHERE is_neo=1),"
                    " (SELECT COUNT(*) FROM asteroids WHERE is_pha=1), (SELECT COUNT(*) FROM close_approaches),"
                    " (SELECT COUNT(*) FROM impact_risk)")["rows"][0]
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            cfg = llm.load_config()
            return self._json({
                "dataset": info,
                "counts": dict(zip(["asteroids", "neo", "pha", "close_approaches", "impact_risk"], counts)),
                "model": _provider.name if _provider else
                         (f"OpenAI {cfg['openaiModel']}" if cfg["openaiKey"] and cfg["provider"] != "local"
                          else "local model"),
                "strategies": nlq.STRATEGIES,
                "default_strategy": nlq.DEFAULT_STRATEGY,
                "examples": EXAMPLE_QUESTIONS,
            })
        if self.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/ask":
            return self._json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(min(n, 20_000)) or b"{}")
            question = str(req.get("question", "")).strip()[:500]
            strategy = req.get("strategy") or nlq.DEFAULT_STRATEGY
            if not question:
                return self._json({"error": "Please type a question."}, 400)
            if strategy not in nlq.STRATEGIES:
                return self._json({"error": f"Unknown strategy {strategy}"}, 400)
            return self._json(nlq.ask(provider(), question, strategy))
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8452
    print(f"Loading model... ", end="", flush=True)
    print(provider().name)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Asteroid Q&A running at http://localhost:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
