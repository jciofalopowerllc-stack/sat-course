# AI Master Schedule Builder — Commercial Product Specification

**Product:** AI-Powered Master Schedule Builder
**Developer:** JCiofalo Power LLC
**Pilot School:** Don Bosco Preparatory High School (2026-27 Academic Year)
**Version:** 1.0
**Last Updated:** 2026-08-02

---

## 1. Product Overview

A commercial AI scheduling agent that builds zero-conflict master schedules for high schools. The system takes course requests, teacher assignments, room inventory, and institutional constraints as inputs, then produces a complete master schedule with students seated into sections across configurable periods and semesters.

Don Bosco Preparatory High School serves as the pilot implementation for the 2026-27 academic year. The platform is designed for commercial deployment to any secondary school with similar scheduling needs.

### 1.1 Pilot Configuration (Don Bosco Prep)

| Parameter | Value |
|-----------|-------|
| Students | 805 |
| Courses | 144 |
| Sections | 340 |
| Teachers | 62 |
| Periods | 7 (A–G) |
| Semesters | 2 (S1, S2) |
| Course Requests | 6,556 |
| Rooms | 48 |

### 1.1 Design Principles

- **No PII in the analytical layer.** Students, parents, and staff are keyed to ID numbers. Names, contacts, and photos live only in a separate, access-controlled Identity Layer. Input files containing names are rejected at ingestion.
- **Never fabricate.** Never estimate a course code, credit, grade, prerequisite, or policy. When something cannot be verified, document the uncertainty — do not invent certainty.
- **Deterministic core.** No LLM in any calculation. The scheduling engine is pure algorithmic — greedy assignment, constraint satisfaction, and multi-restart optimization.
- **The system flags and explains; a human decides.**

---

## 2. System Architecture

### 2.1 Scheduling Engine (`schedule_engine_v3.py`)

The core algorithm runs in four phases:

| Phase | Name | Function |
|-------|------|----------|
| A | Assign Periods | Place 340 sections across 7 periods (A–G) using multi-restart greedy optimization |
| B | Seat Students | Place 6,556 course requests using pyramid-level ordering with batch recalculation and ripple scoring |
| C | Bump Conflicts | Resolve remaining conflicts by bumping lower-priority courses, with CSP recovery |
| D | Multi-Restart Optimization | 16 random seeds × 60-iteration priority-aware optimization, keep best solution |

**Current Performance:** 301 conflictes, 95.1% placement, 0 graduation requirement conflictes, 0 P4+ conflictes. All 5,033 graduation requirements fulfilled (100%). All 2,104 AP/Honors placements fulfilled (100%). Remaining 301 conflictes are electives only (253 P1, 40 P2, 8 P3).

### 2.2 Data Inputs

| Source File | Template | Contents |
|-------------|----------|----------|
| Student Course Requests | Template 2 | 2-column format: Student ID, Course Code. 6,556 requests (804 students, 144 courses) |
| Co-Schedule Groups | Template 4 | 4 columns: Group Name, Course Code, Teacher ID, Prescribed Room. 7 groups, 16 entries |
| Teacher Profiles | Template 6, Sheet 1 | 17 columns: ID, name, department, load caps, per-semester 6-period approval, period availability (A-G), SSP Teacher flag, co-schedule approval. 62 teachers |
| Teacher-Course Assignments | Template 6, Sheet 2 | 6 columns: Teacher ID, Course Code, Prescribed Room/Period/Term/Cohort. 340 assignments |
| Course Profiles | Template 7 | 15 columns: code, title, department, credits, term, grade levels, sections, max enrollment, singleton, AP, graduation requirement, cohort, NCAA, prerequisites, corequisites. 144 courses |
| Student Profiles | Template 8, Sheet 1 | 11 columns: ID, name, grade, NCAA, LEO II, LEO I, Academic Support, Pathway, Cohort Name, Cohort Locked. 803 students |
| Room Profiles | Template 9 | 5 columns: Room ID, capacity, available periods, available terms, shared room. 48 rooms |
| Historical Grades | Template_Historical_Grades | 7 columns: Student ID, School Year, Course Code, Section, Final Grade, Pass/Fail, Final Exam Grade. 10,346 records |
| Prior Year Master Schedule | Template_Prior_Year_Master_Schedule | 8 columns: School Year, Course Code, Section, Teacher ID, Room, Period, Term, Enrollment. 398 records |
| Course Priorities | course_priorities.json | 0–5 priority scale for 144 courses with department metadata and graduation requirement rules |

