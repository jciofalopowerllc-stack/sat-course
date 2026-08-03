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

**The engine has TWO distinct jobs that run in order:**

1. **Job 1 — Course Section Placement (runs FIRST):**
   - Place course sections (with their assigned teachers and rooms) into the master bell schedule by Term (FY, S1, S2) and Period (A-G)
   - BEFORE placing, the engine MUST analyze priority values for students, teachers, rooms, AND courses
   - Use that analysis to DECIDE the most optimal position (period + term) for each course section with its teacher and room
   - Goal: position sections to AVOID student clashes before students are ever placed

2. **Job 2 — Student Placement (runs SECOND, only after Job 1 is complete):**
   - Place students into the already-positioned course sections
   - Do NOT run student placements until Job 1 is verified correct

### Semester Locks (2026-27)
- **758 Bloomberg Market Concepts**: S2 ONLY — cannot be placed in S1
- **766**: S1 only
- **765**: S2 only
- These are enforced in `SEMESTER_LOCKS` dict in `schedule_engine_v3.py` (line ~1389) AND in Template 7 `Prescribed Term` column

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

### Semester Locks (LEO Programs)
- **745 LEO II**: S1 only (period determined by engine priority placement)
- **734 LEO I**: S2 only (period determined by engine priority placement)
- No course sections are required to be placed in a specific period of the day

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
- `Reports.md` — Report format reference (column layouts, sort orders, features)

### Reports (formats defined in `REPORT_FORMATS` dict in engine)
1. **Master Section Report** (`Master_Section_Report_2026_27.xlsx`) — One row per section: Teacher ID, Teacher Name, Period, Term (S1/S2/FY), Course Code, Section #, Course Title, Section Enrollment
2. **Teacher Schedule Review & Tally** (`Teacher_Schedule_Review_and_Tally.xlsx`) — Side-by-side 2025-26 vs 2026-27 per teacher, periods A-G with S1/S2 courses, total sections and consecutive period tallies
3. **Remaining Clashes** (`Remaining_Clashes_v2.5.xlsx`) — All unplaced student-course pairs with priority label, grad req flag, root cause, blocking courses; Summary tab with counts by grade/label
4. **Student Schedule Report** (`Student_Schedule_Report_2026_27.xlsx`) — All students with S1/S2 split per period (14 period columns), credit value per course, total credits, clashes; UNASSIGNED for empty semester slots
5. **Incomplete Student Schedules** (`Incomplete_Student_Schedules_2026_27.xlsx`) — Only students with UNASSIGNED slots; same S1/S2 split layout plus Unassigned Slots count; sorted by most gaps first
6. **Course Request Report** (`Course_Request_Report_2026_27.xlsx`) — Per-course: Total Requests, Requests Scheduled, Requests Unscheduled, % Scheduled; grand total row
7. **Preflight Validation Report** (`Preflight_Validation_Report.xlsx`) — Auto-generated by engine: duplicates, prerequisite violations, grade eligibility warnings

### Data Corrections Applied
- **556 AP Physics**: Removed from all templates — erroneous entry. AP Physics is only **557 AP Physics 1**
- **Linear Algebra**: Removed from Template 7 and Template 2 — not a real course (1 student request from 106297 also removed)
- **Tranate (105746)**: Course code corrected 556→557 in Template 6 Sheet 2
- **Granieri (122120)**: Reassigned from 810/820/830 to 849×8 + 830×1; former sections transferred to TBD Theology (999999)
- **TBD Theology (999999)**: 830 section removed — 830 should have 9 total sections, not 10

### Current Results (v3 — pre-priority-rewrite baseline)
- 911 clashes (Gr9: 182, Gr10: 178, Gr11: 239, Gr12: 312), 86.1% placement (5627/6538)
- 0 double-bookings (critical fix: students may only occupy one course per period-semester slot)
- Graduation requirement fulfillment: 5042/5427 (92.9%)
- AP/Honors fulfillment: 2318/2465 (94.0%)
- Protected course (graduation_required) clashes: 5
- Root cause: 683 all_periods_blocked, 503 singleton_collision, 2 period_conflict
- Hard enrollment cap of 28 enforced for 310 Spanish I and 520 Chemistry
- 371 sections across 143 courses, 63 teachers
- Top unscheduled courses: 708 Intro to Business (44), 726 Business Concepts (37), 727 Sports Marketing (34), 734 LEO I (24), 732 Business Law (18)
- **NOTE:** These results are from the OLD priority system. Engine has been rewritten with the DATA_STRUCTURE.md priority system but NOT yet re-run.

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
- **Two-section swap optimization**: After single-section moves stall, tries swapping periods between pairs of high-clash sections (time-limited to 60s per restart)
- **Enhanced CSP**: 6 rounds in `full_reseat()` and `full_reseat_fast()`
- **CSP recovery in fast path**: Post-bump CSP recovery and greedy re-add in `full_reseat_fast()`
