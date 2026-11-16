#!$HOME/.pi/agent/laya/.venv/bin/python
"""Laya as a third, independent vote on the same 40 labelled items.

Laya is a different family (encoder + typed heads, one forward pass, ~200 ms, no generation), so its
agreement with a GGUF model is exactly the kind of independence the cross-model gate needs. Joins
against signals.json (A=1.5B canonical, B=3B canonical, Cmaj=1.5B shuffle majority).
"""
import json, os, statistics, time

import laya

HERE = os.path.dirname(os.path.abspath(__file__))
items = [json.loads(l) for l in open(os.path.join(HERE, "items-labelled.jsonl"))]
want = [it["want"] for it in items]

QS = {"label": {
    "type": "choice",
    "instructions": "Which kind of software change is this issue title describing?",
    "criteria": {"bug": "something is broken or errors",
                 "feature": "new capability or behaviour",
                 "docs": "documentation, comments or examples",
                 "chore": "dependency bump, cleanup, version or maintenance"},
}}

BIT = os.path.join(HERE, "laya-bit.json")
if os.environ.get("LAYA_REUSE") and os.path.exists(BIT):
    d = json.load(open(BIT))
    pred, conf = d["laya"], d["conf"]
    print(f"laya: reused {len(pred)} cached answers from {os.path.basename(BIT)}")
else:
    router = laya.Router(max_loaded=1, device="cpu")
    t0 = time.time()
    outs = router.predict_batch([{"state": {"text": it["text"]}, "questions": QS} for it in items],
                                sort_by_length=True)
    dt = time.time() - t0
    pred, conf = [], []
    for o in outs:
        a = o["answers"]["label"] if "answers" in o else o["label"]
        pred.append(a.get("choice"))
        conf.append(a.get("confidence") or 0.0)
    print(f"laya: {len(items)} items in {dt:.1f} s ({dt*1000/len(items):.0f} ms/item)")
    # cache immediately: the join below must never cost a second forward pass
    json.dump({"laya": pred, "conf": conf, "want": want}, open(BIT, "w"))

sig = json.load(open(os.path.join(HERE, "signals.json")))
A, B, C = sig["A"], sig["B"], sig["Cmaj"]


def stats(name, sel):
    if not sel:
        return name, 0, 0, 0.0, 0.0
    ok = sum(1 for i in sel if pred[i] == want[i])
    return name, ok, len(sel), ok / len(sel) * 100, len(sel) / len(items) * 100


def acc2(preds):
    ok = sum(1 for i, p in enumerate(preds) if p == want[i])
    return f"{ok}/{len(want)}", ok / len(want) * 100


rows = [stats("Laya alone (all items)", list(range(len(items))))]
for t in (0.5, 0.7, 0.85, 0.95):
    rows.append(stats(f"Laya confidence >= {t}", [i for i in range(len(items)) if conf[i] >= t]))

three = [i for i in range(len(items)) if A[i] == B[i] == pred[i]]
pair_15_laya = [i for i in range(len(items)) if A[i] == pred[i]]
pair_3_laya = [i for i in range(len(items)) if B[i] == pred[i]]
rows.append(stats("all three agree (1.5B, 3B, Laya)", three))
rows.append(stats("any two of three agree", [i for i in range(len(items))
                                             if len({A[i], B[i], pred[i]}) <= 2]))
rows.append(stats("1.5B == Laya", pair_15_laya))
rows.append(stats("3B == Laya", pair_3_laya))
rows.append(stats("A==B (the old gate, for reference)", [i for i in range(len(items)) if A[i] == B[i]]))
rows.append(stats("A==B AND shuffles agree (old gate)",
                  [i for i in range(len(items)) if A[i] == B[i] and len(set(sig["C"][i])) == 1]))

print(f"\n{'rule':44s}{'correct':>9s}{'n':>5s}{'acc':>7s}{'coverage':>10s}")
for name, ok, k, a_, cov in rows:
    print(f"{name:44s}{ok:>9d}{k:>5d}{a_:>6.0f}%{cov:>9.0f}%")

# majority vote of the three (ties -> escalate)
maj_ok = maj_n = tie = 0
for i in range(len(items)):
    votes = [A[i], B[i], pred[i]]
    top = max(set(votes), key=votes.count)
    if votes.count(top) < 2:
        tie += 1
        continue
    maj_n += 1
    maj_ok += top == want[i]
print(f"\nmajority of 3 (escalating ties): {maj_ok}/{maj_n} correct on covered items "
      f"({maj_ok/maj_n*100:.0f}% precision), coverage {maj_n/len(items)*100:.0f}%, ties {tie}")

print(f"\nLaya confidence: median {statistics.median(conf):.3f}, "
      f"min {min(conf):.3f}, max {max(conf):.3f}")
wrong = [i for i in range(len(items)) if pred[i] != want[i]]
right = [i for i in range(len(items)) if pred[i] == want[i]]
print(f"median confidence when wrong {statistics.median([conf[i] for i in wrong]):.3f} "
      f"vs right {statistics.median([conf[i] for i in right]):.3f}")

