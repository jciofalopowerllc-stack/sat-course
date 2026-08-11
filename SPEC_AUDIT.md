# SPEC_AUDIT.md — Codebase Audit Against Transfer Specification

**Audited file:** `schedule_engine_v3.py` (~9,500 lines)  
**Spec:** `MASTER_SCHEDULE_BUILDER_TRANSFER_SPEC.md` (Sections 2–8)  
**Evidence:** `DBP_SCHEDULE_OPTIMIZER_EVIDENCE_08_11_26.xlsx`  
**Date:** 2026-08-11  

---

## THE HEADLINE

The Schedule Optimizer placed **98.0% of requests with 0 conflicts**.  
This engine places **87.3% of requests with 833 conflicts**.

The spec predicted exactly where the divergence would be. Every major violation found below maps to a specific gap the spec warned about.

---

## SECTION 2 — THE PRIORITY MODEL

### 2.1 Four tiers, fixed — **VIOLATED**

The engine does not use four named tiers. It uses a **9-component additive point system** where graduation requirements, AP status, singleton status, cohort membership, co-schedule membership, semester-only status, prescribed term status, counselor priority level, and Gr12 PAE are all collapsed into a single number.

Point constants (lines 1252–1265):

```
PTS_AP = 30
PTS_SINGLETON = 25
PTS_GRAD_REQ = 30
PTS_GR12_PAE = 20
PTS_SEMESTER_ONLY = 10
PTS_COHORT_COURSE = 15
PTS_COSCHEDULE = 15
PTS_PRESCRIBED_TERM = 10
PTS_PRIORITY_LEVEL = {5: 20, 4: 15, 3: 10, 2: 5, 1: 0}
```

A graduation requirement scores +30. An AP semester co-scheduled elective with counselor MANDATORY priority scores 30+10+15+20 = **75** — more than double the graduation requirement. The spec calls this exact pattern out in Section 1:

> *"If the code computes anything resembling `score = w1*gradReq + w2*pathway + w3*apHonors + w4*elective` and then maximizes total score, it is structurally capable of leaving a senior one credit short of graduating in order to place three students into AP Studio Art."*

**This is exactly what the engine does.**

### 2.2 Strict lexicographic ordering — **VIOLATED (the single most important violation)**

The spec requires: maximize Tier 1 placements to completion → freeze → Tier 2 → freeze → Tier 3 → Tier 4. *"A higher tier is never traded for any quantity of a lower tier."*

The engine does the opposite. All student-course pairs are sorted into **one list** by `course_request_priority` and placed greedily in order (Phase B, lines 6080–6110):

```python
def _full_sort_key(pc):
    pid, cid = pc
    return (
        -course_request_priority(pid, cid),   # single numeric score
        -student_total_priority(pid),
        -course_section_raw(cid),
        len(sec_by_code.get(cid, []))
    )

_all_requests.sort(key=_full_sort_key)
```

There is no tier separation. Graduation requirements and electives compete in the same sorted list. The engine's own diagnostic (lines 633–645) acknowledges this:

> *"a Grade 12 elective with CRP=40 can be placed before a Grade 9 student's grad req with CRP=20. The elective fills a period cell that the Grade 9 student needed."*

**Impact:** This is the structural reason for the 833 conflicts. The weighted system allows high-scoring electives to consume period slots that graduation requirements need. The Schedule Optimizer's lexicographic model prevents this by construction.

### 2.3 The fairness guard — **NOT ADDRESSED**

No worst-served-student pass exists. No maximin or leximin logic. No check for students left with 0 or 1 placements. The engine places in strict priority order — students with lower `student_total_priority` absorb whatever capacity remains.

A grep for `worst`, `maximin`, `leximin`, `fairness`, `underserved` returned zero algorithmic constructs.

### 2.4 Scarcity as a within-tier tiebreak — **PARTIALLY SATISFIED**

Scarcity is partially captured via `PTS_SINGLETON = 25` (singletons get +25) and `len(sec_by_code[code])` as the last tiebreaker in the sort key (fewer sections = placed earlier). However:

- Scarcity is computed as **section count**, not as **available seats across all sections** as the spec requires.
- It is an additive point component, not a within-tier tiebreak — it participates in the cross-tier scoring that Section 2.2 prohibits.

---

## SECTION 3 — POLICY IS DATA, NEVER CODE, NEVER INFERENCE

### 3.1 Never infer classification from a course title — **SATISFIED**

