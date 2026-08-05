# Don Bosco Prep 2026-27 Master Schedule Builder

## Project Rules

### Absolute Rules (from JC Iofalo — non-negotiable)
1. Follow JC's instructions exactly — no assumptions, no improvisation
2. Ask before making ANY design decision — do not change the design on your own
3. Stop immediately when told to stop — no extra tool calls, no "one more thing"
4. Do not claim to understand something when you do not — ask instead
5. Be 100% honest and accurate — facts and solutions only, no false reassurance
6. Every file edit must be immediately followed by commit and push in the same response — no batching, no waiting
7. Read and follow DATA_STRUCTURE.md before writing any engine code — the data structure defines the priority system, implement it exactly
8. Identify and fix your own mistakes proactively — do not wait for JC to find them

### Engine Architecture (from JC Iofalo — non-negotiable)
- Use **schedule_engine_v3.py** (v3 engine) — NOT v4
- Do NOT change template FORMAT — only add/update data within existing columns
- Do NOT make decisions without user (JC Iofalo) approval

**The engine has TWO distinct jobs that run in order, with a mandatory review gate between them:**

1. **Job 1 — Course Section Placement (runs FIRST):**
   - Place course sections (with their assigned teachers and rooms) into the master bell schedule by Term (FY, S1, S2) and Period (A-G)
   - BEFORE placing, the engine MUST analyze priority values for students, teachers, rooms, AND courses
   - Use that analysis to DECIDE the most optimal position (period + term) for each course section with its teacher and room
   - Goal: position sections to AVOID student conflicts before students are ever placed
   - Per-placement cycle: PLACE → SAVE priority values → REMOVE consumed values → RECALCULATE all remaining → RE-RANK → next placement
   - **After Job 1 completes, the engine STOPS and exports `Job1_Section_Placements_2026_27.xlsx` for JC to review**
   - **Engine does NOT proceed to Job 2 until JC gives one of three commands:**
     - **Re-run Job 1** (run again with same or different parameters)
     - **Revise Job 1** (make manual adjustments to section placements)
     - **Start Job 2** (proceed to student enrollment)

2. **Job 2 — Student Placement (runs SECOND, only after Job 1 is reviewed and approved):**
   - Place students into the already-positioned course sections
   - Do NOT run student placements until Job 1 is verified correct
   - Per-placement cycle: PLACE → SAVE priority values → REMOVE consumed values → RECALCULATE all remaining → RE-RANK → next placement
   - **After Job 2 completes, the engine exports `Job2_Student_Placements_2026_27.xlsx` for JC to review**

### Three-Tier Section Placement (Universal Rules — from JC Iofalo, non-negotiable)
The engine places course sections in three tiers. These tiers control the ORDER of placement in `greedy_assign_periods()`. Priority values are used WITHIN each tier to rank sections.

1. **Tier 1 — Grade 12 Singletons (placed FIRST):**
   - Sections of courses eligible for Grade 12 (per Template 7 "Grade Levels") with exactly 1 section
   - Placed according to priority values
   - **ZERO student conflicts** — the engine MUST place these in periods with no student scheduling conflicts
   - Co-scheduled sections are essentially one section and are NOT counted as conflicts

2. **Tier 2 — Grade 12 Doubletons (placed SECOND):**
   - Sections of courses eligible for Grade 12 with exactly 2 sections
   - Placed according to priority values
   - **ZERO student conflicts** — same hard constraint as Tier 1
   - Co-scheduled sections are essentially one section and are NOT counted as conflicts

3. **Tier 3 — All Other Sections (placed LAST):**
   - All remaining sections (Grade 12 courses with 3+ sections, and all non-Grade-12 courses)
   - Placed according to priority values
   - Weighted conflict scoring (not a hard zero-conflict constraint)

**Why this works:** Grade 12 students are in their last year — they cannot retake a missed course. Singletons have no alternative section. Doubletons have minimal flexibility. By placing these first with zero conflicts, the engine guarantees Grade 12 access to their most restricted courses before any other placement decisions consume schedule slots.

**Co-schedule rule:** Co-scheduled sections share the same teacher, room, and period by design. They are essentially one section. A student enrolled in two co-scheduled courses is NOT in conflict — the co-schedule IS the schedule. The engine excludes co-scheduled courses from conflict scoring in `_predict_conflict_score()`.

