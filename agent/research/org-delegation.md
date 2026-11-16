# Organizational delegation, task allocation and roles — evidence base (2026-11-15)

Question: how do large organizations decide what to delegate, how to partition work, who owns an
item, and how much work to have in flight — and which of those mechanisms transfer to an agent
harness? Decision it flips: the intake/partition/role rules in `delegation/policy.md` v3.

Method: Crossref bibliographic queries (8 topics), full abstracts where available; Wikipedia
extracts for definitions (cited by article title, not year — a wiki article is not a dated paper);
canonical books/essays named as such when Crossref returned no DOI. Harvest fold:
`/tmp/deleg/b.out` (scout, 227 s, $0.13). **Every DOI below was re-fetched and title-checked**;
claims that the fold made without a retrievable source were dropped (e.g. an SRE "64% of orgs"
figure that no retrieved source supported).

## Findings that transfer

### Partition on communication boundaries, not on headcount
- **Conway's law** (Conway 1967; Wikipedia "Conway's law"): organizations produce designs that copy
  their communication structure; MacCormack et al. (2012) found loosely-coupled organizations build
  more modular products. → *shard along module boundaries; a shard that needs constant talk with
  another is one shard.*
- **Team Topologies** (Skelton & Pais 2019, canonical): four team types (stream-aligned, enabling,
  complicated-subsystem, platform), three interaction modes (collaboration, X-as-a-service,
  facilitating), and **team cognitive load** as the design constraint. → *the parent is the
  platform; scouts/workers are stream-aligned; a hub file is a platform interface with one owner.*
- **Human–task–agent alignment** (10.2139/ssrn.7256278, 2026): a synthetic stress test across the
  four Team Topologies profiles; agent impact depends on the interaction of task demands, autonomy,
  review queues and topology, not on a single treatment effect. → *evaluate a delegation recipe in
  its topology (who reviews, what queue), not in isolation.*

### One accountable owner, explicit decision rights
- **RACI** (Wikipedia "Responsibility assignment matrix"): Responsible executes, **Accountable is
  individually answerable and should be exactly one per deliverable**, Consulted, Informed. → *the
  parent is the single A; a child is R for its item and I for nothing else.*
- **Oncken's monkey** (Oncken 1974, HBR, canonical): the "monkey" (next move) must stay with the
  owner; a manager who accepts it back becomes the subordinate's subordinate. → *a child that
  returns "what should I do next?" has not been given a contract; the parent must not absorb it.*
- **Who has the D?** (Rogers & Blenko 2006, HBR, canonical; RAPID): separate Recommend, Agree,
  Input, **Decide**, Perform; unclear decision roles are a common cause of slow decisions. → *the
  parent decides scope/acceptance; the worker performs; the verifier recommends a verdict on
  evidence; nobody else decides.*
- **Delegation of decision rights** (10.2139/ssrn.4473848, 2023): the overall level of HQ→local
  delegation was **not associated** with firm performance. (10.2139/ssrn.4014546, 2022):
  centralization drives inertia through bounded information processing. (10.2139/ssrn.2443919,
  2014): firms under-delegate relative to agency-theory predictions, which weakens subordinates'
  incentive to gather information. → *delegate execution and local choices; keep priority,
  acceptance and integration central. "More autonomy" is not a strategy.*

### Pull, limit WIP, and pace to the bottleneck
- **Kanban** (Wikipedia "Kanban (development)"): visualize work, **limit WIP per stage**, pull as
  capacity permits, make policies explicit, use service-level expectations. WiP limits are treated
  as a first-class practice (10.1002/9781119019732.ch4, *Kanban Change Leadership*, 2015).
  → *cap concurrent children (4) and fan-out size (8); a queue of children is a WIP violation.*
- **Little's law / flow** (Reinertsen 2009, *Principles of Product Development Flow*, canonical):
  cycle time = WIP / throughput; small batches and queue limits beat high utilization; batch size
  has a U-shaped cost curve. → *first-pass yield and cycle time are the metrics; utilization is not.*
