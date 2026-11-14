---
description: Run one PDSA improvement cycle on a system (plan → do → study → act, with a measured metric)
argument-hint: "<system or subsystem> [metric to move]"
---

Run one full PDSA cycle on: ${1:-the system I'm currently working on}
Target metric/behaviour to improve: ${2:-the most user-visible weakness I can measure}

Procedure — do the work, don't describe it:

1. **Recall first**: `mem brief`, then `mem search "<system name>"` for prior cycles, decisions and
   lessons about this system. If an open cycle exists for it, continue that cycle instead of opening
   a duplicate.
2. **Plan** — state a falsifiable hypothesis and the exact metric that would refute it, plus the
   current baseline value. Record it: `mem pdsa new --plan "..."`. If the system has no measurement
   harness, build the smallest one first (a fixed case list + one command that prints numbers) —
   a cycle without numbers is not a cycle.
3. **Do** — make the smallest change that tests the hypothesis. Keep it revertible (commit or note
   the diff), and don't bundle unrelated improvements into the same cycle.
4. **Study** — measure before/after on the same harness, including cost side effects (latency,
   tokens, disk, complexity). State the delta in numbers and explain *why* it moved; investigate any
   result that is too good to be true (check for a broken measurement before celebrating).
5. **Act** — decide: keep / revert / next hypothesis. Write it down:
   `mem pdsa update --cycle N --do "..." --study "..." --act "..." --metric-before X --metric-after Y --status closed`,
   and open the next cycle with the new hypothesis (leave it open).
6. **Persist** — `mem add` the durable lesson (kind=lesson) so future sessions inherit it, and update
   the system's own doc (AGENTS.md / SKILL.md / README) if behaviour changed.

Report: metric before → after, what you changed, what you reverted and why, and the open next cycle.
