# Engine Audit Findings — Schedule Engine v3

**Date:** 2026-08-01
**Auditor:** Claude (AI), directed by JC Iofalo
**Engine:** `schedule_engine_v3.py`
**Baseline:** Commit 0dff224 — 325 clashes, 95.1% placement

---

## Summary

A code audit of the scheduling engine revealed 5 bugs, 4 improvements, and 3 design discoveries. The most impactful finding is that the Phase B seating refactor (commit 0dff224) regressed clash count from ~207 to ~325 by changing the order in which courses are placed onto the grid.

---

## Critical Bugs

### BUG-1: Phase B seating order regression (Task #1)

**Severity:** Critical — caused ~118 additional clashes

The Phase B refactor replaced tier-based seating (`P5 first → P4 → P3 → ...`) with composite-scored seating (`grad reqs first → electives`). This moved pure-elective P5 courses (AP Art, AP CS, AP Cyber) behind ALL graduation requirements.

- **Old:** P5 singletons placed first on a wide-open grid → guaranteed no conflict
- **New:** P4 grad-reqs with 8+ sections placed first → fill periods → P5 singletons find their only option blocked

### BUG-2: full_reseat() ordering inconsistent with Phase B (Task #2)

**Severity:** High — affects every Phase D restart

`_reseat_course_order` sorts by `placement_sort_key` only. Phase B initial seating sorts by `-student_prio` first. Every `full_reseat()` call (16+ per engine run) uses the weaker ordering.

### BUG-3: Optimization acceptance is priority-blind (Tasks #3, #4)

**Severity:** High — can introduce P5 clashes during optimization

Both `run_optimization_pass()` and Phase D best-solution selection compare raw clash count only. A move that trades P1 clashes for P5 clashes is accepted as an improvement.

### BUG-4: _compute_conflict_risk() dual definition (Task #5)

**Severity:** Medium — CR input is severely undercomputed

Two function definitions exist. The active one (line ~1096) only counts risk when ALL sections of two courses share a SINGLE period. The spec says it should count ANY period overlap.

### BUG-5: PROT/PROT_P4 dead code (Task #9)

**Severity:** Low — no functional impact, but misleading

Sets are computed and named as if they protect courses, but are never referenced in any decision logic.

---

## Improvements Identified

### IMP-1: Deeper optimization search (Task #6)

Increasing from 40→60 iterations, 8→16 candidates, stall 5→8 reduced clashes by ~40 in testing. Requires priority-aware acceptance (BUG-3 fix) first.

### IMP-2: Post-bump CSP recovery (Task #7)

After bumping, re-add the course and run CSP backtracking to try rearranging section assignments. Recovers placements the greedy pass misses.

### IMP-3: Per-restart seating order recomputation (Task #8)

CR scores depend on period assignments. Recomputing seating order after each `greedy_assign_periods()` seed gives each restart an ordering tuned to its specific period layout.

### IMP-4: Priority-weighted conflict estimation (Task #12)

The optimizer's `new_conf` estimation should penalize moves that create conflicts with P5/singleton courses more heavily.

---

## Design Discoveries

### DISC-1: Grade-dependent P5 vulnerability (Task #10)

7 AP courses (AP Bio, AP Chem, AP Physics 1, AP Physics C, AP Spanish, AP Italian, AP Latin) are P5 for grades 9-11 but drop to pure-elective status (student_prio=5) for grade 12 because their departments aren't required in 12th grade. This is correct per graduation requirements but makes them vulnerable.

### DISC-2: AP electives need higher weight than regular electives (Task #11)

**Per user direction:** AP non-grad-req courses (AP Art, AP CS, AP Cyber, Academic Support, plus grade-12 AP Sciences/Languages) are non-substitutable but get the same student_prio as regular electives. They need a middle band or boost.

### DISC-3: Three-band priority system needed

The current two-band system (100+ grad req, 0-5 elective) doesn't capture the reality that AP electives are more constrained than regular electives. A three-band system would be:

| Band | Score Range | Description |
|------|------------|-------------|
| Band 1 | 100+ | Graduation requirements (current GRAD_REQ_BAND) |
| Band 2 | 50-55 | AP/Singleton electives — non-substitutable, limited sections |
| Band 3 | 0-5 | Regular electives — flexible, multiple alternatives |

---

## Fix Application Order

Fixes must be applied in this order to avoid regressions:

1. **BUG-1 + DISC-3** — Implement three-band priority system (most impactful)
2. **BUG-2** — Align `full_reseat()` ordering with new band system
3. **BUG-3 + BUG-4** — Priority-aware acceptance + Phase D selection
4. **IMP-1** — Deeper optimization (safe after priority protection is in place)
5. **IMP-2 + IMP-3** — Post-bump recovery + per-restart recomputation
6. **BUG-5** — Remove dead code
7. **IMP-4** — Priority-weighted estimation
8. **DOC** — Update all project documents

---

## Test Protocol

After each fix:
1. Run engine and record: total clashes, P5 clashes, placement rate
2. Compare to baseline (325 clashes, 0 P5, 95.1%)
3. Verify P5 clashes remain at 0
4. If P5 clashes appear, revert and investigate before proceeding