### Engine Run Modes
- `python schedule_engine_v3.py` or `python schedule_engine_v3.py job1` — Run Job 1 only, export Excel, **STOP** for review
- `python schedule_engine_v3.py full` — Run Job 1 + Job 2 (student placement), export both Excel reports
- `python schedule_engine_v3.py analyze` — Analyze Job 1+2 outputs, generate `Engine_Analysis_Report.xlsx` (requires prior `full` run)
- `python schedule_engine_v3.py unlimited` — Run Job 1 + Job 2 with **unlimited section caps** (diagnostic mode), export `Unlimited_Seat_Analysis_2026_27.xlsx` showing natural demand per section to identify which sections need splitting or moving
- `python schedule_engine_v3.py gr12` — Run Job 1 + Job 2 for **Grade 12 only**: filters to Gr12-eligible course sections + Grade 12 students only, exports `Job1_Section_Placements_GR12_2026_27.xlsx` and `Job2_Student_Placements_GR12_2026_27.xlsx`
- Default mode is `job1` — the engine will never proceed to Job 2 without explicit approval

### Term Type & Prescribed Term Architecture (REV 08.04.26)
- **Two distinct concepts, two distinct templates:**
  - **Template 7 Column D "Term Type"** — describes WHAT a course IS: `FY` (full-year, 5.0 credits) or `S` (semester, 2.5 credits). Classification only — does NOT control placement.
  - **Template 7 Column E "Term Credits"** — validation failsafe: FY must pair with 5.0, S must pair with 2.5 (0 allowed for special courses like 955 Academic Support).
  - **Template 6 Sheet 2 Column E "Prescribed Term"** — REQUIRED field, describes WHERE a specific section GOES: `FY`, `S1`, `S2`, or `EC` (Engine Choice). This is the **single authoritative source** for per-section semester placement.
- **Prescribed = Required** (same as prescribed room and prescribed period):
  - `FY` → engine MUST place section as full-year (S1+S2)
  - `S1` → engine MUST place section in S1 only
  - `S2` → engine MUST place section in S2 only
  - `EC` → engine MAY place section in either S1 or S2 (Engine Choice — engine decides which is optimal)
