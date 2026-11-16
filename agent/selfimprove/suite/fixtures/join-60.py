#!/usr/bin/env python3
"""join-60 — a five-way cross-file reconciliation over 60 customers and 400 orders, under a rule
that is only stated in prose (RULES.md) and that contradicts the naive SUM(paid).

Why this exists: every task in the suite can be answered from one file or one grep. This one needs
four files held together at once (customers, orders, a maintainer exclusion list, and a rules file)
plus a tie-break rule, so an answer produced by skimming one file is wrong in a way the verifier
catches precisely.

Truth: the generator computes it with a plain implementation and publishes it as a judge file.
"""
import csv
import io
import json
import random

CUSTOMERS = 60
ORDERS = 400

VERIFY = r'''import json, sys
t = json.load(open("_truth.json"))
def read(p):
    try:
        return open(p).read().strip()
    except FileNotFoundError:
        return "<missing>"
cnt, total = read("count.txt"), read("total.txt").replace(",", "")
bad = []
if cnt != str(t["count"]):
    bad.append(f"count {cnt!r} != {t['count']}")
try:
    if abs(float(total) - t["total"]) > 0.005:
        bad.append(f"total {total!r} != {t['total']:.2f}")
except ValueError:
    bad.append(f"total {total!r} is not a number")
if bad:
    print("; ".join(bad), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'''


def main():
    rng = random.Random(777001)
    names = ["Aster", "Borealis", "Cinder", "Dovetail", "Elmwood", "Fathom", "Granite", "Harbor",
             "Ironwood", "Juniper", "Kestrel", "Lumen", "Meridian", "Nimbus", "Orchard", "Pallas"]
    customers = []
    for i in range(1, CUSTOMERS + 1):
        customers.append({
            "customer_id": f"C{i:03d}",
            "name": f"{rng.choice(names)} {rng.choice(['Labs', 'Group', 'Systems', 'Works', 'Co'])}",
            "tier": rng.choice(["gold", "silver", "bronze"]),
            "since": f"20{rng.randint(19, 25)}-{rng.randint(1, 12):02d}",
        })
    excluded = {c["customer_id"] for c in rng.sample(customers, 7)}

    orders = []
    want = []
    for i in range(1, ORDERS + 1):
        cust = rng.choice(customers)["customer_id"]
        status = rng.choices(["paid", "refunded", "pending", "void"], weights=[6, 2, 2, 1])[0]
        amount = round(rng.uniform(15, 900), 2)
        day = f"2026-{rng.randint(7, 9):02d}-{rng.randint(1, 28):02d}"
        orders.append({"order_id": f"O{i:04d}", "customer_id": cust, "date": day,
                       "amount": f"{amount:.2f}", "status": status})
        if status == "paid" and cust not in excluded:
            want.append({"order_id": f"O{i:04d}", "customer_id": cust, "date": day, "amount": amount})

    # one paid order per (customer, date): keep the smallest order_id (the double-billing correction)
    seen = {}
    for o in want:
        key = (o["customer_id"], o["date"])
        if key not in seen or o["order_id"] < seen[key]["order_id"]:
            seen[key] = o
    counted = sorted(seen.values(), key=lambda o: o["order_id"])
    truth = {"count": len(counted), "total": round(sum(o["amount"] for o in counted), 2)}

    def table(rows, cols):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})
        return buf.getvalue()

    files = {
        "customers.csv": table(customers, ["customer_id", "name", "tier", "since"]),
        "orders.csv": table(orders, ["order_id", "customer_id", "date", "amount", "status"]),
        "exclusions.txt": "# accounts under reconciliation hold: their orders do not count\n"
                          + "\n".join(sorted(excluded)) + "\n",
        "RULES.md": (
            "# Which orders count\n\n"
            "1. Only orders whose status is `paid` count. `refunded`, `pending` and `void` never do.\n"
            "2. Orders belonging to a customer listed in `exclusions.txt` do not count.\n"
            "3. If the same customer has more than one counting order on the same date, only the\n"
            "   one with the **lowest order_id** counts (this corrects a known double-billing bug\n"
            "   in the invoicing job).\n\n"
            "Report the number of counting orders in `count.txt` and their amounts added together in\n"
            "`total.txt` with exactly two decimal places, no thousands separator, no currency symbol.\n"
        ),
    }
    print(json.dumps({
        "files": files,
        "verify_files": {"_truth.json": json.dumps(truth), "_verify.py": VERIFY},
        "verify": "python3 _verify.py",
        "good": {"count.txt": f"{truth['count']}\n", "total.txt": f"{truth['total']:.2f}\n"},
        "bad": {"count.txt": f"{truth['count'] + 3}\n", "total.txt": f"{truth['total'] + 100:.2f}\n"},
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
