"""On-demand update: ask GitHub to run the live-forecast cycle now, wait for it, then pull.

GitHub stays the only writer of the ledger (two writers would produce conflicting copies); this just
starts the same job the schedule runs. It needs a token you create and keep yourself, limited to this
repository with "Actions: Read and write" permission, in one of:
  - the environment variable GITHUB_TOKEN, or
  - a file named .github_token in the project folder (git-ignored, never uploaded).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

from .config import ROOT

API = "https://api.github.com"
WORKFLOW = "track-record.yml"
TOKEN_FILE = ROOT / ".github_token"


def token() -> str | None:
    t = os.environ.get("GITHUB_TOKEN")
    if not t and TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text().strip()
    return t or None


def repo_slug() -> str | None:
    """owner/repo of the `origin` remote, e.g. jims516dj-prog/Astro-ML-Prediction."""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True,
                             timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _api(method: str, path: str, tok: str, body: dict | None = None, base: str = API):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "astro-football-app"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def run_cycle(progress=lambda phase, detail="": None, tok: str | None = None, slug: str | None = None,
              base: str = API, poll: float = 5.0, timeout: float = 600.0) -> str:
    """Dispatch the cycle workflow and wait for it. Returns the run's conclusion ('success', ...)."""
    tok, slug = tok or token(), slug or repo_slug()
    if not tok:
        raise RuntimeError("no GitHub token configured")
    if not slug:
        raise RuntimeError("could not tell which GitHub repository this folder comes from")
    t0 = datetime.now(timezone.utc).replace(microsecond=0)
    progress("starting", "Asking GitHub to run the forecast and results cycle now")
    _api("POST", f"/repos/{slug}/actions/workflows/{WORKFLOW}/dispatches", tok, {"ref": "main"}, base)
    deadline = time.time() + timeout
    run = None
    while time.time() < deadline:
        time.sleep(poll)
        runs = (_api("GET", f"/repos/{slug}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=5",
                     tok, base=base) or {}).get("workflow_runs", [])
        mine = [r for r in runs if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= t0]
        if mine:
            run = mine[-1]
            if run["status"] == "completed":
                return run["conclusion"] or "unknown"
            progress("running", f"GitHub is fetching fixtures, odds and results (run {run['id']}, {run['status']})")
        else:
            progress("starting", "Waiting for GitHub to start the run")
    raise RuntimeError("GitHub did not finish the run within 10 minutes; try Get latest results later")