- **Cross-validation rule:** T7 Term Type=FY requires T6 Prescribed Term=FY; T7 Term Type=S requires T6 Prescribed Term=S1/S2/EC. Mismatch = engine validation error.
- **EC redistribution:** EC sections are distributed evenly across S1/S2 by the engine (n_s1 = (n+1)//2)
- **Eliminated:** `SEMESTER_LOCKS` dict, `FULL_FREEDOM` set, `semester_designations.json` — all replaced by T6 Column E as sole authority
- **Distribution (371 sections):** FY=245, S1=15, S2=14, EC=97

### Teacher Section Prescriptions (2026-27)
- **Chiaravalloti, Michael (105747)**: 631 CPR-AED Training/PE × 4 semester sections + 642 Nutrition & Fitness/PE × 6 semester sections = 10 total (5 per semester); Daniels (105763) also teaches 631 × 2 semester sections (6 total 631 sections)
- **Fisk, Mary Pat (105819)**: 131 British Literature H × 3 full-year sections
- **Kozak, Bernadette (105628)**: 595 Engineering Design × 2 semester sections (1 S1 + 1 S2)
- **Laracy, John (106760)**: 851 Spirituality of Vocation × 8 semester sections
- **Umbrino, Philip (105768)**: 130 British Literature × 3 full-year sections (added to existing pool)
- **Lopez, Enrique (102255)**: 201 Introduction to Guitar × 2 semester sections (co-scheduled with 203 Guitar Ensemble, same period/room); 203 Guitar Ensemble is full-year (5 credits, 2 sections)
- **Tranate, John (105746)**: 557 AP Physics 1 × 2 sections (typo corrected from 556→557 in Template 6)
- **Dennehy (105810)**: 248 Adv Drawing × 1 semester section, Room J-322
- **Granieri, William (122120)**: 849 Catholic Social Teaching × 8 semester sections + 830 Theology 11 × 1 section (reassigned from 810/820/830 to TBD Theology teacher)
- **TBD Theology, New (999999)**: Placeholder for new hire — 810 Theology 9 × 3 + 820 Theology 10 × 2 (transferred from Granieri). Replace with real name/ID when available.
- **Saggio, Jack (117711)**: 723 Introduction to Political Science × 1 semester section
- Sections defined in Template 6 Sheet 2 ("Teacher-Course Assignments"), one row per section

### Grade 12 Science Requirement Exceptions (2026-27)
- 39 specific Grade 12 student-course pairs are treated as **graduation_required** priority even though Science is not a standard Gr12 required department
- Courses affected: 543 Anatomy/Physiology H (9 students), 546 Forensics (27 students), 530 Physics (1 student), 531 Physics H (2 students)
- Defined in `student_priority_overrides.json`, loaded by engine at startup
- Engine's `course_request_priority()` and `_is_grad_req_for_student()` check these overrides

### Room Assignment Rules
- Sections without a prescribed room may be placed into any room that is free for that period and term
- Prescribed rooms are NOT exclusively reserved — they are available to other sections in any period/term when the prescribed section is not using them
- 66 of 371 sections have no prescribed room — this is correct (not a data gap)

### Key Files
- `schedule_engine_v3.py` — Main engine (4-phase: Period Assignment → Student Seating → Bump Conflicts → Optimization)
- `course_priorities.json` — Graduation requirements, pathway courses, singleton courses
- `detect_pathways.py` — Pathway detection from Historical Grades + Course Requests
- `templates/` — All input templates (T2, T4, T6, T7, T8, T9, Prior Year, Historical Grades)
- `templates/202526_Master_Schedule_With_Teacher_ID.xlsx` — Official 2025-26 master schedule with teacher names and IDs
- `student_priority_overrides.json` — Student-specific priority overrides (Grade 12 science exceptions)
- `schedule_solution_v3.json` — Engine output
- `priority_audit_log.json` — Per-placement priority audit trail (Phase A + Phase B)
- `Reports.md` — Report format reference (column layouts, sort orders, features)

### Job Review Exports
- **`Job1_Section_Placements_2026_27.xlsx`** — Job 1 output for review before Job 2 starts
  - Sheet 1 "Section Placements": One row per section in placement order — Step, Course Code, Title, Section #, Dept, Teacher, Teacher ID, Room, Period, Term, CS Raw, Top Student Total, Teacher Raw/Total, Room Raw/Total, CS Total, Cap, Co-Schedule Group, Prescribed Cohort
  - Sheet 2 "Period Distribution": Sections per period broken down by S1/S2/FY
  - Sheet 3 "Teacher Loads": Per-teacher S1/S2 period counts vs max load, overload flag
  - Sheet 4 "Teacher Conflicts": Any teacher double-booked in same period+semester (co-scheduled pairs marked)
  - Sheet 5 "Summary": Totals, assigned/unassigned counts, period distribution
- **`Job2_Student_Placements_2026_27.xlsx`** — Job 2 output for review after student enrollment
  - Sheet 1 "Student Placements": One row per student-course placement — Student ID/Name/Grade, Course Code/Title/Section, Period, Term, Teacher, Room, CRP, Student Raw/Total, CS Raw, Fill/Cap/%; **UNSCHEDULED rows** in bold red for empty period slots with correct term (FY if both S1+S2 empty, S1-only, or S2-only)
  - Sheet 2 "Unscheduled Requests": Student-course pairs not placed, with CRP and root cause
  - Sheet 3 "Section Fill": Per-section enrollment vs capacity with fill percentage
  - Sheet 4 "Summary": Placement rate, conflicts by grade, UNSCHEDULED slot counts (total, FY/S1/S2 breakdown, students with gaps)

### Unlimited Seat Analysis Report
- **`Unlimited_Seat_Analysis_2026_27.xlsx`** — Generated by `unlimited` mode (diagnostic)
  - Sheet 1 "Section Demand": Every section with original cap, actual enrollment, over-cap amount, overfill %, action needed (SPLIT/MOVE/OK)
  - Sheet 2 "Course Demand Summary": Per-course totals — original capacity vs actual enrollment, max section enrollment, periods covered, extra sections needed, recommendation
  - Sheet 3 "Period Demand Heatmap": Per-course enrollment by period (A-G) and over-cap by period
  - Sheet 4 "Summary": Diagnostic totals — placement rate, sections needing split/move, courses over capacity, extra sections needed, move recommendation counts
  - Sheet 5 "Section Move Recommendations": Specific move recommendations — which section to move, from which period (low demand) to which period (high demand), demand gain, priority score (grad-req courses ranked highest), driving courses causing the imbalance
  - Sheet 6 "Period Rebalance Summary": Per-course view of demand vs sections by period, surplus/deficit periods, number of moves recommended

### Engine Analysis Report
- **`Engine_Analysis_Report.xlsx`** — Generated by `analyze` mode from Job 1+2 solution data
  - Sheet 1 "Executive Summary": Overall metrics, fulfillment rates, capacity, conflict breakdown, root causes, key findings
  - Sheet 2 "Process Effectiveness": Phase A-D assessments with ratings (GOOD/FAIR/POOR/CRITICAL)
  - Sheet 3 "Bottleneck Analysis": All courses with conflicts — demand, capacity, spare seats, period coverage, diagnosis
  - Sheet 4 "Code Changes": Engine code recommendations with problem/solution/impact/location
  - Sheet 5 "Rule Changes": Administrative/data recommendations
  - Sheet 6 "Process Changes": Engine process flow recommendations
  - Sheet 7 "Period Coverage": Section distribution heatmap across periods A-G per course
  - Sheet 8 "Impact Projection": Estimated conflict reduction if recommendations implemented

### Reports (formats defined in `REPORT_FORMATS` dict in engine)
1. **Master Section Report** (`Master_Section_Report_2026_27.xlsx`) — One row per section: Teacher ID, Teacher Name, Period, Term (S1/S2/FY), Course Code, Section #, Course Title, Section Enrollment
2. **Teacher Schedule Review & Tally** (`Teacher_Schedule_Review_and_Tally.xlsx`) — Side-by-side 2025-26 vs 2026-27 per teacher, periods A-G with S1/S2 courses, total sections and consecutive period tallies
3. **Remaining Conflicts** (`Remaining_Conflicts_v2.5.xlsx`) — All unplaced student-course pairs with priority label, grad req flag, root cause, blocking courses; Summary tab with counts by grade/label
4. **Student Schedule Report** (`Student_Schedule_Report_2026_27.xlsx`) — All students with S1/S2 split per period (14 period columns), credit value per course, total credits, conflicts; UNSCHEDULED with term (FY/S1/S2) for empty semester slots
5. **Incomplete Student Schedules** (`Incomplete_Student_Schedules_2026_27.xlsx`) — Only students with UNSCHEDULED slots; same S1/S2 split layout plus Unscheduled Slots count; sorted by most gaps first
6. **Course Request Report** (`Course_Request_Report_2026_27.xlsx`) — Per-course: Total Requests, Requests Scheduled, Requests Unscheduled, % Scheduled; grand total row
7. **Preflight Validation Report** (`Preflight_Validation_Report.xlsx`) — Auto-generated by engine: duplicates, prerequisite violations, grade eligibility warnings

### Data Corrections Applied
- **556 AP Physics**: Removed from all templates — erroneous entry. AP Physics is only **557 AP Physics 1**
- **Linear Algebra**: Removed from Template 7 and Template 2 — not a real course (1 student request from 106297 also removed)
- **Tranate (105746)**: Course code corrected 556→557 in Template 6 Sheet 2
- **Granieri (122120)**: Reassigned from 810/820/830 to 849×8 + 830×1; former sections transferred to TBD Theology (999999)
- **TBD Theology (999999)**: 830 section removed — 830 should have 9 total sections, not 10
- **Template 7 REV 08.04.26**: Column D changed from "Credits" to "Term Type" (FY/S), Column E added as "Term Credits" (5.0/2.5/0). Semester courses changed from S1→S. 631 CPR-AED and 642 Nutrition & Fitness had "Physical Education" removed from Graduation Requirement.
- **Template 6 REV 08.04.26**: Sheet 2 Column E changed from optional to REQUIRED. All 371 rows populated: FY=245, EC=97, S1=15, S2=14. 203 Guitar Ensemble rows 51-52 corrected from EC→FY.
- **semester_designations.json**: Eliminated — T6 Column E is sole authority for section semester placement
- **Template 2 REV 08.04.26.V3**: Replaced V2. 6,100 requests, 804 students, 141 courses (4 duplicate rows: 106243/642, 106291/642, 112088/2044, 112896/320). English (110-149), Arts (201-255), History (310-311) requests restored. Theology/Academic Support (849, 851, 830, 955) requests removed. Student 121012 included with 6 requests (410,510,570,610,710,810). Student 105477 (Hinspeter) removed from T8. **Post-V3 fix:** Added 428 missing Theology requests (830×98 Gr11, 849×165 Gr12, 851×165 Gr12). Added 28 missing 955 Academic Support requests (confirmed from SIS). Final T2: 6,556 rows (6,552 unique), 804 students, 144 courses.
- **Template 8 REV 08.04.26.V2**: 804 students. Added 121012 Garcia, Jace Jaden (Gr9). Removed 105477 Hinspeter, Jack (Gr12). Prior additions retained: 116597 Giordano, Joseph (Gr9), 120834 McNeal, Harlem (Gr10).

### Current Results (v3 — latest full run, STALE — pre-T2 revision)
- 748 conflicts (Gr9: 169, Gr10: 164, Gr11: 145, Gr12: 270), 88.5% placement (5781/6529)
- 0 double-bookings, 0 teacher load violations
- Graduation requirement fulfillment: 4799/5420 (88.5%)
- AP/Honors fulfillment: 648/682 (95.0%)
- Protected course conflicts: 666
- Root cause: 680 all_periods_blocked, 126 singleton_collision, 5 period_conflict
- 371 sections across 143 courses, 63 teachers
- Phase D: 16 restarts, best seed=4269
- Phase A-0: Conflict matrix (3,018 pairs) with lazy caching across restarts
- Engine Analysis Report generated: 17 recommendations (7 code, 6 rule, 4 process)

### Priority System (DATA_STRUCTURE.md — current engine implementation)
- **Two-level priority:** Course Section Priority determines section placement order; Student Priority determines student fill order
- **8 stacking course characteristics:** AP (30), Singleton (25), Graduation Requirement (20), Gr12 PAE (20), Semester Only (15), Cohort Course (15), Co-Schedule Group (15), Prescribed Term (10)
- **Student Raw** = Grade Level (10/20/30/40) + Cohort LEO II (50) + SSP (25)
- **Student Total** = Raw + sum of course request priorities
- **Course Section Total** = Course Section Raw + Top Student Total + Teacher Total + Room Total
- **Protection:** Courses with Graduation Requirement OR Gr12 PAE OR Singleton flag cannot be bumped
- **Tiebreaker:** When two sections have the same Total, Course Section Raw breaks the tie
- **Recalculation:** After every batch of placements, caches are cleared and all totals re-ranked

### Engine Improvements Applied (retained from prior work)
- **Double-booking fix**: Students may only occupy one course per period-semester slot — bump logic enforces this unconditionally
- **Pin-conflict demotion in CSP**: `resolve_student()` demotes lower-priority pins when two protected courses conflict
- **Global placement ordering**: Both `full_reseat()` and `full_reseat_fast()` sort ALL student-course pairs globally using `course_request_priority` → `student_total_priority` → `course_section_raw` → section count
- **Batch recalculation**: Priority caches cleared and re-ranked every 1,500 placements
- **Teacher load enforcement**: `teacher_would_exceed_cap()` uses per-teacher profile caps from `get_max_load()` (5 default, 6 with per-semester approval)
- **Co-schedule section counting**: Co-scheduled sections count as ONE section for teacher load and priority calculations — `teacher_raw_priority()` groups co-scheduled sections and counts locks once per group instance, not per raw section
- **Two-section swap optimization**: After single-section moves stall, tries swapping periods between pairs of high-conflict sections (time-limited to 60s per restart)
- **Enhanced CSP**: 6 rounds in `full_reseat()` and `full_reseat_fast()`
- **CSP recovery in fast path**: Post-bump CSP recovery and greedy re-add in `full_reseat_fast()`
- **Phase A-0 conflict matrix**: Pre-computes priority-weighted conflict matrix (3,018 course pairs) and conflict degree per course. Lazy caching via `_ensure_conflict_matrix()` computes once and reuses across Phase D's 16 restarts, keeping conflict scoring consistent
