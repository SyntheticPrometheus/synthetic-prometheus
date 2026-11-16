#!/usr/bin/env python3
"""Objective local-model eval v2: raw outputs saved, graders deterministic, no LLM judge."""
import json, re, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:9931"

def post(path, payload, timeout=1800):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def status(model):
    d = json.loads(urllib.request.urlopen(BASE + "/v1/models", timeout=30).read())
    for m in d["data"]:
        if m["id"] == model:
            s = m.get("status")
            return s.get("value") if isinstance(s, dict) else s
    return None

def load(model):
    if status(model) == "loaded":
        return
    try: post("/models/load", {"model": model}, timeout=900)
    except urllib.error.HTTPError as e:
        if e.code != 400: raise
    for _ in range(180):
        if status(model) == "loaded": return
        time.sleep(1)
    raise RuntimeError("load timeout " + model)

def chat(model, system, user, max_tokens=300):
    t0 = time.time()
    payload = {"model": model, "temperature": 0, "max_tokens": max_tokens,
               "chat_template_kwargs": {"enable_thinking": False},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    out = post("/v1/chat/completions", payload)
    dt = time.time() - t0
    msg = out["choices"][0]["message"]
    txt = msg.get("content") or ""
    if not txt.strip():
        txt = msg.get("reasoning_content") or ""
    u = out.get("usage", {})
    return txt, dt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

LOG = """commit 4f2a91c (HEAD -> main)
Author: Dana Whitfield <dana@example.org>
Date:   Tue Mar 4 09:12:44 2025 +0100

    fix(parser): handle empty input file

 src/parse.c        | 14 ++++++++------
 tests/parse_test.c | 22 ++++++++++++++++++++++
 2 files changed, 28 insertions(+), 8 deletions(-)
"""

PARA = ("The router keeps a single KV cache shared by all server slots. When a model is "
        "loaded it allocates the pool up front, so long prompts from one client can evict "
        "cached prefixes used by another. Setting a smaller context per slot avoids the "
        "problem at the cost of rejecting very long prompts, and the server returns 400 "
        "rather than truncating. Operators are advised to size the pool for the largest "
        "expected prompt times the number of parallel slots they enable.")

DIFF = """--- a/src/http.c
+++ b/src/http.c
@@ -40,6 +40,9 @@ static int read_head(struct conn *c)
-    int n = recv(c->fd, buf, sizeof buf, 0);
-    if (n <= 0) return -1;
+    int n = recv(c->fd, buf, sizeof buf, 0);
+    if (n == 0) return -2;                   /* peer closed cleanly */
+    if (n < 0 && errno == EAGAIN) return -3; /* retry later */
+    if (n < 0) return -1;
     c->head_len += n;
     return 0;
 }
"""

ISSUES = [("Login page returns 500 when the email field is empty", "bug"),
          ("Add dark mode to the settings screen", "feature"),
          ("README install section still mentions pip install -e ., but we moved to uv", "docs"),
          ("Bump ruff from 0.4.1 to 0.5.0", "chore")]

TOOLS = """Available tools:
- fs_read(path: string) -> string
- fs_write(path: string, content: string) -> void
- shell(cmd: string) -> string
Reply with ONLY a JSON object {"tool": "<name>", "args": {...}} for the single best next call."""

def strip_fence(t):
    t = t.strip()
    t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()

def as_json(t):
    t = strip_fence(t)
    try: return json.loads(t)
    except Exception: pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    return None

def g_json_extract(t):
    o = as_json(t)
    if not isinstance(o, dict): return 0.0, "no json"
    auth = str(o.get("author", "")); files = o.get("files") or []
    files = files if isinstance(files, list) else [str(files)]
    pts = [("Dana Whitfield" in auth), ("2025-03-04" in str(o.get("date", ""))),
           (len(files) == 2 and any("parse.c" == f.rsplit("/", 1)[-1] for f in map(str, files))
            and any("parse_test.c" == f.rsplit("/", 1)[-1] for f in map(str, files)))]
    return (1.0 if all(pts) else 0.0), f"json ok {sum(pts)}/3"

def g_summarize(t):
    low = t.lower()
    facts = [("kv cache" in low or "kv-cache" in low), ("slot" in low),
             ("400" in low or "reject" in low or "per slot" in low)]
    sents = len([s for s in re.split(r"(?<=[.!?])\s+", strip_fence(t)) if s.strip()])
    invented = set(re.findall(r"\b\d{2,}\b", low)) - {"400"}
    ok = sum(facts) >= 2 and sents <= 2 and not invented and len(t) > 40
    return (1.0 if ok else 0.0), f"facts={sum(facts)}/3 sents={sents} invented={sorted(invented)}"

def g_classify(t):
    got = [w for w in re.findall(r"\b(bug|feature|docs|chore)\b", t.lower())]
    want = [w for _, w in ISSUES]
    return (1.0 if got[:4] == want else 0.0), f"{got[:4]}"

def g_commit(t):
    subj = strip_fence(t).strip().splitlines()[0].strip().strip('"') if strip_fence(t).strip() else ""
    conv = bool(re.match(r"^(fix|feat|refactor|chore|perf)(\([\w/.,-]+\))?!?: .+", subj))
    topic = bool(re.search(r"recv|read_head|eagain|timeout|closed|error", subj, re.I))
    ok = conv and topic
    return (1.0 if ok else 0.0), f"{subj[:80]} | conv={conv} topic={topic}"

def g_tool(t):
    o = as_json(t)
    if not isinstance(o, dict): return 0.0, "no json"
    name = o.get("tool") or o.get("name")
    args = o.get("args") or o.get("arguments") or {}
    cmd = json.dumps(args)
    ok = name == "shell" and "rm" in cmd and "/tmp/build.log" in cmd
    return (1.0 if ok else 0.0), f"{name} {cmd[:70]}"

TASKS = [
 ("json_extract", "Extract the commit author, the date as YYYY-MM-DD, and the list of changed file paths. Reply with only JSON matching {\"author\": str, \"date\": \"YYYY-MM-DD\", \"files\": [str]}.", LOG, g_json_extract),
 ("summarize", "Summarise the text in at most two sentences, using only facts stated in it. Reply with the summary only.", PARA, g_summarize),
 ("classify", "Give each numbered item exactly one label: bug, feature, docs, or chore. Reply with only the four labels, one per line.", "\n".join(f"{i+1}. {t}" for i, (t, _) in enumerate(ISSUES)), g_classify),
 ("commit_msg", "Write a Conventional Commits subject line (max 72 chars, format: type(scope): summary) for this diff. Reply with only the subject line.", DIFF, g_commit),
 ("tool_call", TOOLS, "Remove /tmp/build.log and show me the command output.", g_tool),
]

MODELS = ["Qwen3-0.6B-Q8_0", "qwen2.5-1.5b-instruct-q4_k_m", "Qwen3-1.7B-Q4_K_M",
          "Llama-3.2-3B-Instruct-Q4_K_M"]
QWEN3 = {"Qwen3-0.6B-Q8_0", "Qwen3-1.7B-Q4_K_M"}

raw, results = {}, {}
for model in MODELS:
    print(f"\n===== {model}", flush=True)
    load(model); time.sleep(1)
    row = {}
    for name, sysmsg, user, grader in TASKS:
        if model in QWEN3:
            sysmsg = "/no_think " + sysmsg
        txt, dt, pt, ct = chat(model, sysmsg, user)
        score, why = grader(txt)
        row[name] = score
        raw[f"{model}|{name}"] = {"out": txt, "secs": round(dt, 1), "ptok": pt, "ctok": ct, "score": score}
        print(f"  {name:12s} {score:.0f} {dt:6.1f}s in={pt:4d} out={ct:3d}  {why}", flush=True)
    results[model] = row
    try: post("/models/unload", {"model": model}, timeout=120)
    except Exception: pass

json.dump(raw, open(__file__.rsplit("/", 1)[0] + "/raw.json", "w"), indent=1)
print("\n=== summary (5 tasks) ===")
names = [t[0] for t in TASKS]
print(f"{'task':14s}" + "".join(f"{m[:17]:>19s}" for m in MODELS))
for n in names:
    print(f"{n:14s}" + "".join(f"{results[m][n]:>19.0f}" for m in MODELS))
print(f"{'TOTAL':14s}" + "".join(f"{sum(results[m].values()):>16.0f}/5" for m in MODELS))