### 2.3 Constraint System

| Constraint Type | Description |
|-----------------|-------------|
| Prescribed Term | Per-section semester placement from T6 Column E: FY (full-year), S1, S2, or EC (Engine Choice — engine decides optimal semester) |
| Period Pin | Section locked to a specific period (LEO courses, co-schedule groups) |
| Teacher Load | Max 5 periods per semester per teacher (6 with approval: FY, S1-only, or S2-only) |
| Room Exclusivity | One section per room per period (except shared rooms with capacity ≥ 100, e.g., Gymnasium) |
| Co-Schedule | Multiple course codes share a single period (e.g., AP Art: 253, 254, 255, 764) |
| Graduation Requirements | Grade-specific department requirements enforced via pyramid Level 1 protection |

---

## 3. Priority System — Student Rank Score

### 3.1 Philosophy — The Pyramid

The scheduling engine builds the master schedule like a pyramid, top-down. Placements at the top of the pyramid have the most restrictions and the biggest ripple effect on everyone else — they are placed first, while the grid is wide open. Placements at the bottom are flexible and absorb whatever periods remain. The goal is a zero-conflict master schedule.

Every placement is a "pebble in the pond." The engine measures how many other placements are affected by each one (the ripple). Bigger ripples get placed earlier within their pyramid level. After a batch of placements, the pond has changed — scarcity, conflict risk, and ripple scores are recalculated before the next batch.

### 3.1a Pyramid Levels

Each student-course placement is classified into one of four pyramid levels based on how critical and how constrained it is:

| Level | Score | Name | Description |
|-------|-------|------|-------------|
| 1 (top) | 100+ | Graduation Required | Student MUST take this course to graduate. Department is required for their grade level. |
| 2 | 50-55 | No Alternative | Only 1-2 sections exist and no substitute course is available. Includes singletons (Guitar, Robotics, AP Art, etc.) and P5 courses. |
| 3 | 25-30 | Limited Choice | Few sections available (3 or fewer) and course priority is 3+. Hard to reschedule if bumped. |
| 4 (base) | 0-5 | Flexible | Many sections available. Easy to move around. Absorbs whatever remains. |

Score separation ensures no level can be confused with another: lowest Level 1 (100) is always higher than highest Level 2 (55).

Levels 1 and 2 are **protected** — they cannot be bumped to make room for a lower-level placement.

### 3.2 Ten Raw Inputs

Each student-course-section placement is scored across 10 dimensions. Each dimension is scored 0–5.

| # | Input | Code | Scale | Source |
|---|-------|------|-------|--------|
| 1 | Course File Priority | CFP | 0–5 | Master course profile (stable year-to-year) |
| 2 | Current Year Course Request Priority | CYRP | 0–5 | Set during pre-scheduling based on current demand and teacher availability |
| 3 | Student Scheduling Priority | SSP | 0–5 | Based on student population: LEO, Pathway, Academic Support (multi-membership allowed) |
| 4 | Master Teacher Profile Priority | MTP | 0–5 | Teacher profile: seniority, specialization, replaceability |
| 5 | Current Year Teacher Assignment Priority | CTAP | 0–5 | How critical this specific teacher-course assignment is this year |
| 6 | Term Lock | TL | 0 or 5 | Binary: must be a specific semester (5) or flexible (0) |
| 7 | Period Lock | PL | 0 or 5 | Binary: must be a specific period (5) or flexible (0) |
| 8 | Room Lock | RL | 0 or 5 | Binary: must be a specific room (5) or flexible (0) |
| 9 | Scarcity | SC | 0–5 | Computed: fewer sections = higher score (1 section=5, 2=4, 3=3, 4-5=2, 6+=1) |
| 10 | Conflict Risk | CR | 0–5 | Computed: count of student's other requests sharing period slots with this course |

### 3.3 Priority Scale Definitions

| Value | Label | Description |
|-------|-------|-------------|
| 0 | Elective-Flexible | No scheduling constraint; absorbs remaining capacity |
| 1 | Elective-Standard | Standard elective with minimal constraints |
| 2 | Departmental Core | Department-level requirement, moderate demand |
| 3 | Sequence/Honors | Sequential or honors course, prerequisites constrain placement |
| 4 | Required Core | Graduation requirement, high demand, limited alternatives |
| 5 | AP/Singleton/Locked | AP course, singleton section, or hard-locked constraint — no alternative exists |

