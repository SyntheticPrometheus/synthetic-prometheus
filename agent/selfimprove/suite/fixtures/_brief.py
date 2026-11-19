#!/usr/bin/env python3
"""authored-brief — shared generator for the "authored output under many simultaneous
constraints" task class (cycle 16 hypothesis).

Why this exists: every input-heavy class (bigger logs, deeper chains, more prose) saturated at
1.0 because the base arm scripts the fold. This class cannot be folded by a script: the arm must
AUTHOR prose that satisfies ~20 machine-checkable rules at once (word caps, banned words, ticket
and component cross-references, heading counts, section order, cross-file self-hash), where
fixing one rule tends to break another. A harness that verifies its artifact rule by rule before
reporting has an edge; a one-shot arm slips somewhere.

Truth is produced here, never typed by hand: `good` is authored by this generator against the
same POLICY.md the arm reads, and `bad` is `good` with one real violation (a banned word copied
from the source summary), so selftest.py proves the judge can both pass and fail.

Two instances share the class (release-brief, upgrade-brief) because gate.py counts *tasks*, and
min_delta is 2: one failing task can never move the delta.

Judge fairness note: the first measurement failed the base arm on `version: "4.2"` versus
`version: 4.2`. YAML quoting is the same string, so that was a judge defect, not an arm failure;
frontmatter values are now unquoted before comparison.
"""
import hashlib
import json
import random
import re
import sys

BANNED = ["simple", "minor", "just", "obviously", "quick", "trivial", "should",
          "several", "various", "ensure", "utilize"]
SWAP = {"simple": "small", "minor": "low-risk", "just": "only", "obviously": "clearly",
        "quick": "fast", "trivial": "small", "should": "must", "several": "many",
        "various": "mixed", "ensure": "keep", "utilize": "use"}
KINDS = ["feature", "fix", "perf", "security"]

# every template is <= 70 chars and 9..14 words, so a cleaned bullet stays inside 8..24 words and
# under the 100-char line limit; several carry a banned word the arm must not copy verbatim.
TEMPLATES = [
    "Adds a simple retry path for uploads that time out during peak traffic",
    "Fixes a minor race between session refresh and logout in the auth handler",
    "Removes a quick check that rejected valid keys containing a dash",
    "Improves query planning for billing reports so large accounts load faster",
    "Documents the three steps for rotating signing keys without downtime",
    "Adds just one index to speed up search for very old archived items",
    "Fixes the obviously wrong default for the search result page size",
    "Drops a trivial dependency that pulled in a second copy of the parser",
    "Adds audit logging for key rotation and invalidates stale tokens on change",
    "Reduces memory use in the billing exporter by batching invoice rows",
    "Aligns error messages with the public API style guide and adds examples",
    "Caches the auth discovery document for a short window to cut overhead",
    "Reports the search index lag as a metric so slow rebuilds are visible",
    "Adds a billing invoice endpoint that pages results for large accounts",
    "Rejects uploads whose declared type disagrees with the decoded payload",
]

POLICY = """# Release brief policy

The release brief is judged rule by rule. One violated rule fails the task.

## Inputs

`changes.csv` has one row per change: `id,component,kind,breaking,notable,ticket,summary`.

## What is included

- Include exactly the changes whose `notable` is `yes`; nothing else.
- Every change with `breaking=yes` is notable (the data already follows this).
- Group the included changes under `## <component> (<n>)` headings, where `<n>` is the number of
  bullets in that section. One heading per component that has at least one included change,
  alphabetical order. Do not add headings for components with no included changes.
- Within a section, order bullets by change id, ascending.

## RELEASE_NOTES.md

- Frontmatter delimited by `---` lines, exactly these keys in this order:
  `version`, `notable_count`, `breaking_count`, `components`, `notes_sha256`.
  `components` is a comma+space separated, alphabetically sorted list of the section components.
  `notes_sha256` is the lowercase hex SHA-256 of the body (everything after the closing `---`
  line, byte for byte, including the trailing newline).
- The first body line is exactly `# Release <version>`.
- The second body line is exactly:

  `{summary}`
- Each included change is one bullet shaped `- [<id>] (<ticket>) <kind>: <text>`, where `<ticket>`
  and `<kind>` are the change's ticket and kind from `changes.csv`. The text is 8 to 24 words.
- No bullet text may contain any of these words (whole word, case-insensitive):
  simple, minor, just, obviously, quick, trivial, should, several, various, ensure, utilize.
  The summaries in `changes.csv` contain some of them; paraphrase, do not copy.
- No line may exceed 120 characters.
- The body is {minw} to {maxw} words.
- If `breaking_count` is greater than zero, after the component sections add a final heading
  `## Upgrade notes` with exactly one bullet per breaking change, in id order, shaped
  `- [<id>] action required in <component>: <text>`, 8 to 24 words, obeying the same word ban.

## release.json

A JSON object with exactly these keys:

- `version`: the same string as the frontmatter.
- `notable_count`: number of included changes.
- `breaking_count`: number of breaking changes among the included changes.
- `components`: the same sorted list as the frontmatter.
- `notes_sha256`: the same hash as the frontmatter.

## Finish

Write both files, then re-read them and check every rule above before you report.
"""

