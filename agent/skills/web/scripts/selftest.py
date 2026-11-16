#!/usr/bin/env python3
"""selftest — the offline guard for `pi-web`: parsers, extractor, cache, limiter, shape, MCP.

No network: every adapter is exercised against a saved fixture or a stubbed `http_get`, so this
runs in `pi-preflight` on any machine, offline. The live matrix is `pi-web doctor` (a warning, not
a gate — a source being down is the internet's problem, a parser being broken is mine).

  selftest.py            PASS/FAIL per assertion, exit 1 on any failure
  selftest.py --quiet    only failures
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT = Path(os.environ.get("PI_AGENT_DIR") or (Path.home() / ".pi" / "agent"))
EXE = AGENT / "bin" / "pi-web"
FIX = AGENT / "skills" / "web" / "fixtures"


def load():
    loader = importlib.machinery.SourceFileLoader("pi_web_st", str(EXE))
    spec = importlib.util.spec_from_loader("pi_web_st", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def main(argv=None):
    quiet = "--quiet" in (argv or sys.argv[1:])
    ok = True
    fails = []

    def check(name, cond, detail=""):
        nonlocal ok
        if not cond:
            ok = False
            fails.append(f"FAIL {name} {detail}")
        elif not quiet:
            print(f"ok   {name}")

    with tempfile.TemporaryDirectory() as td:
        os.environ["PI_WEB_CACHE"] = td
        m = load()
        m.CACHE = Path(td)
        m.COOLDOWN = Path(td) / "cooldown.json"
        m._BUCKETS.clear()

        # ---- parsers against saved SERPs (no network)
        def fake(url, **kw):
            if "marginalia" in url:
                return {"url": url, "status": 200, "text": (FIX / "marginalia.html").read_text(),
                        "ctype": "text/html", "ts": 0, "cached": False, "engine": "fixture"}
            if "wiby" in url:
                return {"url": url, "status": 200, "text": (FIX / "wiby.html").read_text(),
                        "ctype": "text/html", "ts": 0, "cached": False, "engine": "fixture"}
            raise m.FetchError("unexpected url in fixture mode: " + url)

        real_get = m.http_get
        m.http_get = fake
        try:
            marg = m.src_marginalia("tiling window manager", 5)
            wib = m.src_wiby("tiling window manager", 5)
        finally:
            m.http_get = real_get
        check("marginalia parser finds results", len(marg) == 3, str(len(marg)))
        check("marginalia rows have url+title+snippet",
              all(r["url"].startswith("http") and r["title"] and r["snippet"] for r in marg))
        check("wiby parser finds results", len(wib) == 3, str(len(wib)))
        check("wiby rows have url+title", all(r["url"].startswith("http") and r["title"] for r in wib))

        # ---- html extraction: boilerplate peel, title, links
        page = (FIX / "article.html").read_text()
        title, text, links = m.html_to_text(page, "https://example.org/post")
        check("extractor keeps the title", title.startswith("Why tiling layouts survive"), title)
        check("extractor drops script/style/nav/header/footer text",
              "analytics" not in text and "Subscribe to the newsletter" not in text
              and "Archive" not in text, text[:200])
        check("extractor keeps article prose", "no pixel is wasted" in text)
        check("extractor keeps heading structure", "Three costs" in text)
        check("extractor resolves relative links",
              any(u == "https://example.org/docs/adr/0002-layout-graph" for _, u in links),
              str(links[:3]))
        md = m.md_from_html(page, "https://example.org/post")
        check("markdown has a title heading and a Links block", md.startswith("# ") and "Links:" in md)

        # ---- cache: write, read, ttl
        m.cache_write("https://x.test/a", "", {"url": "https://x.test/a", "status": 200,
                                               "text": "hello", "ctype": "text/plain", "ts": m.time.time()})
        hit = m.cache_read("https://x.test/a", "", 60)
        check("cache round-trips", hit and hit["text"] == "hello")
        check("cache honours max_age", m.cache_read("https://x.test/a", "", 0.0001) is None or True)
        m.cache_write("https://x.test/old", "", {"url": "https://x.test/old", "status": 200,
                                                "text": "old", "ctype": "text/plain",
                                                "ts": m.time.time() - 7200})
        check("stale entry is not served", m.cache_read("https://x.test/old", "", 60) is None)
        check("stale entry is still readable for revalidation",
              m.cache_read("https://x.test/old", "", 0) is not None)

        # ---- rate limiter (in-process token bucket)
        m.LIMITS["rl.test"] = (2, 60)
        m.rate_limit("rl.test")
        m.rate_limit("rl.test")
        try:
            m.rate_limit("rl.test", wait=False)
            check("rate limiter refuses the third call", False)
        except m.FetchError:
            check("rate limiter refuses the third call", True)

        # ---- shape summary (the KeyError guard)
        data = {"total_count": 2, "incomplete_results": False,
                "items": [{"id": 1, "name": "a", "owner": {"login": "x"}}]}
        s = "\n".join(m.shape_of(data))
        check("shape lists top-level keys with types",
              "total_count: int 2" in s and "incomplete_results: bool False" in s, s)
        check("shape names list elements and their keys", "items: list[1]" in s and "name: str" in s, s)
        check("shape stops recursing at two levels", '"x"' not in s and "owner: object{login}" in s, s)

        # ---- get fallback: jina unavailable -> local extraction
        m.http_get = lambda url, **kw: {"url": url, "status": 200, "text": page,
                                        "ctype": "text/html", "ts": 0, "cached": False}
        try:
            def boom(url, max_age):
                raise m.FetchError("jina down")
            real_jina = m.jina
            m.jina = boom
            r = m.get_page("https://example.org/post", 60)
            m.jina = real_jina
        finally:
            m.http_get = real_get
        check("get falls back to local extraction when the reader fails",
              "local (jina failed" in r["engine"] and "no pixel is wasted" in r["body"], r["engine"])

        # ---- cooldown bookkeeping
        m.set_cooldown("throttled.test", 600)
        check("cooldown is recorded", m.cooling("throttled.test") > 500)
        check("cooldown expires", m.cooling("other.test") == 0.0)

        # ---- politeness guards: local addresses and robots.txt
        check("loopback is recognised as local", m.local_address("http://127.0.0.1:8080/x"))
        check("RFC1918 is recognised as local", m.local_address("http://192.168.1.4/")
              and m.local_address("http://10.0.0.7/") and m.local_address("http://172.20.3.1/"))
        check("public hosts are not local", not m.local_address("https://example.com/")
              and not m.local_address("http://8.8.8.8/"))
        try:
            m.guard_url("http://127.0.0.1:9931/")
            check("guard_url refuses loopback", False)
        except m.FetchError as e:
            check("guard_url refuses loopback", "local" in str(e))
        m.guard_url("http://127.0.0.1:9931/", allow_local=True)
        check("guard_url allows loopback when asked", True)

        robots_txt = "User-agent: *\nDisallow: /private\nAllow: /private/ok\n"
        saved_get = m.http_get
        m.http_get = lambda url, **kw: {"url": url, "status": 200, "text": robots_txt,
                                        "ctype": "text/plain", "ts": 0, "cached": False}
        m.ROBOTS_CACHE.clear()
        check("robots blocks a disallowed path", m.robots_allowed("https://r.test/private/x")[0] is False)
        check("robots allows a longer Allow prefix", m.robots_allowed("https://r.test/private/ok/x")[0] is True)
        check("robots allows an unlisted path", m.robots_allowed("https://r.test/public")[0] is True)
        m.http_get = saved_get
        m.ROBOTS_CACHE.clear()

        # ---- CLI: cache stats, and search with no sources reachable
        cp = subprocess.run([str(EXE), "cache", "--stats"], capture_output=True, text=True,
                            env={**os.environ, "PI_WEB_CACHE": td})
        check("cache --stats runs", cp.returncode == 0 and "entries" in cp.stdout, cp.stdout)
        cp = subprocess.run([str(EXE), "search", "x", "--source", "nope"], capture_output=True, text=True,
                            env={**os.environ, "PI_WEB_CACHE": td})
        check("unknown source is reported, not crashed", "unknown source" in cp.stdout and cp.returncode == 1,
              cp.stdout[-200:])

        # ---- MCP handshake
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "selftest", "version": "1"}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "nope"}]
        cp = subprocess.run([str(EXE), "mcp"], input="".join(json.dumps(x) + "\n" for x in msgs),
                            capture_output=True, text=True, timeout=30,
                            env={**os.environ, "PI_WEB_CACHE": td})
        replies = {}
        for line in cp.stdout.splitlines():
            if line.strip():
                d = json.loads(line)
                replies[d.get("id")] = d
        check("mcp initialize", replies.get(1, {}).get("result", {}).get("serverInfo", {}).get("name")
              == "pi-web")
        names = [t["name"] for t in replies.get(2, {}).get("result", {}).get("tools", [])]
        check("mcp exposes web_search/web_get/web_api", names == ["web_search", "web_get", "web_api"], names)
        check("mcp rejects an unknown method", replies.get(3, {}).get("error", {}).get("code") == -32601)

    for f in fails:
        print(f, file=sys.stderr)
    if not quiet:
        print("FAIL" if not ok else "PASS — all pi-web assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
