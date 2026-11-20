#!/usr/bin/env python3
"""mem — hybrid agent memory store (SQLite: BM25 + entity graph PPR + decay), zero deps.

Design lineage: MemGPT tiers, HippoRAG/HippoRAG2 (phrase graph + personalized PageRank),
Zep/Graphiti (bi-temporal supersession), RAPTOR/TiMem (hierarchical digests, additive only),
Raw-RAG finding (never destroy raw text — digests link, they do not replace),
ACE (incremental structured updates instead of rewrite-in-place).

Every write is appended to journal/*.jsonl BEFORE the DB, so the DB is always rebuildable.

Commands: add brief search get core pin link supersede forget consolidate stats pdsa eval export reindex
"""
import argparse, hashlib, json, math, os, re, sqlite3, sys, time

HOME = os.environ.get("HOME", "$HOME")
FUND = os.path.join(HOME, ".pi", "agent", "memory")   # code assets: venv, model
BASE = os.environ.get("MEM_HOME", FUND)               # data: db, journal, eval
DBP = os.path.join(BASE, "memory.db")
JRN = os.path.join(BASE, "journal")
EVALP = os.path.join(BASE, "eval.json")

VENV_PY = os.path.join(FUND, "venv", "bin", "python")
MODEL_ONNX = os.path.join(FUND, "model", "model.onnx")
TOK_JSON = os.path.join(FUND, "model", "tokenizer.json")
EMB_MODEL = "minilm-l6-quint8-avx2"

TAU = {"fact": 90.0, "pref": 60.0, "decision": 120.0, "lesson": 180.0, "task": 14.0,
       "note": 30.0, "source": 120.0, "digest": 180.0, "playbook": 240.0}
KINDS = set(TAU)

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories(
  id INTEGER PRIMARY KEY, uid TEXT UNIQUE, ts REAL NOT NULL,
  kind TEXT NOT NULL DEFAULT 'note', scope TEXT NOT NULL DEFAULT 'global',
  title TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
  importance REAL NOT NULL DEFAULT 0.5, confidence REAL NOT NULL DEFAULT 0.8,
  source TEXT DEFAULT '', valid_from REAL, valid_to REAL, superseded_by INTEGER,
  accesses INTEGER NOT NULL DEFAULT 0, last_access REAL, strength REAL NOT NULL DEFAULT 1.0,
  pinned INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0, checksum TEXT);