VERIFY = r'''import csv, hashlib, json, re, sys
from pathlib import Path

def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

rows = list(csv.DictReader(open("changes.csv")))
notable = [r for r in rows if r["notable"] == "yes"]
breaking = [r for r in notable if r["breaking"] == "yes"]
comp = {r["id"]: r["component"] for r in rows}
ticket = {r["id"]: r["ticket"] for r in rows}
kind = {r["id"]: r["kind"] for r in rows}
want_ids = [r["id"] for r in notable]
want_comps = sorted({r["component"] for r in notable})
want_seq = [i for c in want_comps
            for i in sorted(r["id"] for r in notable if r["component"] == c)]
want_break = [r["id"] for r in breaking]
truth = json.load(open("_truth.json"))
version, minw, maxw = truth["version"], truth["minw"], truth["maxw"]

rn = Path("RELEASE_NOTES.md")
if not rn.is_file():
    fail("RELEASE_NOTES.md is missing")
raw = rn.read_bytes()
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    fail("RELEASE_NOTES.md is not UTF-8")
if not text.startswith("---\n"):
    fail("RELEASE_NOTES.md must start with a --- frontmatter line")
end = text.find("\n---\n", 4)
if end < 0:
    fail("frontmatter closing --- line is missing")
front, body = text[4:end], text[end + 5:]
fm = {}
for line in front.splitlines():
    if not line.strip():
        continue
    if ":" not in line:
        fail(f"frontmatter line is not key: value: {line!r}")
    k, v = line.split(":", 1)
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]            # YAML quoting does not change the string
    fm[k.strip()] = v
for k in ("version", "notable_count", "breaking_count", "components", "notes_sha256"):
    if k not in fm:
        fail(f"frontmatter is missing {k}")
if fm["version"] != version:
    fail(f"version is {fm['version']!r}, expected {version!r}")
if fm["notable_count"] != str(len(want_ids)):
    fail(f"notable_count is {fm['notable_count']!r}, expected {len(want_ids)}")
if fm["breaking_count"] != str(len(want_break)):
    fail(f"breaking_count is {fm['breaking_count']!r}, expected {len(want_break)}")
if fm["components"] != ", ".join(want_comps):
    fail(f"components is {fm['components']!r}, expected {', '.join(want_comps)!r}")

banned = re.compile(r"\b(" + "|".join(["simple", "minor", "just", "obviously", "quick",
                                       "trivial", "should", "several", "various", "ensure",
                                       "utilize"]) + r")\b", re.I)
m = banned.search(text)
if m:
    fail(f"banned word used: {m.group(0)!r}")

lines = body.splitlines()
if not lines or lines[0].strip() != f"# Release {version}":
    fail(f"first body line must be '# Release {version}'")
kinds = sorted({r["kind"] for r in notable})
kind_part = ", ".join(f"{k} {sum(1 for r in notable if r['kind'] == k)}" for k in kinds)
summary_line = (f"Summary: {len(want_ids)} notable changes, {len(want_break)} breaking, "
                f"across {len(want_comps)} components; kinds: {kind_part}")
if len(lines) < 2 or lines[1].strip() != summary_line:
    fail(f"second body line must be {summary_line!r}")
for ln in text.splitlines():
    if len(ln) > 120:
        fail(f"line over 120 chars: {ln[:60]!r}... ({len(ln)})")
words = body.split()
if not (minw <= len(words) <= maxw):
    fail(f"body is {len(words)} words, expected {minw}..{maxw}")

bullet_re = re.compile(r"^- \[(C-\d{3})\] \((OPS-\d{4})\) ([a-z]+): (.+)$")
sections, order, cur = {}, [], None
for ln in lines[2:]:
    if ln.startswith("## "):
        mm = re.match(r"^## (.+?) \((\d+)\)$", ln)
        name = mm.group(1) if mm else ln[3:].strip()
        cur = name
        if cur in sections:
            fail(f"section {cur!r} appears twice")
        sections[cur] = {"declared": int(mm.group(2)) if mm and name != "Upgrade notes" else None,
                         "bullets": []}
        order.append(cur)
    elif ln.startswith("- "):
        if cur is None:
            fail("bullet outside a section")
        if cur == "Upgrade notes":
            mm = re.match(r"^- \[(C-\d{3})\] (.+)$", ln)
            if not mm:
                fail(f"upgrade bullet is not '- [C-NNN] text': {ln[:60]!r}")
            sections[cur]["bullets"].append(("up", mm.group(1), mm.group(2)))
        else:
            mm = bullet_re.match(ln)
            if not mm:
                fail(f"bullet is not '- [C-NNN] (OPS-NNNN) kind: text': {ln[:60]!r}")
            sections[cur]["bullets"].append(("c", mm.group(1), mm.group(2), mm.group(3),
                                             mm.group(4)))
    elif ln.strip():
        fail(f"unexpected body line: {ln[:60]!r}")

if "Upgrade notes" in sections:
    up = sections.pop("Upgrade notes")["bullets"]
    order.remove("Upgrade notes")
else:
    up = []
if order != want_comps:
    fail(f"component headings are {order}, expected {want_comps}")
seen = []
for c in order:
    got = sections[c]["bullets"]
    if sections[c]["declared"] != len(got):
        fail(f"section {c!r} declares {sections[c]['declared']} bullets but has {len(got)}")
    for _, cid, tk, kd, txt in got:
        if comp.get(cid) != c:
            fail(f"{cid} is listed under {c!r} but belongs to {comp.get(cid)!r}")
        if tk != ticket[cid]:
            fail(f"{cid} ticket is {tk!r}, expected {ticket[cid]!r}")
        if kd != kind[cid]:
            fail(f"{cid} kind is {kd!r}, expected {kind[cid]!r}")
        n = len(txt.split())
        if not (8 <= n <= 24):
            fail(f"{cid} text is {n} words, expected 8..24")
        seen.append(cid)
if seen != want_seq:
    fail(f"included ids are {seen}, expected {want_seq}")
if want_break:
    if [cid for _, cid, _ in up] != want_break:
        fail(f"upgrade notes ids are {[c for _, c, _ in up]}, expected {want_break}")
    for _, cid, txt in up:
        pref = f"action required in {comp[cid]}: "
        if not txt.startswith(pref):
            fail(f"{cid} upgrade note must start with {pref!r}")
        n = len(txt[len(pref):].split())
        if not (8 <= n <= 24):
            fail(f"{cid} upgrade note is {n} words, expected 8..24")
elif up:
    fail("upgrade notes present but breaking_count is 0")

body_bytes = body.encode()
h = hashlib.sha256(body_bytes).hexdigest()
if fm["notes_sha256"] != h:
    fail(f"notes_sha256 is {fm['notes_sha256']!r}, expected {h}")

j = Path("release.json")
if not j.is_file():
    fail("release.json is missing")
try:
    d = json.loads(j.read_text())
except Exception as e:
    fail(f"release.json is not JSON: {e}")
for k in ("version", "notable_count", "breaking_count", "components", "notes_sha256"):
    if k not in d:
        fail(f"release.json is missing {k}")
if d["version"] != version:
    fail("release.json version disagrees with the frontmatter")
if d["notable_count"] != len(want_ids):
    fail("release.json notable_count is wrong")
if d["breaking_count"] != len(want_break):
    fail("release.json breaking_count is wrong")
if d["components"] != want_comps:
    fail(f"release.json components are {d['components']!r}, expected {want_comps!r}")
if d["notes_sha256"] != h:
    fail("release.json notes_sha256 disagrees with the file")
sys.exit(0)
'''


