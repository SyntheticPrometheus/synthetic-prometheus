#!/usr/bin/env python3
"""litwalk — recursive citation-graph literature walk over OpenAlex (no key needed).

Why: a keyword search returns the papers everyone cites; walking `referenced_works`
(backward) and `cited_by` (forward) from a seed returns the *structure* of a field, and
2 hops surface the papers that a single query cannot rank. This is the tool behind
`research/curiosity-creativity.md`; it is re-run when the loop in
`skills/curiosity/SKILL.md` says the literature may have moved.

  litwalk.py seeds  <file.json>          # ids/titles of the seed set (hand-picked canonical works)
  litwalk.py walk   --seeds <file> --out <json> [--depth 2] [--cap 400]
  litwalk.py report --in <json> [--top 60] [--min-cites N] [--since YEAR]

OpenAlex etiquette: cache every response on disk (`research/.litwalk-cache/`), one request
at a time, `mailto` in the query string. Reconstruct abstracts from the inverted index.
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

HOME = Path.home()
CACHE = HOME / ".pi/agent/research/.litwalk-cache"
API = "https://api.openalex.org"
UA = "pi-agent-litwalk/1.0 (mailto:host@localhost)"
SELECT = "id,doi,title,publication_year,cited_by_count,referenced_works,cited_by_api_url,abstract_inverted_index,primary_location,authorships,type,open_access"


def get(url, cache_key=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    if cache_key:
        p = CACHE / (re.sub(r"[^A-Za-z0-9_.-]", "_", cache_key)[:180] + ".json")
        if p.exists():
            return json.loads(p.read_text())
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.loads(r.read().decode())
            if cache_key:
                p.write_text(json.dumps(d))
            return d
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def abstract(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def norm_id(x):
    if not x:
        return None
    x = str(x).strip()
    if x.startswith("https://openalex.org/"):
        return x.rsplit("/", 1)[-1]
    if x.startswith("W"):
        return x
    if re.fullmatch(r"\d+", x):
        return "W" + x
    return x


def work_record(w):
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {}).get("display_name") or ""
    auth = [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])][:3]
    return {
        "id": norm_id(w.get("id")),
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "title": re.sub(r"\s+", " ", w.get("title") or "").strip(),
        "year": w.get("publication_year"),
        "cites": w.get("cited_by_count") or 0,
        "venue": src,
        "authors": [a for a in auth if a],
        "abstract": abstract(w.get("abstract_inverted_index")),
        "refs": [norm_id(r) for r in (w.get("referenced_works") or [])],
        "type": w.get("type"),
    }


def find_seed(q):
    """Resolve a title-ish string to its best OpenAlex work."""
    url = f"{API}/works?search={urllib.parse.quote(q)}&per-page=3&select=id,title,publication_year,cited_by_count"
    d = get(url, "search_" + q)
    for r in d.get("results", []):
        if r.get("id"):
            return norm_id(r["id"])
    return None


def fetch_work(wid):
    d = get(f"{API}/works/{wid}?select={SELECT}", "work_" + wid)
    if not d.get("id"):
        return None
    return work_record(d)


def forward(wid, cap=25, since=None):
    """Most-cited works citing this one (optionally recent only)."""
    filt = f"cites:{wid}"
    if since:
        filt += f",from_publication_date:{since}-01-01"
    url = f"{API}/works?filter={filt}&sort=cited_by_count:desc&per-page={cap}&select=id,title,publication_year,cited_by_count,type"
    d = get(url, f"fwd_{wid}_{since}_{cap}")
    return [norm_id(r["id"]) for r in d.get("results", []) if r.get("id")]


def fetch_many(ids):
    """Batch-fetch works (OpenAlex accepts up to 50 pipe-separated ids)."""
    out = {}
    ids = [i for i in ids if i]
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        url = (f"{API}/works?filter=openalex_id:{'|'.join(chunk)}"
               f"&per-page=50&select={SELECT}")
        d = get(url, "batch_" + "_".join(chunk[:3]) + f"_{len(chunk)}")
        for w in d.get("results", []):
            if w.get("id"):
                r = work_record(w)
                out[r["id"]] = r
    return out


def walk(seed_ids, out, depth=2, cap=400):
    store = {}
    if isinstance(seed_ids, dict):
        seed_ids = list(seed_ids.values())
    layer = [norm_id(i) for i in seed_ids if i]
    for d in range(depth + 1):
        fresh = [i for i in dict.fromkeys(layer) if i not in store][: max(0, cap - len(store))]
        got = fetch_many(fresh)
        store.update(got)
        print(f"depth {d}: fetched {len(got)} (total {len(store)})", file=sys.stderr)
        if d == depth or not got:
            break
        nxt = []
        for wid, rec in got.items():
            nxt.extend(rec["refs"][:18])
        # forward only from seeds (depth 0) and the 10 most-cited depth-1 works
        src = list(got) if d == 0 else [w for w, _ in sorted(got.items(), key=lambda kv: -kv[1]["cites"])[:10]]
        for wid in src:
            if len(nxt) > cap * 3:
                break
            nxt.extend(forward(wid, cap=20))
        layer = nxt
    Path(out).write_text(json.dumps(store, indent=1))
    print(f"{len(store)} works -> {out}")


def report(path, top=60, min_cites=0, since=None, grep=None, json_out=None, grep_title=None, rank="cites"):
    store = json.loads(Path(path).read_text())
    rows = []
    for wid, r in store.items():
        if since and (r.get("year") or 0) < since:
            continue
        if r["cites"] < min_cites:
            continue
        if grep and not re.search(grep, r["title"] + " " + r["abstract"], re.I):
            continue
        if grep_title and not re.search(grep_title, r["title"], re.I):
            continue
        rows.append(r)
    if rank == "relevance":
        rows.sort(key=lambda r: -(3 * bool(grep_title and re.search(grep_title, r["title"], re.I))
                                  + (r["cites"] + 1) ** 0.4))
    else:
        rows.sort(key=lambda r: -r["cites"])
    for r in rows[:top]:
        ab = re.sub(r"\s+", " ", r["abstract"])[:430]
        print(f"### {r['id']} {r['year']} cites={r['cites']} {r['doi']}\n{r['title']}\n{r['venue']}\n{ab}\n")
    if json_out:
        Path(json_out).write_text(json.dumps([r["id"] for r in rows[:top]]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seeds")
    s.add_argument("file")
    w = sub.add_parser("walk")
    w.add_argument("--seeds", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--depth", type=int, default=2)
    w.add_argument("--cap", type=int, default=400)
    r = sub.add_parser("report")
    r.add_argument("--in", dest="inp", required=True)
    r.add_argument("--top", type=int, default=60)
    r.add_argument("--min-cites", type=int, default=0)
    r.add_argument("--since", type=int)
    r.add_argument("--grep", help="regex on title+abstract (domain scoping)")
    r.add_argument("--json-out", help="write the passing ids as a seed list")
    r.add_argument("--grep-title", help="regex on title only (stricter domain scoping)")
    r.add_argument("--rank", choices=["cites", "relevance"], default="cites")
    a = ap.parse_args()
    if a.cmd == "seeds":
        qs = json.loads(Path(a.file).read_text())
        out = {}
        for q in qs:
            wid = find_seed(q)
            out[q] = wid
            print(f"{wid or 'MISS':12s} {q}")
        Path(a.file.replace(".json", ".resolved.json")).write_text(json.dumps(out, indent=1))
    elif a.cmd == "walk":
        walk(json.loads(Path(a.seeds).read_text()), a.out, a.depth, a.cap)
    elif a.cmd == "report":
        report(a.inp, a.top, a.min_cites, a.since, a.grep, a.json_out, a.grep_title, a.rank)


if __name__ == "__main__":
    main()
