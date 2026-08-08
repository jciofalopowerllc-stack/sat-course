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
9. After every engine run (job1, full, gr12, scenario, unlimited), generate a **System Improvement Report** — analyze results for design flaws, feature gaps, data issues, conflict root causes, and optimization opportunities. Present findings with priority levels (CRITICAL / HIGH / MEDIUM / LOW) and decision types (ACTION NEEDED / FYI). Do NOT implement any recommendation without JC's explicit approval. The report is delivered in conversation, not as a file.
10. Every recommendation in the System Improvement Report MUST include **full background details** so the decision-maker can evaluate feasibility without looking up templates. For teacher-related recommendations, this means: teacher name and ID, max load cap, current periods used (S1/S2), free periods, their COMPLETE prescribed course load from Template 7 (all courses, section counts, term types, prescribed periods/rooms), and a feasibility assessment stating whether the fix is a MOVE (relocating an existing section) or an ADD (requiring an additional period beyond max load). Never present a recommendation without the context needed to say yes or no.
11. Every recommendation MUST include a **Revised Schedule Preview** showing the teacher's full period-by-period schedule (Periods A-G, S1/S2 columns) in two views: (1) **Current Schedule** — what the teacher's schedule looks like right now, and (2) **Revised Schedule (if recommendation accepted)** — what the teacher's schedule would look like after the recommended move, with changed periods marked `◀ CHANGED`. This lets the decision-maker see the complete before-and-after impact at a glance without mentally reconstructing the schedule. If the recommendation does not change a particular teacher's schedule, print "(No schedule change for this teacher under current recommendation)" instead.
12. **No blank cells permitted in any template.** Every cell in every template (T1–T9) MUST contain a value. Use `N/A` for fields where no data applies (e.g., no prescribed room, no cohort, no prerequisite). Blank/empty cells are data entry errors — the engine MUST flag them as validation errors at startup and refuse to run until corrected. This applies to all existing and future templates. When creating or editing templates programmatically, always write `N/A` instead of leaving a cell empty.
13. **Y/N column convention.** Columns whose header contains `(Y/N)` (e.g., `Singleton (Y/N)`, `Avail Period A (Y/N)`, `Passed (Y/N)`) must contain exactly `Y` or `N` — never `N/A`, never blank. All other columns use `N/A` when no data applies. The `(Y/N)` suffix in the header IS the contract — the engine validates this at startup and flags any non-Y/N value in a `(Y/N)` column as an error. 26 Y/N columns exist across T1 (6), T2 (13), T3 (5), T4 (1), T6 (1).
14. **Every bug fix must be committed, pushed, and documented immediately.** When a bug is fixed: (1) commit and push the code change in the same response as the fix, (2) add the bug to the "Bugs Fixed" registry below with root cause, fix description, and affected code location, (3) verify no other code path has the same class of bug before closing. Trial and error is acceptable — repeating a previously fixed bug is not. The registry is the institutional memory; consult it before writing new code that touches the same area.

### Engine Architecture (from JC Iofalo — non-negotiable)
- Use **schedule_engine_v3.py** (v3 engine) — NOT v4
- **`Engine_Templates_With_Data.xlsx` is the SOLE AUTHORITATIVE SOURCE** — no legacy files, no fallbacks, no alternative data sources. If a required template sheet (e.g., T5 Student Course Requests) is empty, the engine MUST refuse to run. No silent fallback to any other file.
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

### Semester Pairing Groups (Universal Rule — from JC Iofalo, non-negotiable)
A semester pairing group is a set of 2+ course codes whose semester sections must be placed in the **same periods, opposite semesters** during Job 1 (Section Placement). Each period assigned to the group gets one S1 section and one S2 section of every course in the group.

- **Job 1 constraint only:** The engine pairs sections into shared periods before `greedy_assign_periods()` runs. Pairing group sections are immovable — `greedy_assign_periods()` skips them, and the Phase D optimizer cannot move them.
- **Job 2 is independent:** Students may take paired courses in any period, any semester, any combination. The only requirement is that every student who needs the paired courses gets them somewhere in their schedule.
- **Conflict scoring exclusion:** Pairing group partners are excluded from `_predict_conflict_score()` and co-enrollment spreading — they share periods by design, and students choose independently.
- **Period selection:** The engine scores all C(7, periods_needed) combinations using conflict potential + period load balance, picking the lowest-scoring combo.
- **Defined in:** `Engine_Templates_With_Data.xlsx` → T1 Col 20 "Semester Pairing Group" (per-course label) and `course_priorities.json` → `"semester_pairing_groups"` array (group definitions with descriptions).
- **Current groups:** Grade 12 Theology (849 Catholic Social Teaching + 851 Spirituality of Vocation) — 8 sections each, 4 periods, 16 total sections.
- **Why:** Without pairing, 849 and 851 could spread across all 7 periods, consuming every period for Grade 12 students. With pairing, they share 4 periods, leaving 3 free for other courses. Mathematical conflict reduction: up to 164 fewer conflicts.

### PE Period Pool (Universal Rule — from JC Iofalo, non-negotiable)
Grade 9/10 semester electives, SSP courses, and pathway courses MUST be in the **same periods as their grade's PE course, opposite semesters**. Students take PE one semester and their elective in the other semester in the same period slot.

