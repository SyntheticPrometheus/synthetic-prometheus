#!/usr/bin/env python3
"""arxiv.py — query the arXiv API and print compact paper records.

Usage:
  arxiv.py search "query" [--max 20] [--sort relevance|submittedDate] [--since 2020] [--json]
  arxiv.py get 2401.12345 [2402.67890 ...] [--json]

The API is https://export.arxiv.org/api/query (no key, be polite: one request at a time).
Responses are cached under ~/.pi/agent/research/.arxiv-cache/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://export.arxiv.org/api/query"
CACHE = Path.home() / ".pi" / "agent" / "research" / ".arxiv-cache"
UA = "pi-agent-arxiv/1.0 (+https://github.com/SyntheticPrometheus)"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()
    cached = CACHE / f"{key}.xml"
    if cached.exists():
        return cached.read_text()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        body = r.read().decode("utf-8", "replace")
    cached.write_text(body)
    return body


def parse(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall("a:entry", NS):
        def t(tag: str) -> str:
            x = e.find(tag, NS)
            return (x.text or "").strip() if x is not None else ""

        title = re.sub(r"\s+", " ", t("a:title"))
        abstract = re.sub(r"\s+", " ", t("a:summary"))
        authors = [a.findtext("a:name", default="", namespaces=NS) for a in e.findall("a:author", NS)]
        cats = [c.get("term", "") for c in e.findall("a:category", NS)]
        out.append({
            "id": t("a:id").rsplit("/", 1)[-1],
            "title": title,
            "published": t("a:published")[:10],
            "authors": [a for a in authors if a],
            "categories": cats,
            "abstract": abstract,
            "doi": t("arxiv:doi"),
            "comment": t("arxiv:comment"),
        })
    return out


def search(args) -> list[dict]:
    q = args.query
    if not args.raw:
        q = f'all:"{q}"' if " " in q else f"all:{q}"
    params = {
        "search_query": q,
        "start": 0,
        "max_results": args.max,
        "sortBy": args.sort,
        "sortOrder": "descending",
    }
    papers = parse(fetch(API + "?" + urllib.parse.urlencode(params)))
    if args.since:
        papers = [p for p in papers if p["published"][:4] >= str(args.since)]
    return papers


def get(ids: list[str]) -> list[dict]:
    params = {"id_list": ",".join(ids), "max_results": len(ids)}
    return parse(fetch(API + "?" + urllib.parse.urlencode(params)))


def show(papers: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(papers, indent=2, ensure_ascii=False))
        return
    for p in papers:
        print(f"## {p['title']}")
        print(f"   {p['id']}  ({p['published']})  {', '.join(p['categories'][:3])}")
        if p["authors"]:
            more = " et al." if len(p["authors"]) > 6 else ""
            print(f"   authors: {', '.join(p['authors'][:6])}{more}")
        if p["doi"]:
            print(f"   doi: {p['doi']}")
        if p["comment"]:
            print(f"   comment: {p['comment']}")
        print(f"   {p['abstract'][:1400]}{'…' if len(p['abstract']) > 1400 else ''}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--max", type=int, default=20)
    s.add_argument("--sort", choices=["relevance", "submittedDate", "lastUpdatedDate"], default="relevance")
    s.add_argument("--since", type=int, help="only papers published in this year or later")
    s.add_argument("--raw", action="store_true", help="pass the query as raw arXiv syntax")
    s.add_argument("--json", action="store_true")
    g = sub.add_parser("get")
    g.add_argument("ids", nargs="+")
    g.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        papers = search(args) if args.cmd == "search" else get(args.ids)
    except Exception as e:
        print(f"arxiv.py: {e}", file=sys.stderr)
        return 2
    if not papers:
        print("arxiv.py: no results", file=sys.stderr)
        return 1
    show(papers, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
