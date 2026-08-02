# Engine Audit Findings — Schedule Engine v3

**Date:** 2026-08-01 (updated 2026-08-02)
**Auditor:** Claude (AI), directed by JC Iofalo
**Engine:** `schedule_engine_v3.py`
**Baseline:** Commit 0dff224 — 325 clashes, 95.1% placement
**Current:** Commit 03dde0a — 301 clashes, 95.1% placement, 0 graduation requirement clashes

---

## Summary

A code audit of the scheduling engine revealed 6 bugs, 4 improvements, and 3 design discoveries. All bugs have been fixed. The most impactful finding was BUG-6: graduation requirement misclassification caused World Language and Physical Education courses to be treated as electives. After all fixes: 301 clashes (down from 338), 95.1% placement, 0 graduation requirement clashes, all 5,033 grad req placements fulfilled.

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

### BUG-6: Graduation requirement misclassification (discovered 2026-08-02)

**Severity:** Critical — 127+ courses misclassified, false "100% grad req fulfillment" stat

Two bugs in `course_priorities.json` caused the engine to misidentify graduation requirements:

1. **"Language" vs "World Language"**: The `graduation_requirements.grades_9_10_11.required_departments` list used `"Language"` but Template 7's Department column uses `"World Language"`. The string comparison at `_is_grad_req_dept()` (line 110) failed — all World Language courses (Spanish I/II/III, Italian I/II, Latin) were treated as electives instead of graduation requirements.

2. **"Physical Education" missing entirely**: PE was not listed in any grade level's required departments, so Health/PE (610), Driver's Ed/PE (620), CPR-AED/PE (631), and Nutrition/PE (642) were all treated as electives.

The engine's "100% graduation requirement fulfillment" stat was incorrect — it was calculating correctly against the wrong list of departments. World Language had 87 affected clashes, PE had 40 affected clashes.

**Fix applied:** Two changes to `course_priorities.json`:
- Changed `"Language"` to `"World Language"` in `grades_9_10_11.required_departments`
- Added `grades_9_10_extra.additional_required_departments: ["Physical Education"]` for grades 9-10 only (PE is not required for grades 11-12 per school policy; exceptions exist for Band/Orchestra students in grades 9-10)

Engine code change in `schedule_engine_v3.py`: `GRAD_REQ_DEPTS` construction (line 64) now merges the `grades_9_10_extra` departments into grades 9 and 10 only.

**Impact:** 338→301 clashes, 94.5%→95.1% placement. Graduation requirement fulfillment is now genuinely 100% (5,033/5,033).

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

Fixes were applied in this order:

1. **BUG-1 + DISC-3** — Implemented four-level pyramid system (Graduation Required > No Alternative > Limited Choice > Flexible)
2. **BUG-2** — Aligned `full_reseat()` ordering with pyramid system
3. **BUG-3 + BUG-4** — Priority-aware acceptance + Phase D selection
4. **IMP-1** — Deeper optimization (60 iterations, 16 candidates, stall limit 8)
5. **IMP-2 + IMP-3** — Post-bump CSP recovery + per-restart seating recomputation
6. **BUG-5** — Dead code removed
7. **IMP-4** — Priority-weighted conflict estimation
8. **BUG-6** — Graduation requirement misclassification fix (2026-08-02)
9. **DOC** — All project documents updated

---

## Resolution Status

All findings have been resolved.

| Finding | Status | Result |
|---------|--------|--------|
| BUG-1: Phase B seating regression | FIXED | Four-level pyramid replaces single-tier |
| BUG-2: full_reseat() ordering | FIXED | Consistent with Phase B pyramid ordering |
| BUG-3: Priority-blind optimization | FIXED | Priority-aware acceptance prevents P5 trade-ups |
| BUG-4: Conflict risk dual definition | FIXED | Single definition, any period overlap |
| BUG-5: PROT/PROT_P4 dead code | FIXED | Dead code removed |
| BUG-6: Graduation req misclassification | FIXED | "World Language" match + PE added for grades 9-10 |
| IMP-1: Deeper optimization | APPLIED | 60 iterations, 16 candidates, stall 8 |
| IMP-2: Post-bump CSP recovery | APPLIED | Recovers seats after bumping |
| IMP-3: Per-restart recomputation | APPLIED | Each restart gets ordering tuned to its period layout |
| IMP-4: Priority-weighted estimation | APPLIED | Optimizer penalizes high-priority conflicts |
| DISC-1: Grade-dependent P5 | DOCUMENTED | Correct per graduation rules — not a bug |
| DISC-2: AP elective weight | RESOLVED | Level 2 (No Alternative) in pyramid system |
| DISC-3: Three-band system | SUPERSEDED | Four-level pyramid system implemented |

### Final Results

| Metric | Baseline | After All Fixes |
|--------|----------|-----------------|
| Clashes | 325 | **301** |
| Placement | 95.1% | **95.1%** |
| Graduation Req Clashes | Unknown (bug) | **0** |
| Grad Req Fulfillment | Unknown (bug) | **100% (5,033/5,033)** |
| AP/Honors Fulfillment | Unknown | **100% (2,104/2,104)** |
| P4+ Clashes | 0 | **0** |

---

## Test Protocol

After each fix:
1. Run engine and record: total clashes, P4+ clashes, placement rate, grad req fulfillment
2. Compare to baseline (325 clashes, 95.1%)
3. Verify P4+ clashes remain at 0
4. Verify graduation requirement fulfillment remains at 100%
5. If P4+ clashes appear, revert and investigate before proceeding
