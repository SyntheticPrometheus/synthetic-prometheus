#!/usr/bin/env python3
"""Does repeated sampling + majority vote make a small local model usable unattended?
Unattended means wall-clock is free, so k votes cost nothing. Measures accuracy and how many
items a vote agreement could route to escalation."""
import json, os, sys, time, urllib.request, collections

B = "http://127.0.0.1:9931"
SYS = "Label the item with exactly one of: bug, feature, docs, chore. Reply with the label only."
LABELS = ["bug", "feature", "docs", "chore"]

def post(p, d, t=3600):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=t).read())

def gen(model, text, temp):
    o = post("/v1/chat/completions", {"model": model, "temperature": temp, "max_tokens": 12,
                                      "messages": [{"role": "system", "content": SYS},
                                                   {"role": "user", "content": text}]})
    raw = (o["choices"][0]["message"].get("content") or "").strip().lower()
    for lab in LABELS:                     # first label word wins
        if lab in raw:
            return lab
    return "?" + raw[:8]

items = [json.loads(l) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "items-labelled.jsonl"))]
models = ["qwen2.5-1.5b-instruct-q4_k_m", "Llama-3.2-3B-Instruct-Q4_K_M"]
K = int(sys.argv[1]) if len(sys.argv) > 1 else 3

out = {}
for m in models:
    for other in ["Qwen3-0.6B-Q8_0", "Qwen3-1.7B-Q4_K_M", "Llama-3.2-3B-Instruct-Q4_K_M",
                  "qwen2.5-1.5b-instruct-q4_k_m"]:
        if other != m:
            try: post("/models/unload", {"model": other}, 60)
            except Exception: pass
    t0 = time.time()
    single = [(m, it) for it in items]
    acc1 = 0; res1 = []
    for it in items:
        v = gen(m, it["text"], 0)
        res1.append(v); acc1 += v == it["want"]
    t_single = time.time() - t0

    t0 = time.time()
    voted = []; acck = 0; disagree = 0
    for it in items:
        vs = [gen(m, it["text"], 0.8) for _ in range(K)]
        c = collections.Counter(vs).most_common()
        top = c[0][0]
        tie = len(c) > 1 and c[0][1] == c[1][1]
        if tie or c[0][1] < K - 1:          # no clear majority -> would escalate
            disagree += 1
        voted.append(top); acck += top == it["want"]
    t_votes = time.time() - t0

    out[m] = dict(acc1=acc1, acck=acck, n=len(items), k=K, escalate=disagree,
                  t_single=round(t_single, 1), t_votes=round(t_votes, 1),
                  handoff=[it["id"] for it, v in zip(items, res1) if v != it["want"]])
    print(f"{m}\n  1 vote temp0 : {acc1}/{len(items)} in {t_single:.0f}s ({(t_single/len(items)):.2f}s/item)"
          f"\n  {K} votes maj  : {acck}/{len(items)} in {t_votes:.0f}s ({(t_votes/len(items)/K):.2f}s/vote)"
          f"\n  would escalate: {disagree}/{len(items)}", flush=True)

json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "votes.json"), "w"), indent=1)
print("\nitems 1-vote got wrong (3B):", out[models[1]]["handoff"])