The engine does not use regex, title parsing, or string matching on course names to determine priority, tier, or requirement status. All classification is driven by structured data columns from `Engine_Templates_With_Data.xlsx`:

- **AP status:** T1 Column 11, Y/N flag (line 1720)
- **Singleton status:** T1 Column 9, Y/N flag (lines 1287–1294)
- **Graduation requirement:** T1 Column 12 + T10 worksheet (lines 1313–1329)
- **Department:** T1 Column 3 (line 1343)

One hardcoded set exists: `_GR12_PAE_DEPTS = {'English', 'Mathematics', 'Science', 'Social Studies', 'Language'}` (line 1355). This is a fixed set of department name strings, not a regex, but it is policy in code — see 3.3.

### 3.2 Graduation requirements are counted in years — **VIOLATED**

The spec requires: *"The student needs N years of this subject, and this course provides one of them."* Tier depends on transcript history.

The engine uses a **department membership flag**, not years-completed counting:

```python
def _is_grad_req_for_student(cid, student_grade, pid=None):
    if pid and (str(pid), str(cid)) in _STUDENT_PRIO_OVERRIDES:
        return True
    dept = _course_dept_map.get(str(cid), '')
    return dept in GRAD_REQ_DEPTS.get(student_grade, set())
```
(lines 1349–1353)

"Is this course's department required for this grade level?" — that's the entire check. No transcript history, no counting of years already completed, no knowledge that a student has already satisfied their 3-year language requirement.

Consequences the spec warned about that this engine cannot handle:

- ❌ AP Calculus BC is Tier 1 for a senior needing a 4th math year; AP Statistics for that same senior is Tier 3. **Engine marks both as graduation requirements.**
- ❌ The same course is a different tier for different students in the same section. **Engine uses a single classification per course per grade.**
- ❌ AP language courses are 4th-year electives at a school with a 3-year requirement. **Engine marks all language courses as grad-req for all language-required grades.**
- ❌ Exactly-one resolution when multiple courses can complete the same requirement. **Engine marks all of them as grad-req.**

### 3.3 Everything above must be editable configuration — **PARTIALLY VIOLATED**

The graduation requirement structure is mostly data-driven via T10 (`GRAD_REQ_DEPTS`). However:

- `_GR12_PAE_DEPTS` is **hardcoded** (line 1355) — not in any template
- The 39-row `_STUDENT_PRIO_OVERRIDES` (T12) is a manual patch for the year-counting gap — each override is a specific student×course pair that should be grad-req but isn't detected by the department check
- Fractional requirements (3.5 years Social Studies) are not supported
- Requirement families (3 years of "a world language") are not supported

Audit test from spec: *"If a school required 2 years of language and 4 of science, how many files would have to change?"*  
**Answer: At least T10 (template), plus T12 (manual overrides), plus the hardcoded `_GR12_PAE_DEPTS` set in the engine code. The policy is partially in the code.**

---

## SECTION 4 — HARD CONSTRAINTS

### 4.1 Teacher load — **PARTIALLY SATISFIED**

**Per-semester max load:** SATISFIED. `teacher_would_exceed_cap()` (lines 3542–3553) enforces per-semester caps. `ABSOLUTE_MAX_PERIODS_PER_SEMESTER = 6` (line 3539).

**Per-term 6th-period approval:** SATISFIED. `get_max_load()` (lines 2878–2896) returns `(max_s1, max_s2)` using T2 columns for FY/S1/S2 approval. A teacher approved for S1 only is not approved for S2.

**Semester balance (S1/S2 gap ≥ 2 is invalid):** **NOT ADDRESSED.** No constraint prevents a teacher from having S1=5, S2=3 (gap of 2). The EC rebalancing logic (lines 3150–3234) flips sections to keep teachers within per-semester caps, but does not enforce a maximum gap between semesters.

### 4.2 Co-scheduled blocks count as ONE period — **SATISFIED**

Extensively implemented. Co-schedule groups are tracked via `code_to_cogroup`, and load counting explicitly groups co-scheduled sections. Bug B20 (fixed) addressed the counting logic in `_teacher_aware_ec_rebalance()`. The `teacher_raw_priority()` function groups co-scheduled sections correctly.

Seven co-schedule blocks are defined: Guitar, Programming, Robotics, Italian, Theater, AP Art, Studio Art. All move together.

### 4.3 Rooms — **PARTIALLY SATISFIED**

