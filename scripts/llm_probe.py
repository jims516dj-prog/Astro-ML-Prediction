"""Diagnostics: is GitHub Models (free, with the workflow's own GITHUB_TOKEN) available to this repository?

One request to a small model with a made-up match; prints whether it answered, the answer, and the rate-limit headers
GitHub returns. No key of ours is involved; the token is never printed."""
import json
import os
import time
import urllib.error
import urllib.request

URL = "https://models.github.ai/inference/chat/completions"
token = os.environ.get("GITHUB_TOKEN")
if not token:
    raise SystemExit("no GITHUB_TOKEN in the environment")
for model in ("openai/gpt-4o-mini", "meta/Llama-3.3-70B-Instruct"):
    body = {"model": model, "temperature": 0, "max_tokens": 200, "messages": [
        {"role": "system", "content": "You estimate football match probabilities. Answer JSON only."},
        {"role": "user", "content": 'Match: Arsenal (home) v Burnley, English Premier League. Bookmaker odds home 1.25, '
                                    'draw 6.5, away 12. Give {"home":p,"draw":p,"away":p,"over25":p} with p in 0..1.'}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            limits = {k: v for k, v in r.headers.items() if "ratelimit" in k.lower()}
            print(f"{model}: OK in {time.time() - t0:.1f}s")
            print("  answer:", (data.get("choices") or [{}])[0].get("message", {}).get("content", "")[:300])
            print("  usage:", data.get("usage"))
            print("  rate limits:", limits)
    except urllib.error.HTTPError as e:
        print(f"{model}: HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
    except Exception as e:  # noqa: BLE001
        print(f"{model}: {type(e).__name__}: {e}")
