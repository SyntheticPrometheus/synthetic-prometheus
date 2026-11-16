#!/usr/bin/env python3
"""bench — does the ranked map beat a naive listing at finding a named symbol?

Task being measured (the one the map exists for): "the task names an identifier — is the file that
defines it, and the definition itself, inside a 500/1000/2000-token map?" That is what changes the
next action: a hit means read that file, a miss means fall back to grep.

Ground truth is the index itself (regex definitions), so this measures *ranking*, not extraction
quality — extraction is covered by `--check` examples below. Baselines use the same renderer and
the same per-file cap; only the file ordering changes:

  path     files in alphabetical order            (a human's `ls | head`)
  size     files by byte size, largest first      (the "read the big files" heuristic)
  size/ref files by (size x in-degree), i.e. what grep over the whole tree would surface

Usage:
  bench.py [--root DIR] [--sample 30] [--budgets 500,1000,2000] [--json]
  bench.py --root ~/.pi/agent --sample 60

Exit 0 always (it is a report); numbers are printed as markdown.
"""
from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

AGENT = Path(os.environ.get("PI_AGENT_DIR") or (Path.home() / ".pi" / "agent"))
BIN = AGENT / "bin" / "pi-repomap"


def load_module():
    loader = importlib.machinery.SourceFileLoader("pi_repomap", str(BIN))
    spec = importlib.util.spec_from_loader("pi_repomap", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def pick_symbols(idx, n, seed=7):
    """Symbols defined in exactly one file, name unique enough to be a real query."""
    defines = {}
    for rel, rec in idx["files"].items():
        for name, kind, no, sig in rec["symbols"]:
            if kind not in ("fn", "class", "struct", "trait", "enum", "type", "impl", "h1", "h2"):
                continue
            defines.setdefault(name, []).append(rel)
    cand = sorted((name, rels[0]) for name, rels in defines.items()
                  if len(rels) == 1 and len(name) >= 5 and name.lower() not in
                  {"index", "main", "config", "setup", "install", "window", "windows"})
    rnd = random.Random(seed)
    if len(cand) > n:
        cand = rnd.sample(cand, n)
    return cand


def pick_files(idx, n, seed=11):
    """File-uniform sample: (None, rel) so only file coverage is scored, not symbol recall."""
    files = sorted(rel for rel, rec in idx["files"].items() if rec["symbols"])
    rnd = random.Random(seed)
    if len(files) > n:
        files = rnd.sample(files, n)
    return [(None, rel) for rel in files]


def word_in(line, name):
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", line) is not None


def rank_size(idx):
    return {rel: float(rec.get("size", 0)) for rel, rec in idx["files"].items()}


def rank_ident(idx):
    return {rel: float(len(rec.get("idents", []))) for rel, rec in idx["files"].items()}


def rank_path(idx):
    return {rel: -float(i) for i, rel in enumerate(sorted(idx["files"]))}


BASELINES = {"path": rank_path, "size": rank_size, "ident": rank_ident}


def parse_groups(text):
    groups, cur = {}, None
    for line in text.splitlines():
        if line and not line.startswith("│") and not line.startswith("⋮"):
            cur = line[:-1] if line.endswith(":") else line
            cur = cur.rstrip(":").split(" (cont.)")[0]
            groups.setdefault(cur, [])
        elif line.startswith("│") and cur:
            groups[cur].append(line)
    return groups


def measure(m, idx, symbols, budget, ranking, mention=True):
    """Hit rates for one ranking.

    mention=True mirrors a task that names the identifier (the ranking is personalised by it;
    the informative number there is the file *rank*). mention=False is the harder, more honest
    test of the graph: rank the whole tree with no literal hint and see whether the defining file
    still makes the budget.
    """
    sym_hits = file_hits = 0
    ranks = []
    for name, rel in symbols:
        hint = [name] if mention else ()
        if ranking == "repomap":
            pr = m.rank_files(idx, (), hint)
        else:
            pr = BASELINES[ranking](idx)  # order-only substitution; same renderer and hint
        text, _ = m.render_map(idx, pr, budget, 4.0, hint)
        groups = parse_groups(text)
        if rel in groups:
            file_hits += 1
            ranks.append(list(groups).index(rel) + 1)
        if name is not None and any(word_in(l, name) for l in groups.get(rel, [])):
            sym_hits += 1
    n = max(1, len(symbols))
    return sym_hits / n, file_hits / n, statistics.mean(ranks) if ranks else 0.0


def coverage(m, idx, budget):
    total = sum(len(r["symbols"]) for r in idx["files"].values())
    pr = m.rank_files(idx)
    text, _ = m.render_map(idx, pr, budget, 4.0)
    shown = sum(1 for l in text.splitlines() if l.startswith("│"))
    files = len({l.rstrip(":").split(" (cont.)")[0] for l in text.splitlines()
                 if l and not l.startswith("│") and not l.startswith("⋮")})
    return shown, total, files, len(idx["files"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path.home() / "Projects" / "pergola"))
    ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--budgets", default="500,1000,2000")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    m = load_module()
    root = Path(a.root).expanduser().resolve()
    budgets = [int(b) for b in a.budgets.split(",")]
    t0 = time.time()
    idx = m.build_index(root, [], use_cache=False)
    cold = time.time() - t0
    t0 = time.time()
    idx = m.build_index(root, [], use_cache=True)
    warm = time.time() - t0
    symbols = pick_symbols(idx, a.sample)
    file_sample = pick_files(idx, max(a.sample, 30))
    rows = []
    for mention, sample, label in ((True, symbols, "named"), (False, symbols, "graph"),
                                   (False, file_sample, "fileuniform")):
        for budget in budgets:
            for ranker in ("repomap", "path", "size", "ident"):
                s, f, r = measure(m, idx, sample, budget, ranker, mention)
                rows.append({"ranking": ranker, "budget": budget, "condition": label,
                             "sym": s, "file": f, "rank": r})
    cov = {b: coverage(m, idx, b) for b in (1000,)}
    out = {"root": str(root), "files": len(idx["files"]),
           "symbols": idx["_stats"]["symbols"], "sample": len(symbols),
           "cold_s": round(cold, 2), "warm_s": round(warm, 3), "rows": rows,
           "coverage_1000": cov[1000]}
    if a.json:
        print(json.dumps(out, indent=1))
        return 0
    print(f"# repomap bench — {root}\n")
    print(f"{len(idx['files'])} files · {idx['_stats']['symbols']} symbols · "
          f"{len(symbols)} sampled symbols · index {cold:.2f}s cold / {warm:.2f}s warm\n")
    def table(condition):
        which = {"named": "task mentions the identifier (symbol sample)",
                 "graph": "no mention, symbol sample (big files are over-represented)",
                 "fileuniform": "no mention, file-uniform sample (which files the map picks)"}[condition]
        print(f"## {which}\n")
        print("| ranking | " + " | ".join(f"sym@{b}" for b in budgets) + " | " +
              " | ".join(f"file@{b}" for b in budgets) + " | mean file rank@1000 |")
        print("|" + "---|" * (1 + 2 * len(budgets) + 1))
        for ranker in ("repomap", "path", "size", "ident"):
            by = {r["budget"]: r for r in rows
                  if r["ranking"] == ranker and r["condition"] == condition}
            cells = [f"{by[b]['sym']*100:.0f}%" for b in budgets] + \
                    [f"{by[b]['file']*100:.0f}%" for b in budgets] + \
                    [f"{by[budgets[-1]]['rank']:.1f}"]
            print(f"| {ranker} | " + " | ".join(cells) + " |")
        print()

    table("named")
    table("graph")
    table("fileuniform")
    shown, total, files, nfiles = cov[1000]
    print(f"unconditioned coverage at 1000 tok: {shown}/{total} symbols "
          f"({shown/total*100:.0f}%), {files}/{nfiles} files. "
          "grep still wins for a known name (one call, ~50 tokens); this measures ranking "
          "when the name is unknown or ambiguous, and structure when reading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