- **Room capacity as hard cap:** SATISFIED. `sections[sid]['cap']` is enforced during placement.
- **Prescribed rooms honored:** SATISFIED. T7 Column 10 prescribes rooms; `room_busy()` prevents double-booking.
- **Non-shared rooms restricted to prescribed teacher:** **NOT IMPLEMENTED.** The CLAUDE.md documents this as paused work ("⏸️ PAUSED WORK: Room Ownership & Exclusivity System"). Currently any section can use any free room. The 6 exclusive rooms identified by JC (Gym, S-338, I-111, J-223, J-120, Success Center) are not enforced.
- **Room eligibility sets:** **NOT IMPLEMENTED.** No course-type → room-category restriction.

### 4.4 Cohort integrity — **PARTIALLY SATISFIED**

LEO I and LEO II cohorts exist as student groups loaded from T3 (lines with `LEO_II`, `LEO_A`, `LEO_B` flags). The T13 anchor pair system handles cohort-specific placement patterns. However:

- There is no general-purpose **cohort object** that binds a named set of students to a course with configurable term and section constraints.
- The LEO cohort handling is specific to Don Bosco's structure, not a reusable mechanism.

### 4.5 Section capacity with controlled flex — **NOT ADDRESSED**

No +2 bounded flex exists. The engine uses a strict binary check: `secfill[sid] < sections[sid]['cap']` (line 6139). When a section is full, it is excluded from placement options. There is no mechanism to raise a cap by +2 for otherwise-unplaceable requests, and no audit trail for flex usage.

In unlimited mode, all caps are set to 9999 — this is a diagnostic override, not a bounded flex.

### 4.6 Seats are not reserved for the future — **SATISFIED**

The engine maximizes current-year placement. No seat reservation mechanism exists.

---

## SECTION 5 — IDENTITY AND DATA JOINS

### 5.1 Every join reports its match rate — **PARTIALLY SATISFIED**

The pre-flight validation (lines 2299–2800) checks for:
- Duplicate requests
- Missing prerequisites
- Grade-level eligibility
- Under-enrolled students
- Requests against nonexistent courses

Match rates are reported for several joins (e.g., "Students (from T5): 804"). However, there is no explicit halt on a 0% join match. The engine would proceed with an empty result in some edge cases.

### 5.2 Fallback matching keys — **NOT ADDRESSED**

All matching is by numeric ID only. No name-based fallback with fuzzy handling for case, whitespace, or `Last, First` vs `First Last`.

### 5.3 Pre-flight validation — **SATISFIED**

A comprehensive pre-flight validation stage runs before optimization (lines 2299–2800), producing `Preflight_Validation_Report.xlsx`. It checks courses, teachers, rooms, students, prerequisites, grade eligibility, credit loads, and constraint chains. 1,094 warnings are generated.

### 5.4 Active roster reconciliation — **PARTIALLY SATISFIED**

The engine loads students from T3 and T5 and cross-references them. The CLAUDE.md documents a case where an inactive student (Hinspeter) was discovered. However, there is no formal active/inactive roster reconciliation — the engine schedules whoever appears in the request file.

---

## SECTION 6 — DIAGNOSTICS

### 6.1 Failure attribution — **PARTIALLY SATISFIED**

The Job 2 output includes an "Unscheduled Requests" sheet with root cause per unplaced request. The SIR (System Improvement Report) identifies blocking courses. However, the structural cause tags from the spec are not used:

- ❌ `single-teacher course` — not tagged (though the SIR reports teacher bottlenecks)
- ❌ `singleton section` — not tagged
- ❌ `grade-level congestion` — not tagged
- ❌ `block locked to one period` — not tagged
- ❌ `catalogue gap` — partially addressed (preflight catches nonexistent courses)

### 6.2 Structural metrics — **PARTIALLY SATISFIED**

| Metric | Spec requirement | Engine status |
|--------|-----------------|---------------|
| Seat utilization | Required | ✅ Section Fill sheet in Job 2 output |
| Under-enrolled sections | Required | ❌ Not reported |
| Single-teacher exposure | Required | ❌ Not reported (SIR mentions teachers but no systematic count) |
| Full-year vs semester exposure | Required | ❌ Not reported |
| Period-level congestion | Required | ✅ Period Distribution sheet in Job 1 output |
| Catalogue integrity | Required | ✅ Preflight catches requests against nonexistent courses |