- **Anchor courses:** 610 Health/PE (Grade 9), 620 Driver's Ed/PE (Grade 10)
- **Pre-placement:** PE anchors are placed in Step 1.6 (after co-schedule groups and pairing groups, before greedy). The engine scores all C(7, N) period combinations to find optimal PE periods.
- **Period restriction (Job 1):** During `greedy_assign_periods()`, ALL Gr9/10 semester non-PE courses are restricted to PE pool periods only. Periods outside the pool are blocked with reason `pe_pool`.
- **Grade overlap:** Courses eligible for BOTH Gr9 and Gr10 can use the UNION of both grade pools.
- **Co-schedule compatibility:** If a co-schedule group contains a Gr9/10 semester course, its period is required to be in the PE pool (engine enforces this during combo scoring).
- **Conflict scoring exclusion:** PE anchor ↔ pool course co-enrollment is excluded from `_predict_conflict_score()` and co-enrollment spreading — students take PE and elective in opposite semesters, so same-period same-semester overlap is not a real conflict.
- **Immovable:** PE anchor sections are in `PE_POOL_SIDS` — Phase D optimizer cannot move them. Pool-restricted courses can only move to pool periods during Phase D.
- **Phase D restart:** PE section periods preserved in `_save_fixed_state()` and `_restore_for_restart()`. EC redistribution excludes PE pool sections.

### Engine Run Modes
- `python schedule_engine_v3.py` or `python schedule_engine_v3.py job1` — Run Job 1 only, export Excel, **STOP** for review
- `python schedule_engine_v3.py full` — Run Job 1 + Job 2 (student placement), export both Excel reports
- `python schedule_engine_v3.py analyze` — Analyze Job 1+2 outputs, generate `Engine_Analysis_Report.xlsx` (requires prior `full` run)
- `python schedule_engine_v3.py unlimited` — Run Job 1 + Job 2 with **unlimited section caps** (diagnostic mode), export `Unlimited_Seat_Analysis_2026_27.xlsx` showing natural demand per section to identify which sections need splitting or moving
- `python schedule_engine_v3.py gr12` — Run Job 1 + Job 2 for **Grade 12 only** (shorthand for `--grades 12`)
- `python schedule_engine_v3.py scenario` — **Interactive scenario menu**: presents filter options after data loads, user picks grade levels, cohorts, departments, courses, and/or teachers interactively, then selects Job 1 or Full run
- Default mode is `job1` — the engine will never proceed to Job 2 without explicit approval

### Scenario Filters (CLI flags — combinable with any mode except `analyze`)
Scenario filters let the user run the engine on a subset of sections and students for **lighter evaluative runs**. All filters are combinable. Output filenames are auto-suffixed (e.g., `Job1_Section_Placements_GR11+12_DEPT_Science_2026_27.xlsx`).

| Flag | Example | What it filters |
|------|---------|----------------|
| `--grades` | `--grades 11,12` | Keep only courses eligible for selected grade levels + students in those grades |
| `--cohort` | `--cohort LEO_II` | Keep only LEO II students (options: `LEO_II`, `LEO_A`, `LEO_B`) |
| `--dept` | `--dept "Science,Mathematics"` | Keep only courses in selected departments |
| `--courses` | `--courses 849,851` | Keep only specific course codes |
| `--teachers` | `--teachers 122120,106760` | Keep only sections taught by selected teachers (accepts IDs or names separated by `;`) |

**Examples:**
- `python schedule_engine_v3.py full --grades 12` — Full run, Grade 12 only
- `python schedule_engine_v3.py job1 --dept Science --grades 11,12` — Job 1, Science dept for Gr11+12
- `python schedule_engine_v3.py full --cohort LEO_II` — Full run, LEO II students only
- `python schedule_engine_v3.py full --teachers 122120` — Full run, Granieri's sections + students only
- `python schedule_engine_v3.py full --courses 849,851 --grades 12` — Full run, Gr12 Theology only

### Term Type & Prescribed Term Architecture (REV 08.04.26)
- **Two distinct concepts, two distinct templates:**
  - **Template 7 Column D "Term Type"** — describes WHAT a course IS: `FY` (full-year, 5.0 credits) or `SE` (semester, 2.5 credits). Classification only — does NOT control placement.
  - **Template 7 Column E "Term Credits"** — validation failsafe: FY must pair with 5.0, SE must pair with 2.5 (0 allowed for special courses like 955 Academic Support).
  - **Template 7 Column H "Prescribed Term"** — REQUIRED field, describes WHERE a specific section GOES: `FY`, `S1`, `S2`, or `EC` (Engine Choice). This is the **single authoritative source** for per-section semester placement.
- **Prescribed = Required** (same as prescribed room and prescribed period):
  - `FY` → engine MUST place section as full-year (S1+S2)
  - `S1` → engine MUST place section in S1 only
  - `S2` → engine MUST place section in S2 only
  - `EC` → engine MAY place section in either S1 or S2 (Engine Choice — engine decides which is optimal)