def clean(s):
    out = []
    for w in s.split():
        bare = w.strip(".,;:!?()[]").lower()
        out.append(SWAP.get(bare, w) if bare in SWAP else w)
    return " ".join(out)


def build(seed, version, components, n, title):
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        c = components[(i - 1) % len(components)]
        kind = rng.choice(KINDS)
        # the last component is docs-only: no notable rows, so it must be dropped from the brief
        notable = "no" if c == components[-1] else ("yes" if rng.random() < 0.5 else "no")
        rows.append({"id": f"C-{i:03d}", "component": c, "kind": kind,
                     "breaking": "no", "notable": notable,
                     "ticket": f"OPS-{rng.randint(1000, 9999)}",
                     "summary": rng.choice(TEMPLATES)})
    for c in components[:-1]:
        if not any(r["component"] == c and r["notable"] == "yes" for r in rows):
            pick = next(r for r in rows if r["component"] == c)
            pick["notable"] = "yes"
    picks = [r for r in rows if r["notable"] == "yes"]
    if not any(banned_word(r["summary"]) for r in picks):
        picks[0]["summary"] = TEMPLATES[0]      # keep the bad-answer mutation possible
    for r in rng.sample(picks, max(1, len(picks) // 3)):
        r["breaking"] = "yes"
    notable = [r for r in rows if r["notable"] == "yes"]
    breaking = [r for r in notable if r["breaking"] == "yes"]

    csv_lines = ["id,component,kind,breaking,notable,ticket,summary"]
    for r in rows:
        csv_lines.append(",".join([r["id"], r["component"], r["kind"], r["breaking"],
                                   r["notable"], r["ticket"], r["summary"]]))
    changes_csv = "\n".join(csv_lines) + "\n"

    comps = sorted({r["component"] for r in notable})
    kinds = sorted({r["kind"] for r in notable})
    kind_part = ", ".join(f"{k} {sum(1 for r in notable if r['kind'] == k)}" for k in kinds)
    # no trailing period: the exact string is shown in POLICY, so punctuation is never a trap
    summary = (f"Summary: {len(notable)} notable changes, {len(breaking)} breaking, "
               f"across {len(comps)} components; kinds: {kind_part}")
    body = f"# Release {version}\n" + summary + "\n"
    for c in comps:
        in_c = [r for r in notable if r["component"] == c]
        body += f"\n## {c} ({len(in_c)})\n\n"
        for r in in_c:
            body += f"- [{r['id']}] ({r['ticket']}) {r['kind']}: {clean(r['summary'])}\n"
    if breaking:
        body += "\n## Upgrade notes\n\n"
        for r in breaking:
            body += (f"- [{r['id']}] action required in {r['component']}: "
                     f"{clean(r['summary'])}\n")
    # the word band is derived from the authored body (~5% either side), then published in
    # POLICY.md: a stated, countable rule, not a hidden target.
    nw = len(body.split())
    minw, maxw = int(nw * 0.95), int(nw * 1.05) + 1
    # POLICY shows the literal line the judge expects, rendered by this same expression: the
    # first measurement failed a correct answer on a trailing period that the prose template
    # never mentioned (judge-defect class, 2026-11-14). Selftest pins the two together.
    policy = POLICY.format(minw=minw, maxw=maxw, summary=summary)
    h = hashlib.sha256(body.encode()).hexdigest()
    front = ("---\n"
             f"version: {version}\n"
             f"notable_count: {len(notable)}\n"
             f"breaking_count: {len(breaking)}\n"
             f"components: {', '.join(comps)}\n"
             f"notes_sha256: {h}\n"
             "---\n")
    notes = front + body
    rel = {"version": version, "notable_count": len(notable),
           "breaking_count": len(breaking), "components": comps, "notes_sha256": h}

    bad_row = next(r for r in notable if banned_word(r["summary"]))
    bad_notes = notes.replace(
        f"- [{bad_row['id']}] ({bad_row['ticket']}) {bad_row['kind']}: {clean(bad_row['summary'])}",
        f"- [{bad_row['id']}] ({bad_row['ticket']}) {bad_row['kind']}: {bad_row['summary']}")

    tolerant = notes
    for k in ("version", "notable_count", "breaking_count", "components", "notes_sha256"):
        tolerant = tolerant.replace(f"\n{k}: ", f'\n{k}: "', 1)
        # close the quote at the next newline for that key only
        head, _, tail = tolerant.partition(f'\n{k}: "')
        line, nl, rest = tail.partition("\n")
        tolerant = head + f'\n{k}: "' + line + '"' + nl + rest
    return {
        "files": {"changes.csv": changes_csv, "POLICY.md": policy},
        "verify_files": {"_verify.py": VERIFY,
                         "_truth.json": json.dumps({"version": version, "title": title,
                                                    "minw": minw, "maxw": maxw})},
        "verify": "python3 _verify.py",
        "good": {"RELEASE_NOTES.md": notes, "release.json": json.dumps(rel, indent=1) + "\n"},
        "tolerant": {"RELEASE_NOTES.md": tolerant,
                     "release.json": json.dumps(rel, indent=1) + "\n"},
        "bad": {"RELEASE_NOTES.md": bad_notes, "release.json": json.dumps(rel, indent=1) + "\n"},
    }


def banned_word(s):
    return any(re.search(rf"\b{w}\b", s, re.I) for w in BANNED)


def main(argv):
    seed, version, title = int(argv[1]), argv[2], argv[3]
    components = argv[4].split(",")
    n = int(argv[5])
    print(json.dumps(build(seed, version, components, n, title)))