### 3.4 Weighted Scoring

Not all inputs are equally important. Weights reflect how hard each constraint is to work around:

| # | Input | Weight | Rationale |
|---|-------|--------|-----------|
| 1 | Course File Priority | ×1.0 | Stable baseline |
| 2 | Current Year Course Request Priority | ×1.5 | Reflects current-year demand and scarcity |
| 3 | Student Scheduling Priority | ×2.0 | LEO/special populations must be protected |
| 4 | Master Teacher Profile Priority | ×1.0 | Stable baseline |
| 5 | Current Year Teacher Assignment Priority | ×1.5 | Reflects current-year staffing constraints |
| 6 | Term Lock | ×2.0 | Binary hard constraint — no alternative semester |
| 7 | Period Lock | ×2.0 | Binary hard constraint — no alternative period |
| 8 | Room Lock | ×1.5 | Hard but rooms can sometimes flex |
| 9 | Scarcity | ×1.5 | Fewer available sections = harder to place |
| 10 | Conflict Risk | ×1.5 | More period overlaps with other requests = higher risk |

**Maximum Weighted Sum:** 77.5 (all inputs at 5 with maximum weights)

### 3.4a SSP (Student Special Priority) — Multi-Membership

Students can belong to 1, 2, or all 3 special populations simultaneously. The SSP score is the MAX of their memberships:

| Population | SSP Score | Description |
|------------|-----------|-------------|
| LEO | 5 | LEO II learning community cohort members |
| Pathway | 4 | Pathway program students |
| Academic Support | 3 | Students receiving academic support services |
| Standard | 1 | No special population membership |

A student who is both LEO (5) and Pathway (4) receives SSP = 5 (the maximum). Template 8 records each membership as a separate Y/N flag (LEO II, Pathway, Academic Support).

### 3.4b TSSP (Teacher Special Population Priority)

TSSP mirrors SSP on the teacher side. Teachers who serve special populations receive higher priority in scheduling to protect those students' access. The TSSP score is the MAX of populations served:

| Population Served | TSSP Score | Description |
|-------------------|------------|-------------|
| Teaches LEO courses | 5 | Teacher assigned to LEO cohort courses |
| Teaches Pathway courses | 4 | Teacher assigned to Pathway program courses |
| Teaches Academic Support courses | 3 | Teacher assigned to academic support courses |
| Standard | 1 | No special population courses |

A teacher who teaches both LEO (5) and Pathway (4) courses receives TSSP = 5. Template 6 records each membership as a separate Y/N flag (Teaches LEO, Teaches Pathway, Teaches Acad Support) and stores the computed TSSP.

### 3.5 Constraint Count

The number of raw inputs scoring ≥ 4. This measures how many dimensions are simultaneously constrained.

- A student with 6 constraints is more restricted than one with 2 constraints, even if their weighted sums are similar.
- Constraint count serves as the **primary sort key** for student ranking.

### 3.6 Student Rank Score

Each student is ranked 1–800 (most restricted to least restricted) using a two-key sort:

1. **Primary:** Constraint Count (descending) — more constrained students first
2. **Secondary:** Weighted Sum (descending) — among students with equal constraint counts, higher weighted sums first

### 3.7 Scheduling Order

Placements are sorted globally (not per-student) using a five-key ordering:

1. **Pyramid Level** (highest first) — graduation requirements before no-alternatives before limited-choice before flexible
2. **Ripple Score** (biggest first) — placements that affect the most other placements go first
3. **Composite Score** (constraint count, then weighted sum) — most constrained first
4. **Section Count** (fewest first) — courses with fewer sections are harder to place
5. **Student Rank** (tiebreaker) — most constrained student first

Placements are made in batches. After each batch, scarcity, conflict risk, and ripple scores are recalculated because the pond has changed. Remaining placements are re-sorted with the updated scores before the next batch.

### 3.8 Per-Placement Composite

The same course section produces different composite scores for different students. Example:

| Dimension | LEO Student → Stoller AP | Regular Student → Stoller AP |
|-----------|--------------------------|-------------------------------|
| Course File Priority | 5 (AP) | 5 (AP) |
| Current Year Course Request Priority | 5 (singleton) | 5 (singleton) |
| **Student Scheduling Priority** | **5 (LEO)** | **1 (regular)** |
| Master Teacher Profile Priority | 4 (Stoller) | 4 (Stoller) |
| Current Year Teacher Assignment Priority | 5 (only section) | 5 (only section) |
| Term Lock | 5 (locked S1) | 5 (locked S1) |
| Period Lock | 5 (locked B) | 5 (locked B) |
| Room Lock | 0 (flexible) | 0 (flexible) |
| Scarcity | 5 (singleton) | 5 (singleton) |
| Conflict Risk | 2 (some overlap) | 2 (some overlap) |
| **Weighted Sum** | **62.5** | **54.5** |
| **Constraint Count** | **7** | **6** |