- **Cross-validation rule:** T1 Term Type=FY requires T7 Prescribed Term=FY; T1 Term Type=SE requires T7 Prescribed Term=S1/S2/EC. Mismatch = engine validation error.
- **EC redistribution:** EC sections are distributed evenly across S1/S2 by the engine (n_s1 = (n+1)//2)
- **Eliminated:** `SEMESTER_LOCKS` dict, `FULL_FREEDOM` set, `semester_designations.json` — all replaced by T7 Column H as sole authority
- **Distribution (367 sections):** FY=243, S1=36, S2=34, EC=54

### Teacher Section Prescriptions (2026-27)
- **Chiaravalloti, Michael (105747)**: 631 CPR-AED Training/PE × 4 semester sections + 642 Nutrition & Fitness/PE × 6 semester sections = 10 total (5 per semester); Daniels (105763) also teaches 631 × 2 semester sections (6 total 631 sections)
- **Fisk, Mary Pat (105819)**: 131 British Literature H × 3 full-year sections
- **Kozak, Bernadette (105628)**: 595 Engineering Design × 2 semester sections (1 S1 + 1 S2)
- **Laracy, John (106760)**: 851 Spirituality of Vocation × 8 semester sections
- **Umbrino, Philip (105768)**: 130 British Literature × 3 full-year sections (added to existing pool)
- **Lopez, Enrique (102255)**: 201 Introduction to Guitar × 2 semester sections (co-scheduled with 203 Guitar Ensemble, same period/room); 203 Guitar Ensemble is full-year (5 credits, 2 sections)
- **Tranate, John (105746)**: 557 AP Physics 1 × 2 sections (typo corrected from 556→557 in Template 7)
- **Dennehy (105810)**: 248 Adv Drawing × 1 semester section, Room J-322
- **Granieri, William (122120)**: 849 Catholic Social Teaching × 8 semester sections + 830 Theology 11 × 1 section (reassigned from 810/820/830 to TBD Theology teacher)
- **TBD Theology, New (999999)**: Placeholder for new hire — 810 Theology 9 × 3 + 820 Theology 10 × 2 (transferred from Granieri). Replace with real name/ID when available.
- **Saggio, Jack (117711)**: 723 Introduction to Political Science × 1 semester section
- Sections defined in T7_Teacher-Section Assignments, one row per section

### Grade 12 Science Requirement Exceptions (2026-27)
- 39 specific Grade 12 student-course pairs are treated as **graduation_required** priority even though Science is not a standard Gr12 required department
- Courses affected: 543 Anatomy/Physiology H (9 students), 546 Forensics (27 students), 530 Physics (1 student), 531 Physics H (2 students)
- Defined in `Engine_Templates_With_Data.xlsx` → T12_Student Priority Overrides (39 rows)
- Engine's `course_request_priority()` and `_is_grad_req_for_student()` check these overrides

### Room Assignment Rules
- Sections without a prescribed room may be placed into any room that is free for that period and term
- Prescribed rooms are NOT exclusively reserved — they are available to other sections in any period/term when the prescribed section is not using them
- 66 of 371 sections have no prescribed room — this is correct (not a data gap)
- **Room conflict resolution:** When two sections from different teachers are assigned the same room+period, the section with a prescribed room (from T7) stays; the other is moved to the nearest free room (same wing preferred). If neither has a prescribed room, course section priority breaks the tie. **Prior Year data is never used as a placement factor.**
- **J-321** is historically a Theology room (used by Arcede for 810 Theology 9 in 2025-26). Available for other departments when no Theology class is scheduled.

### Teacher Load Cap Enforcement (from JC Iofalo — non-negotiable)
- **Hard cap:** A teacher MUST NOT be assigned more than 5 sections per semester (counting unique periods occupied, with co-schedule groups counting as 1 period) UNLESS explicitly approved for a 6th period in T2 (Teacher Profiles)
- **Absolute ceiling:** 7/5 is NEVER permitted under any circumstance. Maximum per semester is 6 (with approval). `ABSOLUTE_MAX_PERIODS_PER_SEMESTER = 6` in the engine.
- **6th period approval types:** Full-Year (both semesters), S1-only, or S2-only — defined in T2 (Teacher Profiles)
- **No fallback override:** If no valid period exists without exceeding the cap, the section stays **UNPLACED** — the engine does NOT force-place it
- **Room double-booking is a hard block** — same as teacher_busy and load_cap; the engine will NOT place two non-co-scheduled sections in the same room, same period, same semester
- **FY-equivalent awareness in placement:** When evaluating whether to place a semester section, the engine computes the projected FY-equivalent load using `teacher_load_projection()`. FY = min(S1_count, S2_count). The engine uses this to: (1) enforce the absolute ceiling, (2) score period candidates — preferring placements that minimize FY-equivalent increase and stipend escalation, (3) log the FY-impact transparently in placement reports
- **Pre-flight validation:** Before Job 1 begins, the engine validates every teacher's total prescribed load (FY + S1 + S2 + EC) against their cap, accounting for co-schedule groups as 1 period slot. Any overload is flagged with resolution options (approval or load reduction) and includes the FY-equivalent stipend impact

### 6th-Period Stipend Calculation (from JC Iofalo — non-negotiable)
The engine calculates each teacher's full-year-equivalent period load and 6th-period stipend eligibility. This function is `calculate_teacher_stipend()` in the engine.

**Three-term load display (FY / S1 / S2):**
- **S1** = total periods occupied in Semester 1 (FY sections + S1-only sections)
- **S2** = total periods occupied in Semester 2 (FY sections + S2-only sections)
- **FY** = min(S1, S2) — the full-year equivalent baseline load present in both semesters

**Key concept:** A FY section automatically occupies both S1 and S2. FY, S1, and S2 overlap simultaneously — they are NOT separated. The FY column captures how many periods the teacher is consistently teaching across the entire year. If a teacher works 6 periods in both S1 and S2 (even in different specific periods), FY = 6 — they have a 6th period all year.

**Standard cap = 5 periods per term (always).** The denominator is ALWAYS 5 because that is the cap before extra compensation. Three terms of 5/5 = 15/15 = standard load, no stipend.

**Stipend rules (based on FY equivalent):**
- Both S1 > 5 AND S2 > 5 → **100% of FY 6th-period stipend** (teacher works 6th period all year)
- Only S1 > 5 OR only S2 > 5 → **50% of FY 6th-period stipend** (teacher works 6th period one semester)
- Neither over 5 → **no stipend** (0%)

**Examples:**
- Saggio: FY=5/5, S1=5/5, S2=6/5 → 16/15 → 50% FY Stipend (extra period S2 only)
- Corcoran: FY=6/5, S1=6/5, S2=6/5 → 18/15 → 100% FY Stipend (6 periods both semesters)
- Standard teacher: FY=5/5, S1=5/5, S2=5/5 → 15/15 → No Stipend

### Consecutive-6-Period Constraint (from JC Iofalo — non-negotiable)
- **Rule:** Teachers approved for a 6th teaching period MUST NOT be placed in 6 consecutive periods in any semester. The free period must be interior (B through F), not an endpoint (A or G).
- **Why:** With 7 periods A-G, a teacher teaching 6 periods has exactly 1 free. If that free period is A (periods B-G used) or G (periods A-F used), the teacher has no break — 6 classes in a row. The free period must fall between B and F to ensure at most 5 consecutive periods.
- **Enforcement:** Hard block in `greedy_assign_periods()`, co-schedule group assignment, semester pairing group assignment, and `_can_move_section()` (Phase D optimizer). The engine skips any period that would create 6 consecutive and reports `consecutive_6` as the block reason.
- **Validation:** Post-placement check reports any violations in both Job 1 and full run output.
- **Only applies when:** A teacher would have exactly 6 periods occupied in a semester. Teachers with 5 or fewer periods cannot have 6 consecutive by definition.

### Key Files
- `schedule_engine_v3.py` — Main engine (5-phase: Period Assignment → Student Seating → Bump Conflicts → Optimization → D-2 Unplaced Rescue + Phase A-1 Diagnostics)
- `Engine_Templates_With_Data.xlsx` — **Consolidated workbook (sole authority)** — 12 sheets (T1–T12), all input templates + config data. INDEX sheet has full layout reference.
- `course_priorities.json` — Graduation requirements, pathway courses, singleton courses (T10, T11, T1 Col 20 hold canonical data in the workbook)
- `student_priority_overrides.json` — Student-specific priority overrides (T12 holds canonical data in the workbook)
- `detect_pathways.py` — Pathway detection from T8 Transcript History + Course Requests
- `schedule_solution_v3.json` — Engine output
- `run_diagnostics.json` — Cross-run learning data (Phase A-1 output, loaded by next run)
- `DESIGN_Post_Run_Diagnostics.md` — Full design document for the cross-run learning system
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
- **Tranate (105746)**: Course code corrected 556→557 in Template 7
- **Granieri (122120)**: Reassigned from 810/820/830 to 849×8 + 830×1; former sections transferred to TBD Theology (999999)
- **TBD Theology (999999)**: 830 section removed — 830 should have 9 total sections, not 10
- **Template 7 REV 08.04.26**: Column D changed from "Credits" to "Term Type" (FY/SE), Column E added as "Term Credits" (5.0/2.5/0). Semester courses changed from S1→SE. 631 CPR-AED and 642 Nutrition & Fitness had "Physical Education" removed from Graduation Requirement.
- **Template 7 REV 08.04.26**: Column H "Prescribed Term" changed from optional to REQUIRED. All 371 rows populated: FY=245, EC=97, S1=15, S2=14. 203 Guitar Ensemble rows 51-52 corrected from EC→FY.
- **semester_designations.json**: Eliminated — T7 Column H is sole authority for section semester placement
- **Template 2 REV 08.04.26.V3**: Replaced V2. 6,100 requests, 804 students, 141 courses (4 duplicate rows: 106243/642, 106291/642, 112088/2044, 112896/320). English (110-149), Arts (201-255), History (310-311) requests restored. Theology/Academic Support (849, 851, 830, 955) requests removed. Student 121012 included with 6 requests (410,510,570,610,710,810). **Post-V3 fix:** Added 428 missing Theology requests (830×98 Gr11, 849×165 Gr12, 851×165 Gr12). Added 28 missing 955 Academic Support requests (confirmed from SIS). **Post-audit fix (08.06.26):** Removed 10 course 202 (Chorus) requests — not scheduled A-G. Removed 4 duplicate rows (106243/642, 106291/642, 112088/2044, 112896/320). Final T2: 6,544 rows (header + REQUIRED + 6,542 data), 805 students, 143 courses.
- **Template 8 REV 08.04.26.V2**: 804 students. Added 121012 Garcia, Jace Jaden (Gr9). Prior additions retained: 116597 Giordano, Joseph (Gr9), 120834 McNeal, Harlem (Gr10). 105477 Hinspeter, Jack (Gr12) retained (previously documented as removed in error — student is active with 11 course requests). Note: 105477 has no Transcript History in T8 Sheet 2. **Post-audit fix (08.06.26):** Removed duplicate 116597 row; fixed student 121012 trailing non-breaking space in ID.

### Current Results
- **NO RESULTS** — Engine memory wiped clean (08.07.26). All prior output was generated from corrupted data (wrong teacher IDs + stale legacy student requests) and has been deleted.
- Engine CANNOT run until T5_Student Course Requests is populated in Engine_Templates_With_Data.xlsx.
- First clean run will produce fresh output from the sole authoritative source.

### Priority System (DATA_STRUCTURE.md — current engine implementation)
- **Two-level priority:** Course Section Priority determines section placement order; Student Priority determines student fill order
- **9 stacking course characteristics:** AP (30), Singleton (25), Graduation Requirement (30), Gr12 PAE (20), Priority Level (0–20), Semester Only (10), Cohort Course (15), Co-Schedule Group (15), Prescribed Term (10)
- **6th-Period Teacher boost (5,000):** Applied to Teacher Raw and Room Raw (if prescribed room). Teachers approved for a 6th period are more constrained (consecutive-6 rule, load cap ceiling). The 5,000-point boost guarantees their sections always rank above any non-6th-period teacher's sections (theoretical max cs_total without boost is ~5,790). Boost applies to the TEACHER and ROOM, NOT to course characteristics — course identity stays independent. Among 6th-period teachers, normal priority characteristics still break ties.
- **Student Raw** = Grade Level (10/20/30/40) + Cohort LEO II (50) + SSP (25)
- **Student Total** = Raw + sum of course request priorities
- **Course Section Total** = Course Section Raw + Top Student Total + Teacher Raw + Room Raw (each component added once — no cascading amplification)
- **Protection:** Courses with Graduation Requirement OR Gr12 PAE OR Singleton flag cannot be bumped
- **Tiebreaker:** When two sections have the same Total, Course Section Raw breaks the tie
- **Recalculation:** After every batch of placements, caches are cleared and all totals re-ranked
- **Priority Level (T5 Col D):** Counselor-designated per-request priority, 9th stacking characteristic:
  - 5 = MANDATORY (+20) — counselor-mandated, student MUST take this course
  - 4 = PROGRAM (+15) — required for student's pathway/SSP track
  - 3 = PREFERRED (+10) — first-choice elective (default if not specified)
  - 2 = INTEREST (+5) — student interested but flexible, acceptable to substitute
  - 1 = ALTERNATE (+0) — backup request, fill only if higher-priority requests can't be placed
- **Priority value columns in templates:** Engine_Templates_With_Data.xlsx stores computed priority values alongside source data for full transparency and auditability:
  - **T2** Col 19: `6th Period Boost` (5000 or 0) — derived from 6th Period FY/S1/S2 approval columns
  - **T3** Cols 13-16: `Grade Level Points` (10/20/30/40), `LEO II Points` (50/0), `SSP Points` (25/0), `Student Raw Priority` (sum, range 10–115)
  - **T5** Cols A-D: INPUT (Student ID, Course Code, Alternate Course Code, Priority Level 1-5); Cols E-J: ENGINE-COMPUTED (Student Grade Level, Student Raw Priority, Course Request Priority, Student Total Priority, Graduation Required Y/N, Protected Y/N)
  - **T7** Col 15: `Course Section Raw` (sum of 9 components, range 0–110) + Col 16: `Placement Tier` (1/2/3) + Cols 17-24: 8 individual component columns (`AP Points`, `Singleton Points`, `Grad Req Points`, `Gr12 PAE Points`, `Semester Only Points`, `Cohort Points`, `Co-Schedule Points`, `Prescribed Term Points`) + Col 25: `Grade Levels` (from T1, e.g. "9,10,11,12" — drives three-tier placement system)

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
- **Phase A-1 cross-run diagnostics**: Post-run analyzer writes `run_diagnostics.json` with period coverage analysis, blocking chains, teacher bottlenecks, period hotspots. Next run loads diagnostics and applies bias adjustments to `_predict_conflict_score()` — penalizing problematic periods and rewarding uncovered periods proportional to prior conflict severity
- **System Improvement Report**: Console output after every Job 2 run showing CRITICAL/HIGH/MEDIUM/LOW findings with full teacher background details (ID, max load, current periods used, complete prescribed course load from T7, feasibility assessment — MOVE vs ADD), **Revised Schedule Preview** (current vs proposed period-by-period teacher schedule with ◀ CHANGED markers), blocking chain analysis, teacher bottlenecks, period hotspots, and cross-run conflict delta tracking
- **Phase D-2 unplaced section rescue pass**: After Phase D finishes optimizing the best-seed solution, Phase D-2 scans all sections that remain UNPLACED (period=None). For each unplaced section (highest priority first), it searches for a lower-priority placed section from the SAME TEACHER that can be moved to a different valid period, freeing the original period for the unplaced section. Uses `_can_place_unplaced()` for the rescued section and `_can_move_section()` for the displaced section — both enforce all constraints (teacher busy, load cap, consecutive-6, room busy, PE pool, immovable sets). Rescued sections are re-added to `sec_by_code` (reversing the Bug B1 unplaced filter). After all rescues, `full_reseat()` rebuilds student placements from scratch. Discovered from Corcoran (105712) case: 3 FY + 2 SE sections needing 5 periods — `run_optimization_pass()` only moves placed sections and cannot rescue unplaced ones

### Prior Year Data Policy (from JC Iofalo — non-negotiable)
The engine loads Prior Year schedule data from `T9_Prior Year Master Sections` (within Engine_Templates_With_Data.xlsx). This data is a **historical reference only** — it is NEVER used as an authoritative source for current year placement decisions.

**Permitted uses (reference/comparison only):**
- Track prior-year alignment as an informational metric (how many sections match their prior year period)
- Report `prior_year_match` flag per section in output for administrative review
- Teacher Schedule Review & Tally report shows side-by-side 2025-26 vs 2026-27
- Verify current year assignments when uncertain (e.g., confirm a room change is intentional, not an error)

**Prohibited uses (do NOT implement):**
- Score bonus/penalty based on prior year period match
- Determine room conflict winners based on prior year room usage
- Prefer or avoid periods because of prior year data
- Use prior year teacher-room associations to influence placement

**Sole authorities for current year placement:**
- `Engine_Templates_With_Data.xlsx` — **consolidated workbook** containing all templates and config:
  - T1 (Course Profiles) — course characteristics, grade levels, semester pairing groups
  - T2 (Teacher Profiles) — availability, load caps, 6th period approval
  - T7 (Teacher-Section Assignments) — sections, prescribed rooms/periods/terms/cohorts, priority breakdowns, grade levels
  - T4 (Room Profiles) — room availability, capacity, shared status
  - T10 (Graduation Requirements) — required departments by grade level
  - T11 (Pathway Courses) — SSP pathway-course assignments
  - T12 (Student Priority Overrides) — student-specific graduation-required exceptions

### Cross-Run Learning System (Phase A-1)
The engine learns from its own results across runs. Each run analyzes actual conflicts, writes diagnostics, and the next run reads them to bias section placement toward better periods.

**How it works:**
1. **Run N**: Job 1 places sections → Job 2 places students → Phase A-1 analyzes conflicts → writes `run_diagnostics.json`
2. **Run N+1**: Diagnostic loader reads `run_diagnostics.json` → builds `_diagnostic_bias` dict → `_predict_conflict_score()` uses biases → better placements → fewer conflicts

**Five bias types:**
1. **Coverage penalty**: Penalizes placing sections in periods already covered (if those periods showed conflicts)
2. **Coverage reward**: Rewards placing sections in uncovered periods (negative bias = prefer)
3. **Best-move bonus**: Extra reward for the specific target period the analyzer recommends
4. **Period hotspot cooling**: Penalizes overloaded periods with 3+ conflict-causing courses
5. **Blocking chain awareness**: Pushes blocked courses toward periods free of their blocking courses

**Severity multipliers:** CRITICAL=3×, HIGH=2×, MEDIUM=1.5×, LOW=1× — ensures the most impactful conflicts get the strongest corrections.

**Safety constraints:**
- Only the MOST RECENT run's diagnostics are used (prevents stale data)
- Does NOT override teacher constraints, prescribed periods, or pairing rules
- Does NOT auto-fix — adjusts scoring weights, not hard rules
- Does NOT accumulate across many runs
- Bias is additive to existing conflict score, never replaces it

**Files:**
- `run_diagnostics.json` — Machine-readable output (course diagnostics, blocking chains, teacher bottlenecks, period hotspots)
- `DESIGN_Post_Run_Diagnostics.md` — Full design document with data structure spec

### ⏸️ PAUSED WORK: Room Ownership & Exclusivity System (2026-08-06)

**Status:** Design approved in principle. Implementation paused — templates need cleanup first.

**What was completed:**
1. PTS_SIXTH_PERIOD = 5,000 boost implemented and committed (teacher_raw + room_raw for 6th-period teachers)
2. Room Priority Values export created (47 rooms) — JC revised with YES/NO exclusivity flags
3. JC uploaded `Room_Priority_Values_Revised_08.05.24.xlsx` with 6 exclusive (NO) rooms and 41 shareable (YES) rooms
4. Design document presented and discussed for three capabilities: Exclusive Room Enforcement, Prescribed Teacher Priority (bump), TBD Room Assignment
5. JC uploaded Template 1 (Course Sectioning) — NOT currently loaded by engine

**JC's expanded design vision (three-template cross-validation):**
- **Template 9** (Room Profiles): Add Column F "Exclusive" (Y/N) + Column G "Preferred Teacher ID"
- **T2** (Teacher Profiles): Add Column R "Preferred Room" (teacher-level room preference)
- **Template 1** (Course Sectioning, Sheet 2): Change Column J from "Teacher" (name) → "Teacher ID" (numeric ID)
- Cross-validation at engine startup: Template 9 Room→Teacher ↔ T2 Teacher→Room ↔ Template 1 Section→Teacher+Room

**Exclusive rooms (from JC's revision):** Gym, S-338, I-111, J-223, J-120, Success Center (6 rooms)
**Shareable rooms:** All other 41 rooms

**Template cleanup needed BEFORE implementation:**
- Template 1 not loaded by engine (350 sections vs Template 7's 367 — needs sync)
- Template 1 Sheet 2 Column J has teacher names, needs Teacher IDs
- T2 (Teacher Profiles) needs new "Preferred Room" column (currently 17 cols, A-Q)
- T4 (Room Profiles) needs Column F "Exclusive" and Column G "Preferred Teacher ID" (currently 5 cols, A-E)

**Engine gaps identified (to implement after template cleanup):**
1. No room exclusivity concept — any section can use any room if free
2. No room assignment for TBD sections — 66 sections stay room='TBD' in output
3. No prescribed-teacher bump — first-placed-first-served, no ownership priority
4. No cross-template validation (T1 ↔ T2 ↔ T4 ↔ T7)

**Key data points:**
- 66 of 371 sections have no prescribed room (14 teachers without rooms)
- 13 teachers have 6th-period approval (PTS_SIXTH_PERIOD = 5,000 boost active)
- Template 9 "Shared Room" column (E) is for simultaneous-use (Gym), NOT exclusivity — separate concept
- Room_raw_priority currently based on demand (sections × 5) — Gym inflated at 150 but irrelevant since PE-only

### Bugs Fixed (institutional memory — consult before writing code in these areas)

| # | Date | Bug | Root Cause | Fix | Location |
|---|------|-----|-----------|-----|----------|
| B1 | 08.07.26 | Students enrolled in unplaced sections (period=None) | `occ_cells()` returns `(None, 'S1')` tuples for unplaced sections — never collide with real periods, so the section looks conflict-free and attracts students into a phantom section that doesn't exist in the bell schedule | Filter `sec_by_code` to exclude sections with `period=None` before Phase B starts; single-point fix protects all 9 downstream `sec_by_code` lookups (Phase B, CSP, `full_reseat`, `full_reseat_fast`) | `schedule_engine_v3.py` ~line 5121, before Phase B |
| B2 | 08.07.26 | Teacher-aware EC rebalance missing from Phase D restarts | `_restore_for_restart()` re-distributes EC sections per-course but does NOT re-run the teacher-aware rebalance. Teachers with FY+EC combos (e.g., Umbrino: 4 FY + 2 EC = S1=6 when both EC→S1) end up over cap on every Phase D restart, preventing placement of FY sections that would fit if one EC were flipped to S2 | Extracted rebalance into `_teacher_aware_ec_rebalance()` function; called from both initial startup (verbose) and `_restore_for_restart()` (silent) | `schedule_engine_v3.py` ~line 3019 (function def), ~line 5573 (restart call) |
| B3 | 08.07.26 | Stale T6 references in engine and CLAUDE.md | Comments, strings, and documentation referenced "Template 6 Sheet 2" and "T6 Column E" for teacher-section assignments and prescribed terms; actual data is in T7 Column H. T6 is `T6_Student Prerequisites` (transcript data) | Corrected 13 engine references and 14 CLAUDE.md references to T7/T2 as appropriate | `schedule_engine_v3.py` (comments/strings), `CLAUDE.md` (documentation) |
| B4 | pre-08.07.26 | Phase B seating order regression — P5 electives lost "first in line" | Global sort order did not account for student priority within same course request priority band | Fixed sort key in Phase B placement loop | `schedule_engine_v3.py` Phase B |
| B5 | pre-08.07.26 | `full_reseat()` course order missing `student_prio` | Inconsistent with Phase B sort — `full_reseat` and `full_reseat_fast` used different ordering than Phase B | Unified sort key (`_full_sort_key`) across Phase B, `full_reseat`, and `full_reseat_fast` | `schedule_engine_v3.py` |
| B6 | pre-08.07.26 | `run_optimization_pass()` acceptance is priority-blind | Optimizer accepted/rejected moves based only on raw conflict count, ignoring whether high-priority or low-priority placements were affected | Added priority-weighted scoring to optimizer acceptance criteria | `schedule_engine_v3.py` Phase D |
| B7 | pre-08.07.26 | Phase D best-solution selection is priority-blind | Best seed selected by total conflicts only, not by priority-weighted score | Changed best-solution comparison to use priority-weighted tuple | `schedule_engine_v3.py` Phase D |
| B8 | pre-08.07.26 | `_compute_conflict_risk()` has two definitions — second is too narrow | Duplicate function definitions with different signatures; second overrode first | Removed duplicate, kept the comprehensive version | `schedule_engine_v3.py` |
| B9 | 08.08.26 | Semester sections from same teacher placed in separate periods when they must share | `greedy_assign_periods()` semester complement bonus only checks same-course sections (`sec_by_code[code]`), not cross-course from same teacher. Teachers with N_FY + N_S1 + N_S2 > max_load need S1+S2 sections from DIFFERENT courses to share periods. Example: Saggio (3 FY + 3 S1 + 3 S2 = 9 sections, 6-period cap) — 741 Psych S1 and 723 PoliSci S2 placed in separate periods, consuming 2 periods when 1 suffices. 710 World History #3 left UNPLACED. | Added `_compute_consolidation_set()` to identify teachers needing cross-course pairing. Added cross-course teacher period consolidation in `greedy_assign_periods()`: HARD floor (score=0.5) for consolidation-required teachers when candidate period has teacher in opposite semester; anti-spread penalty (+50) for empty periods when paired periods available. Recomputed in `_restore_for_restart()` for Phase D consistency. | `schedule_engine_v3.py` ~line 3098 (`_compute_consolidation_set`), ~line 4503 (consolidation bonus in greedy), ~line 5579 (restart recompute) |
| B10 | 08.08.26 | SIR recommends moving section to period where teacher is already teaching | Best-uncovered-period selection loop sets `_a1_best_uncovered` to the period with the most rescuable students regardless of teacher availability. When no teacher is free in that period, `_a1_best_teacher` stays `None`, and the validation block (`if _move_teacher:`) is skipped entirely, leaving `_move_valid = True`. Result: invalid recommendations like "Move 742 Economics D→A" when Zawacki already teaches 752 Economics H in Period A. | Two fixes: (1) Primary — pre-check in the best_uncovered loop: `continue` past any uncovered period where no teacher is free, so `_a1_best_uncovered` only gets set to feasible periods. (2) Defensive — if `_move_teacher` is `None` after selection, explicitly set `_move_valid = False`. | `schedule_engine_v3.py` ~line 7012 (pre-check in loop), ~line 7060 (defensive None check) |
| B11 | 08.08.26 | `course_section_raw()` uses T1 grad_req_dept only — misses T10 grade-aware grad reqs | T1 "Graduation Requirement" column has N/A for Business, but T10 says Business is Required-Either for Gr12. Result: 742 Economics, 752 Economics H, 757 Intl Business Strategy all get CS Raw=0 in Job 1 — placed LAST — causing 161 Business dept conflicts. | `course_section_raw()` now checks T1 first, then falls back to T10 `GRAD_REQ_DEPTS` for any grade. If the course's department is a grad req for ANY grade, it gets PTS_GRAD_REQ. | `schedule_engine_v3.py` ~line 1479 |
| B12 | 08.08.26 | Semester complement/consolidation `min()` floors override Tier 1/2 zero-conflict constraint | `score = min(score, 1.0)` (semester complement) and `score = min(score, 0.5)` (consolidation) could force Tier 2 doubleton sections into high-conflict periods, violating the non-negotiable zero-conflict mandate. | Added `and not zero_conflict` guard to both `min()` floors — Tier 1/2 sections never have their zero-conflict penalty overridden. | `schedule_engine_v3.py` ~line 4580, ~line 4607 |
| B13 | 08.08.26 | `cs_total` cascading amplification — student demand counted 4× | `_section_priority_key` computed `cs_total = cs_raw + max_st + (t_raw + max_st) + (r_raw + t_raw + 2*max_st)` = cs_raw + 4×max_st + 2×t_raw + r_raw. Course importance (max 135 pts) dwarfed by student demand (2000+ pts). Low-priority elective with one hot student outranked grad reqs. | Changed to flat addition: `cs_total = cs_raw + max_student + t_raw + r_raw`. Each component added once. | `schedule_engine_v3.py` ~line 4169 |
| B14 | 08.08.26 | Phase D optimizer `all()` check vastly underestimates new conflicts | `new_conf` estimation required ALL sections of a conflicting course to be in target period. For multi-section courses (e.g., 4 sections), almost never true. Optimizer thought moves were better than they were, wasted iterations. | Changed `all()` to `any()` and added proper semester overlap check per-section. | `schedule_engine_v3.py` ~line 6189 |
| B15 | 08.08.26 | Scoring weights too weak to steer placement | Period load balance (0.1), FY-equivalent (3.0), stipend (0.05), teacher avoid (+2), teacher prefer (-1) were negligible vs conflict penalties. Functioned as noise, not real steering. | Increased to meaningful levels: period load 0.5, FY-equiv 10.0, stipend 0.2, avoid +8, prefer -5. | `schedule_engine_v3.py` ~lines 4672, 4686, 4689, 4695, 4697 |
| B16 | 08.08.26 | Audit log `cs_total` uses different formula than actual sort key | Audit log computed `cs_total = cs_raw + top_st + teacher_total + room_total` (using function-based cascading totals), but sort key used inline formula. Audit values didn't match actual placement order. | Changed audit to match sort key: `cs_total = cs_raw + top_st + t_raw + r_raw`. | `schedule_engine_v3.py` ~line 4791 |

**Bug Pattern Watch List** (classes of bugs to check for when writing new code):
- **Phantom data**: Any code that iterates sections, rooms, teachers, or students must handle `None`/missing values. If `period`, `room`, `teacher`, or `halves` can be `None`, the code must explicitly check. Never assume all sections are placed.
- **Phase D restart consistency**: Any state modified during initial setup (EC redistribution, co-schedule assignment, pairing groups, pre-reservation) must be re-applied in `_restore_for_restart()`. If you add a new setup step, add its restoration.
- **Stale references**: When a template column or sheet is renamed/moved, grep the entire codebase (engine + CLAUDE.md + all .py files) for the old name. Comments and print statements count — they mislead future debugging.
- **FY vs SE counting**: A FY section occupies BOTH S1 and S2 (2 semester-slots, 1 period). A SE section occupies 1 semester-slot, 1 period. Teacher load = unique periods per semester, NOT raw section count. Always count by checking `'S1' in halves` and `'S2' in halves` separately.
- **Cross-course teacher consolidation**: When a teacher's total section count (FY + S1 + S2) exceeds their max load without period sharing, S1 and S2 sections from DIFFERENT courses must be paired into shared periods. The same-course complement bonus alone is insufficient — cross-course pairing is needed. Always check `teacher_sections[teacher]`, not just `sec_by_code[code]`.
- **SIR recommendation feasibility**: Any SIR move recommendation MUST validate that (1) the target period has at least one teacher who is free there, (2) the teacher isn't already teaching in the target period, (3) the teacher actually has a section of this course in the from_period, and (4) the move doesn't create a room conflict. Never recommend a period just because it has the most rescuable students — teacher availability is a hard prerequisite.
- **Dual grad-req code paths**: `course_section_raw()` (Job 1) and `course_request_priority()` (Job 2) MUST agree on graduation requirement status. If T10 says a department is required for any grade, `course_section_raw()` must also recognize it — not just T1. Any new grad req data source must be checked in BOTH functions.
- **Tier 1/2 zero-conflict is absolute**: No scoring floor (`min(score, X)`) or bonus may override the zero-conflict constraint for Tier 1 (Gr12 singletons) or Tier 2 (Gr12 doubletons). Always guard score floors with `and not zero_conflict`.
- **cs_total must be flat**: Each priority component (cs_raw, max_student, t_raw, r_raw) must be added exactly ONCE in `_section_priority_key`. No cascading through intermediate totals that re-include earlier components.
- **T7 display values are pre-computed snapshots**: T7 priority columns (CS Raw, PAE Points, etc.) are for human review only. The engine computes fresh every run. After changing point values or priority logic, re-run the T7 recalculation script to keep display values in sync.
- **Phase D-2 sec_by_code re-add**: When Phase D-2 rescues an unplaced section, it MUST re-add the SID to `sec_by_code[code]`. The Bug B1 filter (before Phase B) permanently removes unplaced SIDs — without re-adding, the rescued section gets a period but `full_reseat()` never enrolls students in it. Always check `if sid not in sec_by_code.get(code, [])` before appending to avoid duplicates.
- **Phase D-2 occ_cells invalidation**: After any period change in Phase D-2 (both the displaced section and the rescued section), `_invalidate_occ_cache()` MUST be called. Stale cache → wrong conflict detection → wrong student placements.
- **Phase D-2 two-step validation**: Displacing a placed section and placing an unplaced section are TWO separate operations requiring TWO separate validity checks. Use `_can_move_section()` for the displaced section (checks constraints for moving from current period to new period). Use `_can_place_unplaced()` for the unplaced section (checks constraints for fresh placement into the freed period). Do NOT use `_can_move_section()` for the unplaced section — it assumes `period` is not None.