### 6.3 Prescriptive output — **PARTIALLY SATISFIED**

The SIR generates specific recommendations with teacher details and schedule previews. However, the recommendations are generated as console output, not embedded in the export workbook.

---

## SECTION 7 — HUMAN-IN-THE-LOOP AND THE RULINGS LEDGER

### **NOT ADDRESSED**

No rulings ledger exists. No exception queue. No mechanism to:
- Detect ambiguity and halt
- Present choices to an administrator
- Record decisions persistently
- Apply recorded decisions on subsequent runs
- Embed rulings in the export

The engine resolves ambiguities silently using its priority scoring. When contradictory data exists (e.g., two courses could satisfy the same requirement), the engine picks whichever scores higher — there is no detection, no halt, no recording.

---

## SECTION 8 — OUTPUT AND DELIVERABLE DESIGN

### **VIOLATED**

The engine produces **multiple separate files**, not one consolidated workbook:

- `Job1_Section_Placements_2026_27.xlsx` (5 sheets)
- `Job2_Student_Placements_2026_27.xlsx` (4 sheets)
- `Preflight_Validation_Report.xlsx`
- `Master_Section_Report_2026_27.xlsx`
- `Teacher_Schedule_Review_and_Tally.xlsx`
- `Remaining_Conflicts_v2.5.xlsx`
- `Student_Schedule_Report_2026_27.xlsx`
- `Incomplete_Student_Schedules_2026_27.xlsx`
- `Course_Request_Report_2026_27.xlsx`
- `Engine_Analysis_Report.xlsx` (8 sheets)
- `Unlimited_Seat_Analysis_2026_27.xlsx` (6 sheets)
- `schedule_solution_v3.json`
- `priority_audit_log.json`
- `run_diagnostics.json`

This is exactly the "sprawl of separate files" the spec identifies as the largest complaint.

No build versioning. No rules ledger embedded in exports. No self-describing metadata in exports.

---

## CONFLICT DEFINITION — THE FOUNDATIONAL DIVERGENCE

This is not in a numbered section but it is **the most important finding**.

The Schedule Optimizer defines a student period conflict as **an invalid state** — the schedule is not a schedule if it contains one. Target: 0.

This engine defines a student period conflict as **a penalty to minimize** — the engine places students into conflicting sections and counts the conflicts afterward. The placement code (lines 6142–6146):

```python
chosen_sid = min(opts, key=lambda sid: (
    added_conflicts(pid, sid),       # minimize conflicts (soft preference)
    max(0, secfill[sid] + 1 - sections[sid]['cap']),
    secfill[sid]
))
```

The engine prefers lower-conflict placements but **does not reject** a placement that creates a conflict. If all available sections of a course cause conflicts, the student is placed anyway.

This is why 833 conflicts exist. The Schedule Optimizer would have left those students unscheduled in that period rather than double-booking them.

---

## GAP RANKING (by impact on output quality)

| Rank | Gap | Section | Impact |
|------|-----|---------|--------|
| **1** | **Conflicts are penalties, not invalid states** | — | The entire 833-conflict count. This is not an optimization problem — it is a constraint enforcement problem. |
| **2** | **Weighted scoring instead of lexicographic tiers** | 2.2 | Graduation requirements lose slots to high-scoring electives. Structurally prevents the engine from guaranteeing grad-req placement. |
| **3** | **No year-counting for graduation requirements** | 3.2 | Every course in a required department gets the +30 boost, regardless of whether the student has already satisfied the requirement. Over-marks courses as grad-req → wastes priority on students who don't need it. |
| **4** | **No fairness guard** | 2.3 | A handful of students can end up with 1-2 of 7 requests while others get 7/7. No mechanism to detect or correct this. |
| **5** | **No semester balance constraint** | 4.1 | Teachers can have 5/3 or 6/4 loads. The Schedule Optimizer prevented this. |
| **6** | **No +2 section cap flex** | 4.5 | Requests that could be saved by seating 2 extra students are lost. |
| **7** | **No exclusive room enforcement** | 4.3 | Rooms assigned to wrong teachers (paused work). |
| **8** | **File sprawl** | 8 | User experience issue. Multiple files instead of one consolidated workbook. |
| **9** | **No rulings ledger** | 7 | Ambiguities resolved silently. No audit trail. |
| **10** | **Incomplete diagnostics** | 6 | Missing under-enrolled, single-teacher, FY-exposure reports. |
