"""Run the dashboard locally exactly as deployed: static files + the same /api backend over the same database.

    python3 site/dev_server.py        then open http://localhost:8000
"""
import sys
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "api"))
import index  # noqa: E402  the deployed backend module


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api"):
            return index.handler.do_GET(self)
        return super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"dashboard + backend on http://localhost:{port}  (database: {index.PACKED.relative_to(HERE)})")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(HERE))).serve_forever()
