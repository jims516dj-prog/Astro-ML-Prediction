import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from astrofoot import sync


class FakeGitHub(BaseHTTPRequestHandler):
    """Minimal stand-in for the GitHub Actions API: one dispatch, a run that finishes on the third poll."""
    calls: list = []
    polls = 0

    def log_message(self, *a):
        pass

    def _reply(self, code, body=None):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def do_POST(self):
        FakeGitHub.calls.append(("POST", self.path, self.headers.get("Authorization"),
                                 json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
        self._reply(204)

    def do_GET(self):
        FakeGitHub.calls.append(("GET", self.path, self.headers.get("Authorization"), None))
        FakeGitHub.polls += 1
        now = datetime.now(timezone.utc) + timedelta(seconds=1)
        old = {"id": 1, "created_at": "2020-01-01T00:00:00Z", "status": "completed", "conclusion": "success"}
        if FakeGitHub.polls == 1:
            runs = [old]                                             # our run not visible yet
        else:
            runs = [old, {"id": 2, "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "status": "in_progress" if FakeGitHub.polls == 2 else "completed", "conclusion":
                          None if FakeGitHub.polls == 2 else "success"}]
        self._reply(200, {"workflow_runs": runs})


@pytest.fixture
def fake():
    FakeGitHub.calls, FakeGitHub.polls = [], 0
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_run_cycle_dispatches_waits_and_ignores_older_runs(fake):
    phases = []
    out = sync.run_cycle(lambda p, d="": phases.append(p), tok="t0k", slug="me/repo", base=fake, poll=0.01)
    assert out == "success"
    post = FakeGitHub.calls[0]
    assert post[0] == "POST" and post[1] == "/repos/me/repo/actions/workflows/track-record.yml/dispatches"
    assert post[2] == "Bearer t0k" and post[3] == {"ref": "main"}
    assert FakeGitHub.polls == 3 and "running" in phases          # waited through in_progress, skipped run 1


def test_run_cycle_requires_a_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sync, "TOKEN_FILE", sync.ROOT / "no-such-token-file")
    with pytest.raises(RuntimeError, match="token"):
        sync.run_cycle(slug="me/repo")