The LEO student ranks higher and gets placed first — their seat is guaranteed before the regular student is considered.

---

## 4. Data Files

### 4.1 Engine Data

| File | Format | Purpose |
|------|--------|---------|
| `course_priorities.json` | JSON | Priority scale (0–5) for 144 courses, department metadata, graduation requirement rules by grade level |
| `priority_assignments.json` | JSON | Weighted scoring system: 10 input weights, per-course/student/teacher priority assignments |
| `schedule_solution_v3.json` | JSON | Complete engine output: sections, student assignments, conflictes, room assignments, stats |

### 4.2 Interactive Boards (9 HTML files in `boards/`)

| File | Purpose |
|------|---------|
| `index.html` | Dashboard hub with summary stats (conflictes, placement rate, students, sections) |
| `master_schedule_builder.html` | Full course catalog (144 courses) with student request management and validation |
| `student_conflict_report.html` | Drag-and-drop schedule grid for students with conflicts, visual period/semester layout |
| `conflict_resolution_console.html` | Course-level conflict analysis with fix recommendations for affected courses |
| `student_request_recommendations.html` | Alternative course options for bumped requests with availability details |
| `singleton_board.html` | Scheduling grid for 47 singleton courses, teacher-period conflict view |
| `constraint_builder.html` | Configure semester locks, period locks, and co-schedule constraints for 138 courses |
| `credit_validation_report.html` | Students exceeding the 35-credit cap with priority-ranked drop candidates |
| `data_source_audit_report.html` | Cross-file integrity checks and data quality findings |

### 4.3 Reports

| File | Format | Purpose |
|------|--------|---------|
| `Unfulfilled_Requests_Report.xlsx` | Excel | 301 unfulfilled requests: Student ID, name, grade, course, priority band, root cause, blocking courses |
| `Preflight_Validation_Report.xlsx` | Excel | Pre-build validation: credit checks, prerequisite verification, duplicate detection |

### 4.4 Analytics

| File | Format | Purpose |
|------|--------|---------|
| `analyze_conflictes.py` | Python | Conflict analysis and diagnostics tooling |
| `apply_singleton_changes.py` | Python | Utility to apply board changes back to engine |
| `STUDENT_RANK_SCORE_SAMPLE_20.xlsx` | Excel | 20-student sample demonstrating the priority scoring system |

---

## 5. Pilot Results (Don Bosco Prep)

### 5.1 Engine Results History

| Version | Conflictes | Placement | Grad Req Conflictes | Notes |
|---------|---------|-----------|------------------|-------|
| v1.0 (single-tier) | 207 | 96.8% | 0 P5 | Original engine, single priority scale |
| v1.1 (composite scoring) | 325 | 95.1% | 0 P5 | Phase B refactor regressed ordering |
| v1.2 (three-band fix) | 240 | 95.1% | 0 P5 | Three-band priority + priority-aware optimization |
| v2.0 (pyramid + ripple) | 338 | 94.5% | 0 (incorrect) | Four-level pyramid system. Graduation req detection bug: "Language" vs "World Language" mismatch, PE missing |
| v2.1 (grad req fix) | 301 | 95.1% | 0 (verified) | Fixed graduation req config: "World Language" match, PE added for grades 9-10. All 5,033 grad reqs fulfilled |
| v2.2 (pathway elevation) | **99** | **98.4%** | **0** | Pathway detection from Historical Grades + Course Requests. 625/805 students assigned to named pathways. Pathway courses elevated to Level 2. Grades 9-10 conflictes eliminated |

### 5.2 Current Configuration

| Metric | Value |
|--------|-------|
| Total Sections | 340 |
| Total Courses | 144 |
| Total Teachers | 62 |
| Total Students | 804 |
| Total Rooms | 48 |
| Total Requests | 6,556 |
| Pyramid Levels | 4 (Graduation Required, No Alternative, Limited Choice, Flexible) |
| Protected Levels | 1 and 2 (cannot be bumped) |
| Restart Seeds | 16 |
| Optimization Iterations | 60 per restart |
| Batch Recalculation Size | 1,500 placements |