- **Self-assignment** (10.1007/978-3-319-57633-6_22, 2017) and **self-organizing teams**
  (10.26686/wgtn.16985179, grounded theory, 58 practitioners / 23 organizations): Scrum mandates
  self-organization but gives few concrete guidelines for becoming/remaining self-organizing.
  → *pull is good, but needs an explicit protocol: ready queue + claimed item + owner + check.
  Autonomy without a protocol is the failure the paper documents.*
- **Theory of constraints** (Goldratt; Wikipedia "Theory of constraints"): throughput equals the
  bottleneck's capacity; drum–buffer–rope and critical-chain buffers protect the constraint.
  → *pace dispatch to the slowest stage — usually verification/integration, not generation.*

### Small batches, explicit flow, retrospective
- **Scrum** (Wikipedia "Scrum (project management)"): time-boxed iterations, a prioritized backlog,
  a cross-functional self-managing team, a review and a **retrospective**; roles separate value
  ordering (Product Owner), execution (Developers), process (Scrum Master). → *agenda = backlog,
  parent = PO + Scrum Master, retrospective = `pi-delegate flow`.*
- **Accelerate / DORA** (Forsgren, Humble & Kim 2018, canonical): small batch size, trunk-based
  development, loosely coupled architecture and psychological safety predict delivery performance;
  measure lead time, deployment frequency, change-failure rate, MTTR. → *measure lead time (dispatch
  → verdict), rework (fail rate), and batch size (files per shard), not raw activity.*
- **Jira issue tracking** (10.1049/sfw2.12129, 2023): assignment of new issues to the most suitable
  contributor can be automated from textual + non-textual features (topic modelling), for bugs and
  features alike. → *the ledger's task_sha + cue classifier is the same mechanism at a smaller
  scale; assignment quality is measurable and improves with features, not with seniority labels.*

## Tensions

- **Self-organization vs single accountability.** Scrum/self-assignment say the team pulls; RACI,
  Oncken and RAPID say one named owner and one decider. Reconciliation for agents: the parent names
  the accountable owner and the acceptance check; the child may choose *how* within SCOPE, never
  *what* or *whether*.
- **Wide spans vs interaction explosion.** IT widened human spans from ~1:4 to ~1:10 (Wikipedia
  "Span of control"), but Graicunas (1933) showed cross-relationships grow superlinearly with n,
  and Conway favors small decoupled units. → *the human span number does not transfer; the
  interaction term does. Four concurrent children, not ten.*
- **Delegation level vs performance.** 10.2139/ssrn.4473848 finds no overall association, while
  10.2139/ssrn.4014546 finds centralization causes inertia. → *the effect is conditional on local
  information and metrics, which is exactly why every dispatch carries ACCEPTANCE and a verdict.*

## Implications for the harness (mapped)

| Org mechanism | Harness artefact | Rule in policy v3 |
|---|---|---|
| backlog / epic | `pi-agenda` tasks + goals | p1 bugs preempt; recurring work is a row |
| ticket + assignee | ledger row + `task_sha` + SCOPE | one owner per file; `pi-claim` before writes |
| definition of ready | six-field contract, `plan` check | <6 fields → no dispatch |
| WIP limit | `MAX_CONCURRENCY=4`, `MAX_PARALLEL_TASKS=8` | cap is a constraint, not a target |
| pull / self-assignment | ready queue + child picks within SCOPE | child chooses how, not what |
| RACI / RAPID | role table in policy §6 | parent = single Accountable + Decide |
| code review | `verifier` reproduces the check | evidence, not the worker's summary |
| integration / release | `integrator` owns hub files | one merge owner after fan-out |
| retrospective | `pi-delegate flow` + `report` weekly | PDSA cycle, gate before rule change |
| DORA lead time / rework | dispatch→verdict time; fail rate | flow metrics, not activity counts |
| theory of constraints | pace to verification/integration | don't fan out faster than you can check |

## What does not transfer

- Motivation, career incentives and agency problems (10.2139/ssrn.2443919) have no analogue in a
  stateless child; do not import "incentives" as prompt text.
- Human co-location and meeting cadence are irrelevant; what transfers is *information flow* and
  *ownership*, not ceremonies.
- Human span-of-control numbers (1:4–1:10) are about supervision bandwidth; the agent constraint is
  integration bandwidth and the dispatch floor, which is why the local cap is 4.
