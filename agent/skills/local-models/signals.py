#!/usr/bin/env python3
"""Which offline signal predicts a wrong answer? Unattended offline-first needs an error detector,
not more votes (votes agreed on the wrong label 39/40 times).

Signals tested per item:
  A  1.5B, temp 0, canonical label order
  B  3B,   temp 0, canonical label order
  C  1.5B, temp 0, label order shuffled 3 ways (positional-bias decorrelation)
  D  cross-model agreement: A == B
  E  cross-order agreement: majority of C, plus how many of 3 orders agreed
Reports accuracy of each single model, and the accuracy/coverage of the "trust local" subsets that
each signal would let through, i.e. what fraction of a cloud bill the residue would be.
"""
import collections, json, os, random, time, urllib.request

B_ = "http://127.0.0.1:9931"
SYS = "Label the item with exactly one of: {opts}. Reply with the label only."
LABELS = ["bug", "feature", "docs", "chore"]
items = [json.loads(l) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "items-labelled.jsonl"))]


def api(path, payload=None, t=3600):
    r = urllib.request.Request(B_ + path, data=json.dumps(payload).encode() if payload else None,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=t) as f:
        body = f.read()
    return json.loads(body) if body else {}


def unload_except(keep):
    for m in [x["id"] for x in api("/v1/models")["data"]]:
        if m != keep:
            try: api("/models/unload", {"model": m}, 60)
            except Exception: pass


def ask(model, text, opts, temp=0.0):
    sysmsg = SYS.format(opts=", ".join(opts))
    o = api("/v1/chat/completions", {"model": model, "temperature": temp, "max_tokens": 12,
                                     "messages": [{"role": "system", "content": sysmsg},
                                                  {"role": "user", "content": text}]})
    raw = (o["choices"][0]["message"].get("content") or "").strip().lower()
    for lab in LABELS:
        if lab in raw:
            return lab
    return "?" + raw[:6]


def run(model, ordered=True, reps=1):
    unload_except(model)
    out = []
    for it in items:
        samples = []
        for _ in range(reps):
            opts = LABELS[:] if ordered else random.sample(LABELS, len(LABELS))
            samples.append(ask(model, it["text"], opts))   # positions vary between samples
        out.append(samples)
    return out


M15, M3 = "qwen2.5-1.5b-instruct-q4_k_m", "Llama-3.2-3B-Instruct-Q4_K_M"
random.seed(7)
t0 = time.time()
A = run(M15, ordered=True, reps=1)
A = [x[0] for x in A]
print(f"A 1.5B canonical done {time.time()-t0:.0f}s", flush=True)

t0 = time.time()
Bv = run(M3, ordered=True, reps=1)
Bv = [x[0] for x in Bv]
print(f"B 3B canonical done {time.time()-t0:.0f}s", flush=True)

t0 = time.time()
Cv = run(M15, ordered=False, reps=3)
print(f"C 1.5B shuffled x3 done {time.time()-t0:.0f}s", flush=True)

want = [it["want"] for it in items]
n = len(items)


def rate(sel):
    if not sel: return 0, 0
    ok = sum(1 for i in sel if A[i] == want[i])
    return ok, len(sel)


Cmaj = []
for vs in Cv:
    c = collections.Counter([v for v in vs if not v.startswith("?")])
    Cmaj.append(c.most_common(1)[0][0] if c else vs[0])

rows = []
rows.append(("1.5B canonical (A)", *rate(range(n))))
rows.append(("3B canonical (B)", sum(1 for i in range(n) if Bv[i] == want[i]), n))
rows.append(("1.5B shuffled majority (C)", sum(1 for i in range(n) if Cmaj[i] == want[i]), n))

agree_ab = [i for i in range(n) if A[i] == Bv[i]]
rows.append(("TRUST where A==B (cross-model)", *rate(agree_ab)))
dis_ab = [i for i in range(n) if A[i] != Bv[i]]
rows.append(("ESCALATE where A!=B (accuracy there)", *rate(dis_ab)))

agree_c = [i for i in range(n) if len(set(v for v in Cv[i] if not v.startswith("?"))) == 1]
rows.append(("TRUST where 3 shuffles agree", *rate(agree_c)))

both = [i for i in range(n) if i in set(agree_ab) and i in set(agree_c)]
rows.append(("TRUST where A==B AND shuffles agree", *rate(both)))

print(f"\n{'signal':44s}{'correct':>9s}{'n':>6s}{'acc':>7s}{'coverage':>10s}")
for name, ok, k in rows:
    print(f"{name:44s}{ok:>9d}{k:>6d}{(ok/k*100 if k else 0):>6.0f}%{(k/n*100 if name.startswith('TRUST') else 0):>9.0f}%")

residue = [i for i in range(n) if i not in set(both)]
print(f"\nresidue for the cloud after 'A==B AND shuffles agree': {len(residue)}/{n} "
      f"({len(residue)/n*100:.0f}%), and local got {rate(both)[0]}/{rate(both)[1]} of the rest right")
json.dump({"A": A, "B": Bv, "C": Cv, "Cmaj": Cmaj, "want": want},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals.json"), "w"), indent=1)