### 5.3 Current Results (v2.2)

| Metric | Value |
|--------|-------|
| Conflictes | 99 |
| Placement Rate | 98.4% (6,052/6,151) |
| Graduation Req Fulfillment | 100% (5,033/5,033) |
| AP/Honors Fulfillment | 100% (2,104/2,104) |
| P4+ Conflictes | 0 |
| Students Affected | 86 |
| Prior-Year Alignment | 237/316 |
| Pathway Students Identified | 625/805 |

### 5.4 Conflict Breakdown (v2.2)

| Category | Count |
|----------|-------|
| P1 (Elective-Standard) | 58 |
| P2 (Departmental Core) | 34 |
| P3 (Sequence/Honors) | 7 |
| P4+ (Required Core) | 0 |

| Department | Count |
|------------|-------|
| Physical Education | 34 |
| Science | 25 |
| Business | 21 |
| Communication Arts | 9 |
| Computer Science | 5 |
| Humanities | 5 |

| Grade | Count |
|-------|-------|
| Grade 9 | 0 |
| Grade 10 | 0 |
| Grade 11 | 55 |
| Grade 12 | 44 |

### 5.5 Target

| Metric | Target |
|--------|--------|
| Conflictes | 0 |
| Placement Rate | 100% |
| P4+ Conflictes | 0 |

---

## 6. Roadmap

### 6.1 Completed (v1.0)

- [x] Four-phase scheduling engine (period assignment, student seating, conflict resolution, multi-restart optimization)
- [x] Course priority scale (0-5) integrated into all engine decision points
- [x] Interactive singleton board with drag-and-drop
- [x] Student conflict report with impact analysis
- [x] Conflict resolution console
- [x] Constraint builder UI
- [x] Room conflict resolution (28 moves, 0 remaining)
- [x] Semester lock and full freedom support
- [x] Co-schedule groups
- [x] LEO cohort pinning

### 6.2 Completed (v2.0 — Student Rank Score + Pyramid + Ripple)

- [x] 10-input weighted priority scoring per student-course-section placement (CFP, CYRP, SSP, MTP, CTAP, TL, PL, RL, SC, CR)
- [x] Student ranking 1-805 by constraint density
- [x] SSP multi-membership: students belong to 1, 2, or all 3 populations (LEO, Pathway, Academic Support)
- [x] TSSP (Teacher Special Population Priority): derived from SSP Teacher flag in Template 6
- [x] Per-semester approved 6-period load (Full-Year, S1-only, S2-only)
- [x] Template 6 header-based column lookup (17 columns, no hardcoded indices)
- [x] Template 8 student profiles reading (LEO, Pathway, Academic Support flags)
- [x] Engine reads TSSP from Template 6 SSP Teacher flag and SSP from Template 8
- [x] Course-Teacher Lock codes read from Template 6 instead of hardcoded
- [x] Current year course request priority data input (CYRP — improved formula, singletons 3-5)
- [x] Master teacher profile priority data input (MTP — cross-referenced with Template 6)
- [x] Current year teacher assignment priority data input (CTAP — sole teachers set to 5)
- [x] Engine refactor: replace single-tier `prio(c)` with composite placement scoring
- [x] Most-constrained-first scheduling order (composite-sorted, student rank tiebreaker)
- [x] Four-level pyramid system (Graduation Required > No Alternative > Limited Choice > Flexible)
- [x] Ripple scoring — measures cross-impact of each placement on the rest of the schedule
- [x] Batch recalculation in Phase B — recalculate scores between batches as the schedule fills
- [x] Priority-aware optimization — prevents trading high-priority conflictes for low-priority ones
- [x] Priority-aware conflict estimation — optimizer penalizes moves that create high-priority conflicts
- [x] Post-bump CSP recovery — after bumping, rearrange remaining placements to recover seats
- [x] Per-restart seating order recomputation — each restart recalculates scores for its specific period layout
- [x] Conflict risk fix — any period overlap (not just single-period exact match)
- [x] Memory optimization — fast reseat for optimizer, workbook cleanup, garbage collection between restarts

### 6.3 Completed (v2.1 — Data Loading Adaptation + Graduation Requirement Fix)

