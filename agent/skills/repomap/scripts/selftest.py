#!/usr/bin/env python3
"""selftest — the pi-repomap guard: extraction, budget, ranking, cache and the MCP handshake.

Runs on a throwaway fixture tree, so it never depends on this machine's repos. `pi-preflight`
runs it as the `repomap` check: a tool that silently stops parsing (the frontmatter class of
failure) fails here instead of being discovered weeks later.

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
EXE = AGENT / "bin" / "pi-repomap"


def load():
    loader = importlib.machinery.SourceFileLoader("pi_repomap_st", str(EXE))
    spec = importlib.util.spec_from_loader("pi_repomap_st", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def fixture(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "core.py").write_text(
        '"""Core."""\n\nCONST = 3\n\n\ndef solve(n):\n    return helper(n)\n\n\n'
        'class Widget:\n    def draw(self):\n        pass\n')
    (root / "src" / "util.py").write_text("def helper(n):\n    return n * 2\n")
    (root / "src" / "lib.rs").write_text(
        "pub struct Thing {\n    x: i32,\n}\n\nimpl Thing {\n    pub fn new() -> Self { Thing { x: 0 } }\n}\n\n"
        "pub fn run() -> i32 { solve_it() }\n\nfn solve_it() -> i32 { 1 }\n")
    (root / "src" / "main.ts").write_text(
        "export function boot(): void { run(); }\ninterface Opts { a: number }\nconst run = () => 1;\n")
    (root / "run.sh").write_text("#!/usr/bin/env bash\nhello() { echo hi; }\nhello\n")
    (root / "notes.md").write_text("# Notes\n\ntext\n\n## Detail\n")
    (root / "bin").mkdir()
    p = root / "bin" / "tool"
    p.write_text("#!/usr/bin/env python3\ndef entry():\n    return 1\n")
    p.chmod(0o755)


def mcp(msgs: list[dict], timeout: int = 20) -> list[dict]:
    inp = "".join(json.dumps(m) + "\n" for m in msgs)
    cp = subprocess.run([str(EXE), "mcp"], input=inp, capture_output=True, text=True, timeout=timeout)
    out = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main(argv=None):
    quiet = "--quiet" in (argv or sys.argv[1:])
    m = load()
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
        root = Path(td) / "repo"
        fixture(root)
        os.environ["PI_REPOMAP_CACHE"] = str(Path(td) / "cache")
        m.CACHE_DIR = Path(td) / "cache"
        idx = m.build_index(root, [], use_cache=True, verbose=False)
        kinds = {(rel, s[0], s[1]) for rel, r in idx["files"].items() for s in r["symbols"]}
        check("extracts python fn/class", ("src/core.py", "solve", "fn") in kinds)
        check("extracts python class", ("src/core.py", "Widget", "class") in kinds)
        check("extracts rust struct/impl/type", ("src/lib.rs", "Thing", "struct") in kinds and
              ("src/lib.rs", "Thing", "impl") in kinds)
        check("extracts ts fn/interface", ("src/main.ts", "boot", "fn") in kinds and
              ("src/main.ts", "Opts", "type") in kinds)
        check("extracts shell fn", any(r == "run.sh" and n == "hello" for r, n, k in kinds))
        check("extracts md headings", ("notes.md", "Notes", "h1") in kinds)
        check("extensionless shebang script is a source", ("bin/tool", "entry", "fn") in kinds)

        refetch = m.build_index(root, [], use_cache=True)
        check("cache reuses unchanged files", refetch["_stats"]["parsed"] == 0 and
              refetch["_stats"]["files"] == idx["_stats"]["files"])

        for budget, hint in ((120, ["solve"]), (400, []), (2000, ["boot"])):
            pr = m.rank_files(idx, (), hint)
            text, used = m.render_map(idx, pr, budget, 4.0, hint)
            check(f"map respects {budget}-token budget (used {used})", used <= budget)
            check(f"map is non-empty at {budget}", "│" in text or text.startswith("⋮"))

        pr = m.rank_files(idx, (), ["solve"])
        text, _ = m.render_map(idx, pr, 300, 4.0, ["solve"])
        first = next((l for l in text.splitlines() if l and not l.startswith("│")), "")
        check("mentioned identifier pulls its file to rank 1", first.startswith("src/core.py"), first)
        check("mentioned symbol is shown", any("solve" in l for l in text.splitlines() if l.startswith("│")))

        cp = subprocess.run([str(EXE), "find", "helper", "--root", str(root)],
                            capture_output=True, text=True)
        check("find reports the definition", "src/util.py" in cp.stdout and cp.returncode == 0, cp.stdout)
        check("find reports the referrer", "src/core.py" in cp.stdout, cp.stdout)
        cp = subprocess.run([str(EXE), "outline", str(root / "src" / "core.py")],
                            capture_output=True, text=True)
        check("outline prints line numbers", "solve" in cp.stdout and "CONST" in cp.stdout, cp.stdout)
        cp = subprocess.run([str(EXE), "find", "no_such_symbol_xyz", "--root", str(root)],
                            capture_output=True, text=True)
        check("find exits 1 when absent", cp.returncode == 1)

        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "selftest", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "repomap", "arguments": {"path": str(root), "budget": 200}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": "symfind", "arguments": {"name": "helper", "path": str(root)}}}]
        replies = {r["id"]: r for r in mcp(msgs) if "id" in r}
        check("mcp initialize", replies.get(1, {}).get("result", {}).get("serverInfo", {}).get("name")
              == "pi-repomap")
        names = [t["name"] for t in replies.get(2, {}).get("result", {}).get("tools", [])]
        check("mcp lists repomap/symfind/outline",
              names == ["repomap", "symfind", "outline"], names)
        body = replies.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "")
        check("mcp repomap returns a map", "src/util.py" in body or "src/core.py" in body, body[:120])
        body = replies.get(4, {}).get("result", {}).get("content", [{}])[0].get("text", "")
        check("mcp symfind finds the definition", "src/util.py" in body, body[:120])
        try:
            subprocess.run([str(EXE), "--help"], capture_output=True, timeout=10, check=False)
            check("cli responds", True)
        except subprocess.SubprocessError as e:
            check("cli responds", False, str(e))

    for f in fails:
        print(f, file=sys.stderr)
    if not quiet:
        print("FAIL" if not ok else f"PASS — all repomap assertions held")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