CREATE TABLE IF NOT EXISTS entities(id INTEGER PRIMARY KEY, name TEXT UNIQUE, df INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS mentions(mem_id INTEGER, ent_id INTEGER, weight REAL DEFAULT 1.0,
  PRIMARY KEY(mem_id, ent_id));
CREATE INDEX IF NOT EXISTS mentions_ent ON mentions(ent_id);
CREATE TABLE IF NOT EXISTS edges(src INTEGER, dst INTEGER, rel TEXT, weight REAL DEFAULT 1.0,
  ts REAL, PRIMARY KEY(src, dst, rel));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts REAL, kind TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS embeddings(mem_id INTEGER PRIMARY KEY, vec BLOB, model TEXT, dim INTEGER,
  checksum TEXT);
CREATE TABLE IF NOT EXISTS recalls(id INTEGER PRIMARY KEY, ts REAL, query TEXT, returned TEXT,
  used TEXT, latency_ms REAL, budget_tokens INTEGER, result_tokens INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS pdsa(id INTEGER PRIMARY KEY, cycle INTEGER, plan TEXT, do TEXT,
  study TEXT, act TEXT, metric_before REAL, metric_after REAL, status TEXT DEFAULT 'open',
  created REAL, updated REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
  title, body, tags, content='memories', content_rowid='id', tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
  INSERT INTO mem_fts(rowid,title,body,tags) VALUES(new.id,new.title,new.body,new.tags); END;
CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
  INSERT INTO mem_fts(mem_fts,rowid,title,body,tags) VALUES('delete',old.id,old.title,old.body,old.tags); END;
CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memories BEGIN
  INSERT INTO mem_fts(mem_fts,rowid,title,body,tags) VALUES('delete',old.id,old.title,old.body,old.tags);
  INSERT INTO mem_fts(rowid,title,body,tags) VALUES(new.id,new.title,new.body,new.tags); END;
"""

STOP = set("""a an the and or not but if then than that this these those of in on at to for from by with
without into over under about as is are was were be been being it its it's i you we they he she them us
our your their my me do does did done can could should would will shall may might must have has had
use used using via per each any all some more most other such no nor only own same so too very just
also there here when where which who whom what how why both etc vs versus""".split())

CUE_NEW = re.compile(r"\b(now|currently|as of|switched to|migrated to|replaced by|no longer|instead|new:)\b", re.I)
CUE_OLD = re.compile(r"\b(previously|used to|formerly|was|deprecated|older|old:)\b", re.I)


# ---------------------------------------------------------------- embeddings
def emb_ready():
    return os.path.exists(MODEL_ONNX) and os.path.exists(TOK_JSON) and os.path.exists(VENV_PY)


_EMB = {}


def embedder():
    if "sess" in _EMB:
        return _EMB["sess"], _EMB["tok"]
    from tokenizers import Tokenizer
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    so.log_severity_level = 3
    sess = ort.InferenceSession(MODEL_ONNX, so, providers=["CPUExecutionProvider"])
    tok = Tokenizer.from_file(TOK_JSON)
    tok.enable_truncation(max_length=256)
    tok.enable_padding(pad_id=0, pad_token="[PAD]")
    _EMB.update(sess=sess, tok=tok)
    return sess, tok


def embed(texts):
    import numpy as np
    sess, tok = embedder()
    encs = tok.encode_batch([re.sub(r"\s+", " ", t)[:1500] for t in texts])
    ids = np.array([e.ids for e in encs], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
    feeds = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in {i.name for i in sess.get_inputs()}:
        feeds["token_type_ids"] = np.zeros_like(ids)
    out = sess.run(None, feeds)[0]
    m = mask[..., None].astype(np.float32)
    v = (out * m).sum(1) / np.maximum(m.sum(1), 1e-6)
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    return v.astype(np.float32)


def store_emb(c, mem_id, title, body, checksum):
    if not emb_ready():
        return False
    v = embed([f"{title}. {body}"])[0]
    c.execute("INSERT OR REPLACE INTO embeddings(mem_id,vec,model,dim,checksum) VALUES(?,?,?,?,?)",
              (mem_id, v.tobytes(), EMB_MODEL, int(v.shape[0]), checksum))
    return True


_MAT = {}


def dense_rank(c, q, limit=60):
    if not emb_ready():
        return {}
    import numpy as np
    k2 = c.execute("SELECT COUNT(*) n, COALESCE(MAX(mem_id),0) m FROM embeddings").fetchone()
    ck = (k2["n"], k2["m"])
    if _MAT.get("ck") != ck:
        rows = c.execute("""SELECT e.mem_id, e.vec FROM embeddings e JOIN memories m ON m.id=e.mem_id
            WHERE m.archived=0 AND e.model=? ORDER BY e.mem_id""", (EMB_MODEL,)).fetchall()
        if not rows:
            return {}
        M = np.frombuffer(b"".join(r["vec"] for r in rows), dtype=np.float32).reshape(len(rows), -1)
        _MAT.update(ck=ck, ids=[r["mem_id"] for r in rows], M=M)
    qv = embed([q])[0]
    s = _MAT["M"] @ qv
    k = min(limit, len(s))
    top = np.argpartition(-s, k - 1)[:k]
    top = top[np.argsort(-s[top])]
    hi = float(s[top[0]]) or 1.0
    return {_MAT["ids"][i]: max(0.0, float(s[i]) / hi) for i in top if s[i] > 0.20}


# ---------------------------------------------------------------- infra
def conn():
    os.makedirs(BASE, exist_ok=True)
    os.makedirs(JRN, exist_ok=True)
    c = sqlite3.connect(DBP, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    return c


def journal(rec):
    os.makedirs(JRN, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with open(os.path.join(JRN, f"{day}.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def uid_for(title, body):
    return hashlib.sha1((title + "\x00" + body).encode()).hexdigest()[:10]


def tokens(s):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9_.\-/+]{2,}", (s or "").lower()) if w not in STOP]


def tokset(s):
    return set(tokens(s))


def jacc(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def est_tokens(s):
    return max(1, len(s) // 4)


def now():
    return time.time()


def age_days(ts):
    return max(0.0, (now() - (ts or now())) / 86400.0)


def event(c, kind, payload):
    c.execute("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)", (now(), kind, json.dumps(payload)[:4000]))


# ---------------------------------------------------------------- entities
def extract_terms(title, body, tags, limit=24):
    txt = f"{title} {body}"
    toks = tokens(txt)
    counts = {}
    for t in toks:
        counts[t] = counts.get(t, 0) + 1
    # adjacent bigrams of non-stopword tokens, kept as phrases (HippoRAG-ish phrase nodes)
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/+]{1,}", txt)
    bi = {}
    for a, b in zip(raw, raw[1:]):
        al, bl = a.lower(), b.lower()
        if al in STOP or bl in STOP or len(al) < 3 or len(bl) < 3:
            continue
        p = f"{al} {bl}"
        bi[p] = bi.get(p, 0) + 1
    out = {}
    for t, n in counts.items():
        w = 0.5 + 0.5 * min(1.0, n / 3.0)
        if t in {x.lower() for x in tags}:
            w += 0.6
        out[t] = w
    for p, n in bi.items():
        if n >= 1:
            out[p] = 0.8 + 0.2 * min(1.0, n / 2.0)
    top = sorted(out.items(), key=lambda kv: -kv[1])[:limit]
    return top


def index_terms(c, mem_id, terms):
    for name, w in terms:
        row = c.execute("SELECT id,df FROM entities WHERE name=?", (name,)).fetchone()
        if row:
            c.execute("UPDATE entities SET df=df+1 WHERE id=?", (row["id"],))
            eid = row["id"]
        else:
            eid = c.execute("INSERT INTO entities(name,df) VALUES(?,1)", (name,)).lastrowid
        c.execute("INSERT OR REPLACE INTO mentions(mem_id,ent_id,weight) VALUES(?,?,?)", (mem_id, eid, w))


# ---------------------------------------------------------------- write
def cmd_add(a, c):
    body = a.body if a.body and a.body != "-" else sys.stdin.read()
    body = body.strip()
    if not body and not a.title:
        die("nothing to add")
    title = (a.title or body.split("\n")[0])[:160]
    kind = a.kind if a.kind in KINDS else "note"
    tags = [t.strip().lower() for t in (a.tags or "").split(",") if t.strip()]
    uid = uid_for(title, body)
    dup = c.execute("SELECT id,title FROM memories WHERE uid=? OR (title=? AND body=?)", (uid, title, body)).fetchone()
    if dup and not a.force:
        print(f"dup #{dup['id']} {dup['title'][:70]}")
        return 0
    rec = dict(ts=now(), kind=kind, scope=a.scope, title=title, body=body, tags=tags,
               importance=max(0.0, min(1.0, a.importance)), confidence=a.confidence,
               source=a.source or os.environ.get("PI_SESSION_ID", "")[:12], uid=uid,
               checksum=hashlib.sha256(body.encode()).hexdigest()[:16])
    journal({"op": "add", "rec": rec})
    cur = c.execute("""INSERT INTO memories(uid,ts,kind,scope,title,body,tags,importance,confidence,
        source,valid_from,checksum,pinned) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (uid, rec["ts"], kind, rec["scope"], title, body, json.dumps(tags), rec["importance"],
                     rec["confidence"], rec["source"], rec["ts"], rec["checksum"], 1 if a.pin else 0))
    mid = cur.lastrowid
    index_terms(c, mid, extract_terms(title, body, tags))
    if emb_ready():
        store_emb(c, mid, title, body, rec["checksum"])
    if a.link:
        for other in re.findall(r"\d+", a.link):
            c.execute("INSERT OR IGNORE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)",
                      (mid, int(other), "relates", 1.0, now()))
            c.execute("INSERT OR IGNORE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)",
                      (int(other), mid, "relates", 1.0, now()))
    event(c, "add", {"id": mid, "title": title[:80]})
    c.commit()
    print(f"added #{mid} [{kind}/{rec['scope']}] {title[:80]}")
    return 0


def cmd_link(a, c):
    rel = a.rel or "relates"
    for (s, d) in ((a.src, a.dst), (a.dst, a.src)):
        if rel in ("derived_from", "supersedes"):
            if s != a.src:
                continue
        c.execute("INSERT OR REPLACE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (s, d, rel, a.weight, now()))
    event(c, "link", {"src": a.src, "dst": a.dst, "rel": rel})
    c.commit()
    print(f"linked {a.src} -{rel}-> {a.dst}")


def cmd_supersede(a, c):
    old = c.execute("SELECT id,title,ts FROM memories WHERE id=?", (a.old,)).fetchone()
    new = c.execute("SELECT id,title,ts FROM memories WHERE id=?", (a.new,)).fetchone()
    if not old or not new:
        die("both ids must exist")
    c.execute("UPDATE memories SET valid_to=?, superseded_by=? WHERE id=?", (new["ts"], a.new, a.old))
    c.execute("INSERT OR REPLACE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (a.new, a.old, "supersedes", 1.0, now()))
    event(c, "supersede", {"old": a.old, "new": a.new})
    journal({"op": "supersede", "old": a.old, "new": a.new, "ts": now()})
    c.commit()
    print(f"#{a.new} supersedes #{a.old} ({old['title'][:50]} → {new['title'][:50]})")


def cmd_pin(a, c):
    c.execute("UPDATE memories SET pinned=? WHERE id=?", (0 if a.off else 1, a.id))
    c.commit()
    print(f"#{a.id} pin={'off' if a.off else 'on'}")


def cmd_forget(a, c):
    flag = 0 if a.unarchive else 1
    c.execute("UPDATE memories SET archived=?, pinned=0 WHERE id=?", (flag, a.id))
    event(c, "archive" if flag else "unarchive", {"id": a.id})
    journal({"op": "archive" if flag else "unarchive", "id": a.id, "ts": now()})
    c.commit()
    print(f"#{a.id} {'archived (raw text retained; --unarchive restores)' if flag else 'restored'}")
    return 0


# ---------------------------------------------------------------- read
def prior(row):
    """decayed activation: importance × ebbinghaus decay + access reinforcement"""
    tau = TAU.get(row["kind"], 45.0)
    d = age_days(row["last_access"] or row["ts"])
    decay = math.exp(-age_days(row["ts"]) / tau)
    reinforce = 1.0 + 0.35 * math.log1p(row["accesses"])
    val = 1.0 if (row["valid_to"] is None and not row["superseded_by"]) else 0.25
    return row["importance"] * (0.65 * decay + 0.35) * reinforce * val


def scope_bonus(scope, ctx):
    if not ctx:
        return 1.0
    if scope == ctx:
        return 1.25
    if scope == "global":
        return 1.0
    if scope.split(":")[0] == ctx.split(":")[0]:
        return 0.95
    return 0.8


def fts_query(q):
    ts = tokens(q)
    if not ts:
        return None
    parts = []
    for t in ts[:12]:
        t = t.replace('"', "")
        parts.append(f'"{t}"*')
    return " OR ".join(parts), " AND ".join(parts)


def bm25_rank(c, q, limit=60):
    fq = fts_query(q)
    if not fq:
        return {}, {}
    or_q, and_q = fq
    rows = c.execute("""SELECT m.id, bm25(mem_fts, 4.0, 1.0, 2.0) AS s FROM mem_fts
        JOIN memories m ON m.id=mem_fts.rowid
        WHERE mem_fts MATCH ? AND m.archived=0 ORDER BY s LIMIT ?""", (and_q, limit)).fetchall()
    if len(rows) < 3:
        rows = c.execute("""SELECT m.id, bm25(mem_fts, 4.0, 1.0, 2.0) AS s FROM mem_fts
            JOIN memories m ON m.id=mem_fts.rowid
            WHERE mem_fts MATCH ? AND m.archived=0 ORDER BY s LIMIT ?""", (or_q, limit)).fetchall()
    # FTS5 bm25() is negative (more negative = better); convert to a positive 0..1 score
    out = {}
    for r in rows:
        x = max(0.0, -float(r["s"]))
        out[r["id"]] = x / (1.0 + x)
    return out, {r["id"]: i + 1 for i, r in enumerate(rows)}


def phrase_rank(c, q, limit=40):
    """entity/phrase index match, idf-weighted (rare phrase hits matter more)"""
    ts = tokens(q)
    if not ts:
        return {}
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/+]{1,}", q.lower())
    keys = list(dict.fromkeys(ts + [f"{a} {b}" for a, b in zip(raw, raw[1:]) if a not in STOP and b not in STOP]))
    total = max(1, c.execute("SELECT COUNT(*) n FROM memories WHERE archived=0").fetchone()["n"])
    scores = {}
    for k in keys[:18]:
        for r in c.execute("""SELECT mt.mem_id, mt.weight, e.df FROM entities e
              JOIN mentions mt ON mt.ent_id=e.id WHERE e.name=?""", (k,)).fetchall():
            idf = math.log(1.0 + total / max(1, r["df"]))
            scores[r["mem_id"]] = scores.get(r["mem_id"], 0.0) + r["weight"] * idf
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    mx = top[0][1] if top else 1.0
    return {i: s / mx for i, s in top}


def bigrams(q):
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/+]{1,}", q.lower())
    return [f"{a} {b}" for a, b in zip(raw, raw[1:]) if a not in STOP and b not in STOP and len(a) > 2 and len(b) > 2]


def prox_rank(c, q, limit=40):
    """verbatim phrase-proximity retrieval: query bigrams matched as FTS phrases"""
    scores = {}
    for bg in bigrams(q)[:4]:
        try:
            rows = c.execute("""SELECT m.id, bm25(mem_fts, 4.0, 1.0, 2.0) s FROM mem_fts
                JOIN memories m ON m.id=mem_fts.rowid WHERE mem_fts MATCH ? AND m.archived=0
                ORDER BY s LIMIT 20""", (f'"{bg}"',)).fetchall()
        except sqlite3.OperationalError:
            continue
        for r in rows:
            x = max(0.0, -float(r["s"]))
            scores[r["id"]] = scores.get(r["id"], 0.0) + x / (1.0 + x)
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    mx = top[0][1] if top else 1.0
    return {i: s / mx for i, s in top}


def anchor_cov(q, text):
    """fraction of query bigrams appearing verbatim, plus title term coverage"""
    bgs = bigrams(q)
    if not bgs:
        return 0.0
    low = re.sub(r"\s+", " ", text.lower())
    return sum(1 for b in bgs if b in low) / len(bgs)


def ppr(c, seeds, iters=4, damping=0.85, hops=2, limit=300):
    """personalized pagerank over memory graph (edges + co-mention), bounded subgraph"""
    if not seeds:
        return {}
    S = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        if not frontier or len(S) > limit:
            break
        nxt = set()
        qs = ",".join("?" * len(frontier))
        for r in c.execute(f"""SELECT src,dst FROM edges WHERE src IN ({qs}) OR dst IN ({qs})""",
                           (*frontier, *frontier)).fetchall():
            nxt.add(r["src"]); nxt.add(r["dst"])
        ents = [r["ent_id"] for r in c.execute(
            f"SELECT DISTINCT ent_id FROM mentions WHERE mem_id IN ({qs})", tuple(frontier)).fetchall()]
        if ents:
            eq = ",".join("?" * len(ents))
            for r in c.execute(f"""SELECT DISTINCT mem_id FROM mentions WHERE ent_id IN ({eq})
                    GROUP BY mem_id HAVING COUNT(*)>=1""", tuple(ents)).fetchall():
                nxt.add(r["mem_id"])
        nxt -= S
        S |= nxt
        frontier = nxt
    S = list(S)[:limit]
    if len(S) < 2:
        return {s: 1.0 for s in seeds}
    idx = {m: i for i, m in enumerate(S)}
    qs = ",".join("?" * len(S))
    adj = {m: {} for m in S}
    for r in c.execute(f"""SELECT src,dst,weight FROM edges
            WHERE (src IN ({qs}) AND dst IN ({qs}))""", (*S, *S)).fetchall():
        adj[r["src"]][r["dst"]] = adj[r["src"]].get(r["dst"], 0.0) + 0.5 * (r["weight"] or 1.0)
        adj[r["dst"]][r["src"]] = adj[r["dst"]].get(r["src"], 0.0) + 0.5 * (r["weight"] or 1.0)
    for r in c.execute(f"""SELECT a.mem_id x, b.mem_id y, SUM(a.weight*b.weight) w
            FROM mentions a JOIN mentions b ON a.ent_id=b.ent_id AND a.mem_id<b.mem_id
            WHERE a.mem_id IN ({qs}) AND b.mem_id IN ({qs}) GROUP BY 1,2""", (*S, *S)).fetchall():
        adj[r["x"]][r["y"]] = adj[r["x"]].get(r["y"], 0.0) + 0.25 * r["w"]
        adj[r["y"]][r["x"]] = adj[r["y"]].get(r["x"], 0.0) + 0.25 * r["w"]
    tot = sum(seeds.values()) or 1.0
    p = {m: (seeds.get(m, 0.0) / tot if m in seeds else 0.0) for m in S}
    base = dict(p)
    for _ in range(iters):
        nxt = {m: 0.0 for m in S}
        for m, w in p.items():
            if w <= 0:
                continue
            nb = adj[m]
            if not nb:
                continue
            s = sum(nb.values()) or 1.0
            for d, ew in nb.items():
                nxt[d] += w * ew / s
        p = {m: damping * nxt[m] + (1 - damping) * base.get(m, 0.0) for m in S}
    mx = max(p.values()) or 1.0
    return {m: v / mx for m, v in p.items() if v > 0}


def rrf(rankings, k=12, weights=None):
    """reciprocal rank fusion, min-max normalized output"""
    score = {}
    for i, rk in enumerate(rankings):
        if not rk:
            continue
        w = (weights or [])[i] if weights and i < len(weights) else 1.0
        for j, (mid, _s) in enumerate(sorted(rk.items(), key=lambda kv: -kv[1])):
            score[mid] = score.get(mid, 0.0) + w / (k + j + 1)
    if not score:
        return {}
    mx = max(score.values())
    return {m: s / mx for m, s in score.items()}


def search(c, q, k=8, ctx=None, budget=None, want_digests=True):
    t0 = time.time()
    bm, bm_rank = bm25_rank(c, q)
    ph = phrase_rank(c, q)
    seeds = dict(bm)
    for m, s in ph.items():
        seeds[m] = seeds.get(m, 0.0) + 0.9 * s
    top_seeds = dict(sorted(seeds.items(), key=lambda kv: -kv[1])[:25])
    pr = prox_rank(c, q)
    for m, s in pr.items():
        seeds[m] = seeds.get(m, 0.0) + 0.7 * s
    dn = {}
    if getattr(search, "use_dense", True):
        dn = dense_rank(c, q)   # confidence gating was tried and reverted: it never fired safely
    for m, s in dn.items():
        seeds[m] = seeds.get(m, 0.0) + 0.6 * s
    top_seeds = dict(sorted(seeds.items(), key=lambda kv: -kv[1])[:25])
    pp = ppr(c, top_seeds)
    fused = rrf([bm, ph, pr, pp, dn], weights=[1.0, 0.85, 1.15, 1.1, 1.35])
    qtok = set(tokens(q))
    cands = {}
    for mid in set(list(fused) + list(pp) + list(seeds) + list(pr) + list(dn)):
        row = c.execute("SELECT * FROM memories WHERE id=? AND archived=0", (mid,)).fetchone()
        if not row:
            continue
        ttok = set(tokens(row["title"]))
        t_cov = (len(qtok & ttok) / len(qtok)) if qtok else 0.0
        anc = anchor_cov(q, row["title"] + " " + row["body"][:600])
        sc = (1.45 * fused.get(mid, 0.0) + 0.5 * pp.get(mid, 0.0) + 0.7 * dn.get(mid, 0.0)
              + 0.8 * anc + 0.45 * t_cov
              + 0.30 * prior(row) * scope_bonus(row["scope"], ctx))
        if row["kind"] == "digest" and not want_digests:
            sc *= 0.9
        if row["pinned"]:
            sc += 0.12
        cands[mid] = (sc, row)
    for mid, row in [(r["id"], r) for r in c.execute(
            "SELECT * FROM memories WHERE pinned=1 AND archived=0").fetchall()]:
        cands.setdefault(mid, (0.9 * prior(row), row))
    ranked = sorted(cands.values(), key=lambda t: -t[0])

    # MMR-lite: penalize near-duplicate token sets so one answer doesn't eat the budget
    picked, seen_sets = [], []
    for sc, row in ranked:
        ts = tokset(row["title"] + " " + row["body"])
        if seen_sets and max(jacc(ts, s) for s in seen_sets) > 0.72:
            continue
        picked.append((sc, row))
        seen_sets.append(ts)
        if len(picked) >= max(k * 2, k + 4):
            break

    out, used_tok = [], 0
    for sc, row in picked:
        cost = est_tokens(row["title"]) + est_tokens(row["body"][:900]) + 12
        if budget and used_tok + cost > budget and out:
            break
        out.append((sc, row))
        used_tok += cost
        if len(out) >= k:
            break
    lat = (time.time() - t0) * 1000
    ids = [r["id"] for _, r in out]
    c.execute("INSERT INTO recalls(ts,query,returned,used,latency_ms,budget_tokens,result_tokens) VALUES(?,?,?,?,?,?,?)",
              (now(), q, json.dumps(ids), "[]", lat, budget or 0, used_tok))
    for _s, r in out:
        c.execute("UPDATE memories SET accesses=accesses+1, last_access=? WHERE id=?", (now(), r["id"]))
    c.commit()
    return out, used_tok, lat


def fmt_card(sc, row, idx):
    d = age_days(row["ts"])
    age = f"{d:.0f}d" if d >= 1 else f"{d*24:.0f}h"
    flags = []
    if row["pinned"]:
        flags.append("PIN")
    if row["valid_to"] or row["superseded_by"]:
        flags.append("STALE")
    if row["kind"] == "digest":
        flags.append("DIGEST")
    fl = (" " + ",".join(flags)) if flags else ""
    body = re.sub(r"\s+", " ", row["body"]).strip()
    return (f"[#{row['id']}] {row['kind']}/{row['scope']} {age} i={row['importance']:.1f} s={sc:.2f}{fl}\n"
            f"  {row['title'][:140]}\n  {body[:420]}{'…' if len(body) > 420 else ''}")


def cmd_search(a, c):
    if a.dense is not None:
        search.use_dense = a.dense
        search.force_dense = a.dense
    out, used, lat = search(c, " ".join(a.query), k=a.k, ctx=a.scope, budget=a.budget)
    if a.json:
        print(json.dumps([{"id": r["id"], "score": round(s, 3), "kind": r["kind"], "scope": r["scope"],
                           "title": r["title"], "body": r["body"], "tags": json.loads(r["tags"]),
                           "age_days": round(age_days(r["ts"]), 1)} for s, r in out], indent=1))
        return 0
    if not out:
        print("(no memories matched)")
        return 0
    print("\n\n".join(fmt_card(s, r, i) for i, (s, r) in enumerate(out)))
    print(f"\n-- {len(out)} hits, ~{used} tok, {lat:.0f} ms")
    return 0


def cmd_get(a, c):
    rows = [c.execute("SELECT * FROM memories WHERE id=? OR uid=?", (a.id, str(a.id))).fetchone()]
    for r in rows:
        if not r:
            die("not found")
        print(f"#{r['id']} uid={r['uid']} [{r['kind']}/{r['scope']}] {time.strftime('%Y-%m-%d %H:%M', time.gmtime(r['ts']))} (UTC)")
        print(f"title: {r['title']}\ntags: {r['tags']} importance={r['importance']} conf={r['confidence']} accesses={r['accesses']} pinned={r['pinned']} archived={r['archived']}")
        if r["superseded_by"]:
            print(f"SUPERSEDED by #{r['superseded_by']}")
        print(f"source: {r['source']}\n---\n{r['body']}")
        print("---")
        for e in c.execute("""SELECT e.name, mt.weight FROM mentions mt JOIN entities e ON e.id=mt.ent_id
                WHERE mt.mem_id=? ORDER BY mt.weight DESC LIMIT 12""", (r["id"],)):
            print(f"  ~{e['name']}")
        for e in c.execute("SELECT dst,rel,weight FROM edges WHERE src=? UNION SELECT src,rel,weight FROM edges WHERE dst=?", (r["id"], r["id"])):
            print(f"  -> #{e['dst']} {e['rel']}")
    return 0


def agenda_line() -> str:
    """One line from the agenda store, so a due item cannot be invisible at session start."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agenda", "agenda.db")
    if not os.path.exists(path):
        return ""
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        now = time.time()
        due = db.execute(
            "select id, next_due from obligations where enabled=1 and next_due<=? order by priority", (now,)
        ).fetchall()
        late = db.execute(
            "select id, due from tasks where status in ('open','doing') and due is not null and due<=?"
            " order by priority", (now,)
        ).fetchall()
        nxt = db.execute(
            "select id, next_due from obligations where enabled=1 and next_due>? order by next_due limit 1",
            (now,),
        ).fetchone()
        db.close()
    except Exception:
        return ""
    parts = []
    if due:
        parts.append(f"{len(due)} due ({', '.join(r[0] for r in due[:3])})")
    if late:
        parts.append(f"{len(late)} overdue task(s) ({', '.join('#' + str(r[0]) for r in late[:3])})")
    if nxt:
        delta = nxt[1] - now
        when = f"{delta / 60:.0f}m" if delta < 7200 else f"{delta / 3600:.0f}h"
        parts.append(f"next {nxt[0]} in {when}")
    if not parts:
        return "clear"
    tail = "" if due or late else " — run `pi-agenda next`"
    return "; ".join(parts) + tail


# A pinned row is the one thing a session must not miss, so pinned comes first — but not without a
# ceiling, or the pinned set would grow until the brief is only pins. 0.80 measured 2026-11-16: the
# 7 live pinned rows cost 565 tokens, so at the 1100 default the floor is 880 and every pin fits
# while KEY/RECENT/PDSA still share 220 (at 0.62 the floor cut one pin at 1100 and three at 900).
CORE_SHARE = 0.80


def cmd_brief(a, c):
    """session-start working set: pinned core + top lessons/decisions + recent, in slices.

    Allocator, measured 2026-11-16: fixed shares (CORE 30%, KEY 34%, RECENT 22%, PDSA 14%) cut the
    pinned set at 3 of 7 rows and KEY at 3 of 10 while RECENT (8/8, the cheapest and most
    disposable section) lost nothing — the cap was never the constraint, the split was. Pinned rows
    now take their real cost first (up to CORE_SHARE of the budget), and the rest split what is left
    in proportion. Every section states how many rows it dropped, so a truncated brief is visible
    instead of silent; a section whose rows were all dropped still prints its header, and if the
    pinned set itself does not fit, the optional sections are withheld rather than shown while a
    pinned rule (the thing a session must not miss) is missing.
    """
    budget = a.budget
    if budget < 120:
        # below this no pinned rule fits, so printing headers would be a lie about what a session
        # knows: say the one true thing and stop (tester finding: --budget 0 printed ~54/0)
        print(f"brief: --budget {budget} is too small for one pinned rule (the 7 live pins cost "
              f"~565 tok); use --budget 1100")
        return 0
    reserve = min(70, max(0, budget // 8))     # footer room, scaled: never make `used` exceed it
    budget -= reserve
    rest = {"KEY": 0.63, "RECENT": 0.25, "PDSA": 0.12}
    blocks, used = [], 0

    def section(title, rows, fmt, cap):
        """Print a section with first-fit rows under `cap`; return (spent, dropped).

        The header prints even when nothing fits: a section with 0 lines and no header hid both the
        section and its drops (tester finding, 2026-11-16).
        """
        nonlocal used
        spent, lines, dropped = 0, [], 0
        for r in rows:
            txt = fmt(r)
            cost = est_tokens(txt)
            if spent + cost > cap:
                dropped += 1
                continue
            lines.append(txt)
            spent += cost
        if rows:
            head = f"## {title}" + (f" {len(lines)}/{len(rows)}" if dropped else "")
            blocks.append(head)
            used += est_tokens(head)
            blocks.extend(lines)
            used += spent
        return spent, dropped

    # a superseded or archived pin is not a rule any more: #19 was superseded and still printed in
    # CORE because this query, unlike the KEY one, never filtered it (tester finding, 2026-11-16)
    core = c.execute("""SELECT * FROM memories WHERE pinned=1 AND archived=0
        AND valid_to IS NULL AND superseded_by IS NULL AND kind != 'digest'
        ORDER BY importance DESC LIMIT 8""").fetchall()
    spent_core, dropped_core = section(
        "CORE (pinned)", core,
        lambda r: f"[#{r['id']}] {r['title'][:150]}: {re.sub(r'\\s+', ' ', r['body'])[:260]}",
        int(budget * CORE_SHARE))
    left = max(budget - spent_core, 0)
    if dropped_core:
        blocks.append(f"(budget too small for {dropped_core} pinned rule(s); optional sections "
                      f"withheld — raise --budget)")
        used += 20
        left = 0
    # digests are an index over raw rows, not a memory to act on: they belong in `mem search`,
    # never in the 8-row RECENT window (tester hypothesis, confirmed by the query having no filter)
    imp = c.execute("""SELECT * FROM memories WHERE archived=0 AND pinned=0 AND kind IN ('lesson','decision','playbook','pref')
        AND valid_to IS NULL AND superseded_by IS NULL
        ORDER BY importance DESC, ts DESC LIMIT 10""").fetchall()
    if left:
        section("KEY LESSONS / PREFERENCES", imp,
                lambda r: f"[#{r['id']}] ({r['kind']}) {r['title'][:120]}: {re.sub(r'\\s+', ' ', r['body'])[:200]}",
                int(left * rest["KEY"]))
        rec = c.execute("""SELECT * FROM memories WHERE archived=0 AND kind != 'digest'
            ORDER BY ts DESC LIMIT 8""").fetchall()
        section("RECENT", rec, lambda r: f"[#{r['id']}] {r['title'][:110]} ({age_days(r['ts']):.0f}d)",
                int(left * rest["RECENT"]))
        pd = c.execute("SELECT cycle,plan FROM pdsa WHERE status='open' ORDER BY cycle DESC LIMIT 2").fetchall()
        section("OPEN PDSA", pd,
                lambda r: f"cycle {r['cycle']}: {re.sub(r'\\s+', ' ', r['plan'] or '')[:180]}",
                int(left * rest["PDSA"]))
    line = agenda_line()
    if line and used + est_tokens(line) + 8 <= budget + reserve:
        blocks.append("## AGENDA")
        blocks.append(line)
        used += est_tokens(line) + 3
    st = c.execute("SELECT COUNT(*) n, SUM(archived) ar FROM memories").fetchone()
    print("\n".join(blocks))
    # measured, not a fudge: `used` is the estimated tokens actually printed (the old footer added a
    # hard-coded 40, so --budget 0 reported "~54/0" — tester finding, 2026-11-16)
    print(f"## STATS {st['n']} memories ({st['ar'] or 0} archived), "
          f"budget ~{used}/{a.budget} tok")
    # A pinned rule is a promise that it is in every session. When the budget cannot hold the set,
    # the brief used to print 6/7 and still exit 0, so the caller could not tell a complete brief
    # from a truncated one (measured 2026-11-20: the boot extension asked for 700 while the pins
    # need ~830, and one pinned rule was never loaded). Exit 1 so the guard has something to read.
    return 1 if dropped_core else 0


# ---------------------------------------------------------------- consolidate
def build_digests(c, min_df=4, per=6):
    """extractive theme digests (RAPTOR-flavoured, but additive: originals stay primary)"""
    made = 0
    ents = c.execute("""SELECT e.id, e.name, e.df FROM entities e WHERE e.df>=? AND length(e.name)>3
        ORDER BY e.df DESC LIMIT 40""", (min_df,)).fetchall()
    for e in ents:
        title = f"Theme: {e['name']}"
        if c.execute("SELECT 1 FROM memories WHERE title=? AND archived=0", (title,)).fetchone():
            continue
        mems = c.execute("""SELECT m.id,m.kind,m.title,m.body,m.importance FROM memories m
            JOIN mentions mt ON mt.mem_id=m.id WHERE mt.ent_id=? AND m.archived=0
            AND m.kind!='digest' ORDER BY m.importance DESC, m.ts DESC LIMIT ?""", (e["id"], per)).fetchall()
        if len(mems) < min_df:
            continue
        body = "Extractive index over raw entries (originals kept). " + " ".join(
            f"#{m['id']} {m['title'][:90]};" for m in mems)
        # `uid` is the unique key, not `title`: the early check above only sees live rows, so a
        # digest that was archived and is rebuilt with the same body would collide here and abort
        # the whole weekly consolidation (measured 2026-11-16: UNIQUE constraint on memories.uid).
        uid = uid_for(title, body)
        if c.execute("SELECT 1 FROM memories WHERE uid=?", (uid,)).fetchone():
            continue
        cur = c.execute("""INSERT INTO memories(uid,ts,kind,scope,title,body,tags,importance,confidence,
            source,valid_from,checksum) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, now(), "digest", "global", title, body, json.dumps(["digest", e["name"]]),
             0.55, 0.9, "consolidate", now(), hashlib.sha256(body.encode()).hexdigest()[:16]))
        did = cur.lastrowid
        index_terms(c, did, extract_terms(title, body, ["digest"]))
        for m in mems:
            c.execute("INSERT OR IGNORE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (did, m["id"], "derived_from", 0.6, now()))
        if emb_ready():
            store_emb(c, did, title, body, hashlib.sha256(body.encode()).hexdigest()[:16])
        made += 1
    return made


def cmd_consolidate(a, c):
    rows = c.execute("SELECT * FROM memories WHERE archived=0").fetchall()
    toks = {r["id"]: tokset(r["title"] + " " + r["body"]) for r in rows}
    dup_pairs, merge_budget = [], a.max_merges
    ids = list(toks)
    cos = {}
    if emb_ready():
        missing = [r for r in rows if not c.execute(
            "SELECT 1 FROM embeddings WHERE mem_id=? AND model=?", (r["id"], EMB_MODEL)).fetchone()]
        if missing:
            vs = embed([f"{r['title']}. {r['body']}" for r in missing])
            for r, v in zip(missing, vs):
                c.execute("INSERT OR REPLACE INTO embeddings(mem_id,vec,model,dim,checksum) VALUES(?,?,?,?,?)",
                          (r["id"], v.tobytes(), EMB_MODEL, int(v.shape[0]), r["checksum"]))
        import numpy as np
        got = [(r["mem_id"], np.frombuffer(r["vec"], dtype=np.float32)) for r in c.execute(
            "SELECT e.mem_id, e.vec FROM embeddings e JOIN memories m ON m.id=e.mem_id "
            "WHERE m.archived=0 AND e.model=?", (EMB_MODEL,)).fetchall()]
        for i in range(len(got)):
            for j in range(i + 1, len(got)):
                cos[(got[i][0], got[j][0])] = float(got[i][1] @ got[j][1])
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            j = jacc(toks[x], toks[y])
            dc = cos.get((x, y), cos.get((y, x), 0.0))
            if j >= a.dedup_threshold or dc >= a.sem_dedup:
                dup_pairs.append((max(j, dc), x, y))
                event(c, "near-dup", {"a": x, "b": y, "jac": round(j, 3), "cos": round(dc, 3)})
    dup_pairs.sort(reverse=True)
    made = 0
    for s, x, y in dup_pairs[:200]:
        rx = c.execute("SELECT * FROM memories WHERE id=?", (x,)).fetchone()
        ry = c.execute("SELECT * FROM memories WHERE id=?", (y,)).fetchone()
        if not rx or not ry:
            continue
        keeper, other = (rx, ry) if prior(rx) >= prior(ry) else (ry, rx)
        c.execute("INSERT OR IGNORE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (keeper["id"], other["id"], "relates", s, now()))
        c.execute("INSERT OR IGNORE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (other["id"], keeper["id"], "relates", s, now()))
        c.execute("UPDATE memories SET archived=1, pinned=0 WHERE id=?", (other["id"],))
        event(c, "dedup", {"kept": keeper["id"], "archived": other["id"], "sim": round(s, 3)})
        made += 1
    # conflict / supersession: same entities, new-cue vs old-cue or high overlap with differing numbers
    sup = 0
    live = c.execute("SELECT * FROM memories WHERE archived=0 AND valid_to IS NULL ORDER BY ts").fetchall()
    by_ent = {}
    for r in live:
        for m in c.execute("SELECT ent_id FROM mentions WHERE mem_id=?", (r["id"],)):
            by_ent.setdefault(m["ent_id"], []).append(r)
    seen = set()
    for eid, group in by_ent.items():
        if len(group) < 2 or len(group) > 12:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                o, n = group[i], group[j]
                if o["id"] == n["id"] or (o["id"], n["id"]) in seen:
                    continue
                if o["kind"] != n["kind"] or o["kind"] in ("source", "digest"):
                    continue
                if not (CUE_NEW.search(n["body"]) and (CUE_OLD.search(o["body"]) or jacc(toks[o["id"]], toks[n["id"]]) > 0.5)):
                    continue
                c.execute("UPDATE memories SET valid_to=?, superseded_by=? WHERE id=?", (n["ts"], n["id"], o["id"]))
                c.execute("INSERT OR REPLACE INTO edges(src,dst,rel,weight,ts) VALUES(?,?,?,?,?)", (n["id"], o["id"], "supersedes", 1.0, now()))
                event(c, "supersede", {"old": o["id"], "new": n["id"], "via": "consolidate", "ent": eid})
                seen.add((o["id"], n["id"]))
                sup += 1
    # decay / archive
    ar = 0
    for r in c.execute("SELECT * FROM memories WHERE archived=0 AND pinned=0").fetchall():
        p = prior(r)
        if p < a.archive_below and age_days(r["ts"]) > 45:
            c.execute("UPDATE memories SET archived=1 WHERE id=?", (r["id"],))
            ar += 1
    dig = 0
    if a.digest and a.refresh_digests:
        olds = [r["id"] for r in c.execute("SELECT id FROM memories WHERE kind='digest'").fetchall()]
        for i in olds:
            c.execute("DELETE FROM embeddings WHERE mem_id=?", (i,))
            c.execute("DELETE FROM mentions WHERE mem_id=?", (i,))
            c.execute("DELETE FROM edges WHERE src=? OR dst=?", (i, i))
            c.execute("DELETE FROM memories WHERE id=?", (i,))
    if a.digest:
        dig = build_digests(c, min_df=a.digest_min_df, per=a.digest_per)
    c.commit()
    report = {"deduped": made, "superseded": sup, "archived": ar, "digests": dig,
              "live": c.execute(
        "SELECT COUNT(*) n FROM memories WHERE archived=0").fetchone()["n"]}
    event(c, "consolidate", report)
    journal({"op": "consolidate", "report": report, "ts": now()})
    print(json.dumps(report, indent=1))
    return 0


# ---------------------------------------------------------------- stats / pdsa / eval
def cmd_stats(a, c):
    q = lambda s, *p: c.execute(s, p).fetchall()
    n = q("SELECT COUNT(*) n FROM memories")[0]["n"]
    live = q("SELECT COUNT(*) n FROM memories WHERE archived=0")[0]["n"]
    print(f"memories: {n} total, {live} live, {n-live} archived")
    for r in q("SELECT kind, COUNT(*) n, ROUND(AVG(importance),2) i FROM memories GROUP BY kind ORDER BY n DESC"):
        print(f"  {r['kind']:<9} {r['n']:>4}  avg_i={r['i']}")
    ent = q("SELECT COUNT(*) n FROM entities")[0]["n"]
    men = q("SELECT COUNT(*) n FROM mentions")[0]["n"]
    edg = q("SELECT COUNT(*) n FROM edges")[0]["n"]
    print(f"graph: {ent} entities, {men} mentions, {edg} edges")
    rl = q("SELECT COUNT(*) n, AVG(latency_ms) l, AVG(result_tokens) t FROM recalls")[0]
    print(f"recalls: {rl['n']} avg_latency={rl['l'] or 0:.1f}ms avg_tokens={rl['t'] or 0:.0f}")
    sz = os.path.getsize(DBP) / 1024 if os.path.exists(DBP) else 0
    print(f"db: {sz:.0f} KB at {DBP}")
    return 0


def cmd_pdsa(a, c):
    if a.action == "new":
        cyc = c.execute("SELECT COALESCE(MAX(cycle),0)+1 c FROM pdsa").fetchone()["c"]
        c.execute("INSERT INTO pdsa(cycle,plan,status,created,updated) VALUES(?,?, 'open',?,?)", (cyc, a.plan, now(), now()))
        c.commit()
        print(f"pdsa cycle {cyc} opened: {a.plan}")
    elif a.action == "update":
        row = c.execute("SELECT * FROM pdsa WHERE cycle=?", (a.cycle,)).fetchone()
        if not row:
            die("no such cycle")
        fields = {"plan": a.plan, "do": a.do, "study": a.study, "act": a.act}
        for k, v in fields.items():
            if v is not None:
                c.execute(f"UPDATE pdsa SET {k}=? WHERE cycle=?", (v, a.cycle))
        if a.metric_before is not None:
            c.execute("UPDATE pdsa SET metric_before=? WHERE cycle=?", (a.metric_before, a.cycle))
        if a.metric_after is not None:
            c.execute("UPDATE pdsa SET metric_after=? WHERE cycle=?", (a.metric_after, a.cycle))
        if a.status:
            c.execute("UPDATE pdsa SET status=? WHERE cycle=?", (a.status, a.cycle))
        c.execute("UPDATE pdsa SET updated=? WHERE cycle=?", (now(), a.cycle))
        c.commit()
        print(f"pdsa cycle {a.cycle} updated")
    else:
        rows = c.execute("SELECT * FROM pdsa ORDER BY cycle DESC").fetchall()
        for r in rows:
            print(f"--- cycle {r['cycle']} [{r['status']}] {time.strftime('%Y-%m-%d', time.gmtime(r['created']))}"
                  f" metric {r['metric_before']}→{r['metric_after']}")
            for k in ("plan", "do", "study", "act"):
                if r[k]:
                    print(f"{k.upper():<6}{re.sub(r'\s+', ' ', r[k])[:600]}")
    return 0


def cmd_eval(a, c):
    if not os.path.exists(EVALP):
        die(f"no eval set at {EVALP}")
    if getattr(a, "dense", None) is not None:
        search.use_dense = a.dense
        search.force_dense = a.dense
    spec = json.load(open(EVALP))
    qs = spec["queries"] if isinstance(spec, dict) else spec
    hits5 = hitsb = 0
    rr = 0.0
    lat, toks = [], []
    misses = []
    for case in qs:
        q = case["q"]
        expect = {int(e) if str(e).isdigit() else e for e in case["expect"]}
        for trial in (1, 2):  # warm, measure second pass
            out, used, ms = search(c, q, k=6, ctx=case.get("scope"), budget=case.get("budget"))
        ids = [r["id"] for _s, r in out]
        hit = sorted(set(ids) & expect)
        hits5 += 1 if hit else 0
        hitsb += 1 if all(e in ids for e in expect) else 0
        rank = min([ids.index(e) for e in hit], default=0)
        rr += (1.0 / (rank + 1)) if hit else 0.0
        lat.append(ms); toks.append(used)
        if not hit:
            misses.append((q, sorted(expect), ids[:4]))
        if a.verbose:
            print(f"{'OK ' if hit else 'MISS'} {q[:60]:<62} ranks={[ids.index(e)+1 for e in hit]} tok={used}")
    n = len(qs)
    res = {"n": n, "recall@6": round(hits5 / n, 3), "all_expected": round(hitsb / n, 3),
           "mrr": round(rr / n, 3), "avg_tokens": round(sum(toks) / n, 0),
           "p50_ms": round(sorted(lat)[len(lat) // 2], 1)}
    print(json.dumps(res, indent=1))
    if misses:
        print("\nmisses:")
        for m in misses:
            print(f"  q={m[0][:70]!r} want={m[1]} got={m[2]}")
    if a.save:
        json.dump(res, open(os.path.join(BASE, f"eval-{time.strftime('%Y%m%dT%H%M')}.json"), "w"), indent=1)
    return 0


def cmd_embed(a, c):
    if not emb_ready():
        die(f"dense layer unavailable: need {VENV_PY}, {MODEL_ONNX}, {TOK_JSON}")
    todo = c.execute("""SELECT m.id, m.title, m.body, m.checksum FROM memories m
        LEFT JOIN embeddings e ON e.mem_id=m.id
        WHERE e.mem_id IS NULL OR e.checksum IS NOT m.checksum OR e.model IS NOT ?""", (EMB_MODEL,)).fetchall()
    if not todo:
        print("all memories embedded")
        return 0
    t0 = time.time()
    B = 16
    for i in range(0, len(todo), B):
        batch = todo[i:i + B]
        vs = embed([f"{r['title']}. {r['body']}" for r in batch])
        for r, v in zip(batch, vs):
            c.execute("INSERT OR REPLACE INTO embeddings(mem_id,vec,model,dim,checksum) VALUES(?,?,?,?,?)",
                      (r["id"], v.tobytes(), EMB_MODEL, int(v.shape[0]), r["checksum"]))
    c.commit()
    print(f"embedded {len(todo)} memories in {time.time()-t0:.1f}s")
    # pruning stale/archived vectors
    n = c.execute("""DELETE FROM embeddings WHERE mem_id NOT IN
        (SELECT id FROM memories)""").rowcount
    if n:
        c.commit()
    return 0


def cmd_doctor(a, c):
    import shutil
    print(f"mem home      {BASE}")
    print(f"db            {DBP} ({os.path.getsize(DBP)/1024:.0f} KB)" if os.path.exists(DBP) else "db            none")
    print(f"dense layer   {'ON' if emb_ready() else 'OFF'}"
          f"  model={'yes' if os.path.exists(MODEL_ONNX) else 'missing'} venv={'yes' if os.path.exists(VENV_PY) else 'missing'}")
    if emb_ready():
        import numpy, onnxruntime
        print(f"              numpy {numpy.__version__} / ort {onnxruntime.__version__} / {EMB_MODEL}")
        try:
            t0 = time.time(); session, _tok = embedder(); t1 = time.time()
            embed(["warmup"]); t2 = time.time()
            print(f"              load {1000*(t1-t0):.0f} ms, query embed {1000*(t2-t1):.0f} ms")
        except Exception as ex:
            print(f"              embed error: {ex}")
    print(f"journal       {len(os.listdir(JRN)) if os.path.isdir(JRN) else 0} day-files")
    n = c.execute("SELECT COUNT(*) n FROM memories").fetchone()["n"]
    ne = c.execute("SELECT COUNT(*) n FROM embeddings").fetchone()["n"]
    print(f"memories      {n} ({ne} embedded)")
    print(f"journal/raw   every write is appended to {JRN}/<date>.jsonl before the DB")
    return 0


def cmd_export(a, c):
    rows = c.execute("SELECT * FROM memories WHERE archived=0 ORDER BY id").fetchall()
    if a.format == "jsonl":
        for r in rows:
            print(json.dumps({k: r[k] for k in r.keys()}, ensure_ascii=False))
    else:
        for r in rows:
            print(f"## #{r['id']} {r['title']}\n- {r['kind']}/{r['scope']} {time.strftime('%Y-%m-%d', time.gmtime(r['ts']))} i={r['importance']}\n\n{r['body']}\n")
    return 0


def cmd_reindex(a, c):
    c.execute("INSERT INTO mem_fts(mem_fts) VALUES('rebuild')")
    c.execute("DELETE FROM mentions")
    for r in c.execute("SELECT * FROM memories").fetchall():
        index_terms(c, r["id"], extract_terms(r["title"], r["body"], json.loads(r["tags"])))
    c.execute("UPDATE entities SET df=1")
    c.commit()
    print(f"reindexed {c.execute('SELECT COUNT(*) n FROM memories').fetchone()['n']} memories")


def cmd_used(a, c):
    rid = c.execute("SELECT id FROM recalls ORDER BY id DESC LIMIT 1").fetchone()
    if not rid:
        die("no recalls yet")
    c.execute("UPDATE recalls SET used=? WHERE id=?", (json.dumps(a.ids), rid["id"]))
    c.commit()
    print(f"recall #{rid['id']} marked used={a.ids}")


def die(m):
    print(f"mem: {m}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- cli
def main():
    p = argparse.ArgumentParser(prog="mem", description="hybrid agent memory (BM25 + graph PPR + decay)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_cmd(name, fn, **kw):
        sp = sub.add_parser(name, **kw)
        sp.set_defaults(fn=fn)
        return sp

    s = add_cmd("add", cmd_add, help="store a memory (body from arg or stdin)")
    s.add_argument("body", nargs="?", default="-")
    s.add_argument("--title", "-t")
    s.add_argument("--kind", "-k", default="note", help=f"one of {sorted(KINDS)}")
    s.add_argument("--scope", "-s", default="global")
    s.add_argument("--tags", "-g", default="")
    s.add_argument("--importance", "-i", type=float, default=0.5)
    s.add_argument("--confidence", type=float, default=0.8)
    s.add_argument("--source", default="")
    s.add_argument("--link", default="", help="comma ids to relate")
    s.add_argument("--pin", action="store_true")
    s.add_argument("--force", action="store_true")

    s = add_cmd("search", cmd_search, help="hybrid recall")
    s.add_argument("query", nargs="+")
    s.add_argument("--k", type=int, default=8)
    s.add_argument("--budget", type=int, default=1400, help="token budget for results")
    s.add_argument("--scope", default=None, help="context scope for boosting")
    s.add_argument("--json", action="store_true")
    s.add_argument("--dense", dest="dense", action="store_true", default=None)
    s.add_argument("--no-dense", dest="dense", action="store_false")

    s = add_cmd("brief", cmd_brief, help="session-start working set")
    # 1100: measured pinned+KEY+RECENT content is ~1105 tokens (2026-11-16). Growth beyond this is
    # absorbed by the allocator (pinned first, then proportional) and printed as drops, not silent.
    s.add_argument("--budget", type=int, default=1100)

    s = add_cmd("get", cmd_get); s.add_argument("id")
    s = add_cmd("pin", cmd_pin); s.add_argument("id", type=int); s.add_argument("--off", action="store_true")
    s = add_cmd("forget", cmd_forget); s.add_argument("id", type=int)
    s.add_argument("--unarchive", action="store_true")
    s = add_cmd("stats", cmd_stats)

    s = add_cmd("link", cmd_link); s.add_argument("src", type=int); s.add_argument("dst", type=int)
    s.add_argument("--rel", default="relates"); s.add_argument("--weight", type=float, default=1.0)
    s = add_cmd("supersede", cmd_supersede); s.add_argument("old", type=int); s.add_argument("new", type=int)

    s = add_cmd("consolidate", cmd_consolidate, help="dedupe, resolve conflicts, decay")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--dedup-threshold", type=float, default=0.80)
    s.add_argument("--sem-dedup", type=float, default=0.90, help="cosine gate for paraphrase duplicates")
    s.add_argument("--archive-below", type=float, default=0.06)
    s.add_argument("--max-merges", type=int, default=50)
    s.add_argument("--digest", action="store_true", help="also build extractive theme digests")
    s.add_argument("--digest-min-df", type=int, default=4)
    s.add_argument("--digest-per", type=int, default=5)
    s.add_argument("--refresh-digests", action="store_true")

    s = add_cmd("pdsa", cmd_pdsa)
    s.add_argument("action", choices=["new", "update", "list"])
    s.add_argument("--cycle", type=int)
    s.add_argument("--plan"); s.add_argument("--do"); s.add_argument("--study"); s.add_argument("--act")
    s.add_argument("--metric-before", type=float); s.add_argument("--metric-after", type=float)
    s.add_argument("--status", choices=["open", "closed"])

    s = add_cmd("eval", cmd_eval)
    s.add_argument("--verbose", "-v", action="store_true")
    s.add_argument("--save", action="store_true")
    s.add_argument("--dense", dest="dense", action="store_true", default=None)
    s.add_argument("--no-dense", dest="dense", action="store_false")
    s = add_cmd("embed", cmd_embed, help="build/refresh dense vectors")
    s = add_cmd("doctor", cmd_doctor, help="capability + health report")
    s = add_cmd("export", cmd_export); s.add_argument("--format", default="md", choices=["md", "jsonl"])
    s = add_cmd("reindex", cmd_reindex)
    s = add_cmd("used", cmd_used); s.add_argument("ids", nargs="+", type=int)

    a = p.parse_args()
    c = conn()
    return a.fn(a, c) or 0


if __name__ == "__main__":
    try:
        rc = main() or 0
    except BrokenPipeError:
        rc = 0
    sys.stdout.flush()
    sys.stderr.flush()
    # skip interpreter teardown: numpy/onnxruntime cleanup costs ~300 ms per invocation
    os._exit(rc)