- [x] V3 engine data loading rewritten to read current v4-format templates (DO NOT change templates)
- [x] Teacher ID→Name mapping built from Template 6 Sheet 1 (v3 keys on teacher names, not IDs)
- [x] Template 2 loader: 2-column format (Student ID, Course Code), joins names/grades from Template 8
- [x] Template 6 loader: fixed header names ("Avail Period X", "Special Student Population Teacher", "Approved 6th Period FY"), data starts row 3
- [x] Template 7 loader: header-based column lookup, 15 columns, skips non-numeric course codes
- [x] Template 8 loader: fixed data start row 2→3, reads LEO/Pathway/Academic Support/Cohort flags
- [x] Transcript loader: reads from Template_Historical_Grades.xlsx (10,346 records) instead of empty Template 8 Sheet 2
- [x] Prior year loader: reads Template_Prior_Year_Master_Schedule.xlsx (398 records), maps teacher IDs to names
- [x] Co-schedule loader: reads new format (one course per row, 4 columns, grouped by name)
- [x] Template 9 room profiles: 48 rooms with capacity, availability, shared room flag
- [x] Shared room fix: only Gymnasium (capacity ≥ 100 AND Shared=Y) allows simultaneous sections — prevents 46/48 rooms from being treated as shared
- [x] Graduation requirement bug fix: "Language" → "World Language" in course_priorities.json to match Template 7 department names
- [x] Physical Education added to graduation requirements for grades 9-10 only (not required grades 11-12)
- [x] Engine reads grade-specific PE requirements via `grades_9_10_extra` config section in course_priorities.json
- [x] Result: 338→301 conflictes, 94.5%→95.1% placement, 0 graduation requirement conflictes (verified correct)
- [x] Unfulfilled Requests Report generated (Excel): 301 requests, 290 students, sorted by priority band
- [x] 9 interactive HTML boards generated: conflict report, conflict console, recommendations, singleton board, constraint builder, master schedule builder, credit validation, data audit, dashboard index

### 6.4 Completed (v2.2 — Pathway Course Elevation)

- [x] Pathway detection from Historical Grades: identify each student's pathway (Business, CS, Engineering, Fine Arts, Music Arts, Communication Arts, Theater) using completed course history
- [x] Detection rules: G12 = 2+ courses, G11 = 1+ course, G10 = G9 history + G10 requests, G9 = elective request match. Tie-break = most matches. All LEO = Business pathway
- [x] Added `pathway_courses` mapping to `course_priorities.json` (8 pathways, 45 course codes total)
- [x] Created `detect_pathways.py` — updates Template 8 Pathway column with pathway name for 625/805 students
- [x] Modified `student_prio()`: elevate pathway courses to Level 2 (No Alternative) for enrolled pathway students
- [x] Result: 301→99 conflictes (-67%), 95.1%→98.4% placement, grades 9-10 conflictes eliminated (149→0)
- [ ] 6 pathway courses not in Template 7: App Development, Chorus, Music Service, Music Service Project, Tech Theater Level I, The Story Lab

### 6.5 Completed (v3.0 — Three-Tier Section Placement + Phase A Overhaul)

- [x] Three-Tier Section Placement (Universal Rules — from JC Iofalo, non-negotiable):
  - Tier 1: Grade 12 Singletons placed FIRST, by priority, ZERO student conflicts (hard constraint)
  - Tier 2: Grade 12 Doubletons placed SECOND, by priority, ZERO student conflicts (hard constraint)
  - Tier 3: All Other Sections placed LAST, by priority values with weighted conflict scoring
- [x] `_section_tier(code)` function classifies sections by Gr12 eligibility + section count
- [x] `greedy_assign_periods()` restructured: three-pass tier loop, each tier processes sections by priority
- [x] Conflict penalty weight fix: was `* 0.5` (too weak), now `* 5.0` singletons / `* 2.0` others (Tier 3), `* 10000` (Tiers 1 & 2)
- [x] Period spreading: applies to ALL courses with 2+ sections, proportional penalty `+25 * sections_in_period`
- [x] Co-schedule exclusion: `_predict_conflict_score()` skips co-scheduled courses (one section, not a conflict)
- [x] Audit log records tier for each placement

### 6.6 Future

- [ ] Admin interface for entering/adjusting all 10 priority inputs
- [ ] Real-time constraint count and weighted sum display during data entry
- [ ] Student rank score dashboard — visual ranking of all 800 students
- [ ] What-if analysis: preview ranking impact of priority changes before committing
- [ ] Multi-year priority history tracking
- [ ] Automated priority recommendations based on historical data
