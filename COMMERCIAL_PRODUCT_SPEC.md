# AI Master Schedule Builder — Commercial Product Specification

**Product:** AI-Powered Master Schedule Builder
**Developer:** JCiofalo Power LLC
**Pilot School:** Don Bosco Preparatory High School (2026-27 Academic Year)
**Version:** 1.0
**Last Updated:** 2026-07-29

---

## 1. Product Overview

A commercial AI scheduling agent that builds zero-conflict master schedules for high schools. The system takes course requests, teacher assignments, room inventory, and institutional constraints as inputs, then produces a complete master schedule with students seated into sections across configurable periods and semesters.

Don Bosco Preparatory High School serves as the pilot implementation for the 2026-27 academic year. The platform is designed for commercial deployment to any secondary school with similar scheduling needs.

### 1.1 Pilot Configuration (Don Bosco Prep)

| Parameter | Value |
|-----------|-------|
| Students | 800 |
| Courses | 141 |
| Sections | 350 |
| Teachers | 64 |
| Periods | 7 (A–G) |
| Semesters | 2 (S1, S2) |
| Course Requests | 6,512 |

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
| A | Assign Periods | Place 350 sections across 7 periods (A–G) using multi-restart greedy optimization |
| B | Seat Students | Place 6,512 course requests using greedy warm-start + CSP re-solve |
| C | Bump Conflicts | Resolve remaining conflicts by bumping lower-priority courses |
| D | Multi-Restart Clash Resolution | 8 random seeds, full re-seat per seed, keep best solution |

**Current Performance:** 207 clashes, 96.8% placement rate (6,305/6,512), zero P5 (AP/Singleton) clashes.

### 2.2 Data Inputs

| Source File | Contents |
|-------------|----------|
| Course Sectioning Template | Course codes, titles, departments, credits, types, section counts, teacher assignments, rooms |
| Student Course Requests | Student ID, grade, 8 course requests per student (800 students) |
| LEO II Cohorts A & B | 36 students in LEO learning community with pinned schedules |
| Principals Prescribed Course Sections | Authoritative section/teacher/period assignments |
| Semester Designations | S1/S2 locks, full freedom courses, split rules |
| Course Priorities | 0–5 priority scale for 141 courses |
| Co-Schedule Groups | Course groups that must share a period (AP Art, Guitar, Theater, etc.) |
| Teacher Profiles (Template 6) | 48 columns: departments, load caps, per-semester 6-period approval, period availability, SSP Teacher flag, certifications, computed MTP |
| Student Profiles (Template 8) | 21 columns: grade, SSP, multi-membership flags (LEO, Pathway, Academic Support), IEP, cohort |

### 2.3 Constraint System

| Constraint Type | Description |
|-----------------|-------------|
| Semester Lock | Course must run in S1 or S2 only (e.g., 766→S1, 765→S2) |
| Full Freedom | Course sections split freely across semesters (e.g., 849, 851) |
| Period Pin | Section locked to a specific period (LEO courses, co-schedule groups) |
| Teacher Load | Max 5 periods per semester per teacher (6 with approval) |
| Room Exclusivity | One section per room per period |
| Co-Schedule | Multiple course codes share a single period (e.g., AP Art: 253, 254, 255, 764) |
| Protected Courses (PROT) | P5 courses never bumped during conflict resolution |

---

## 3. Priority System — Student Rank Score

### 3.1 Philosophy

The scheduling engine builds the master schedule in order of constraint density. Placements with the most restrictions are locked in first, while the grid is wide open and conflict-free. Flexible placements go last, absorbing whatever periods remain. The goal is a zero-conflict master schedule.

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

1. Rank all 800 students by Student Rank Score (most restricted first)
2. For each student, rank their course requests by Placement Composite Score (highest first)
3. Student #1's highest-scoring placement enters a wide-open grid — guaranteed no conflict
4. Work through all 800 students in rank order
5. By the time flexible students are reached, their flexible courses absorb whatever periods remain

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
| `course_priorities.json` | JSON | Priority scale (0–5) for 141 courses with department and section metadata |
| `semester_designations.json` | JSON | 45 semester placement rules: pinned, prescribed S1/S2, split, builder choice |
| `schedule_solution.json` | JSON | Complete engine output: sections, student assignments, clashes, room assignments |

### 4.2 Interactive Tools

| File | Format | Purpose |
|------|--------|---------|
| `master_schedule_builder.html` | HTML | Master worksheet with course tally, manual review, grade-level views |
| `singleton_board.html` | HTML | Drag-and-drop scheduling board with zoom, conflict detection, export |
| `conflict_resolution_console.html` | HTML | Interactive console for resolving remaining scheduling conflicts |
| `constraint_builder.html` | HTML | Structured constraint entry form: semester locks, full freedom, co-schedule |
| `student_clash_report.html` | HTML | Per-student conflict report with drag-drop reassignment and impact analysis |
| `student_request_recommendations.html` | HTML | Course request analysis and recommendations |

### 4.3 Analytics

| File | Format | Purpose |
|------|--------|---------|
| `analyze_clashes.py` | Python | Clash analysis and diagnostics tooling |
| `apply_singleton_changes.py` | Python | Utility to apply board changes back to engine |
| `STUDENT_RANK_SCORE_SAMPLE_20.xlsx` | Excel | 20-student sample demonstrating the priority scoring system |

---

## 5. Pilot Results (Don Bosco Prep)

### 5.1 Current Engine Results (v1.0)

| Metric | Value |
|--------|-------|
| Total Sections | 350 |
| Total Courses | 141 |
| Total Teachers | 64 |
| Total Students | 800 |
| Total Requests | 6,512 |
| Placed | 6,305 (96.8%) |
| Clashes | 207 |
| P5 (AP/Singleton) Clashes | 0 |
| Section Sizes | min=1, max=71, avg=18.0 |
| Teacher Load Violations | 3 |
| Room Conflicts | 0 (28 resolved via reassignment) |

### 5.2 Clash Distribution by Priority

| Priority | Label | Clashes |
|----------|-------|---------|
| P1 | Elective-Standard | 95 |
| P2 | Departmental Core | 29 |
| P3 | Sequence/Honors | 74 |
| P4 | Required Core | 9 |
| P5 | AP/Singleton | 0 |

### 5.3 Target (v2.0 with Student Rank Score)

| Metric | Target |
|--------|--------|
| Clashes | 0 |
| Placement Rate | 100% |
| P4+ Clashes | 0 |

---

## 6. Roadmap

### 6.1 Completed (v1.0)

- [x] Four-phase scheduling engine (period assignment, student seating, conflict resolution, multi-restart optimization)
- [x] Course priority scale (0–5) integrated into all engine decision points
- [x] Protected courses (PROT) — P5 courses never bumped
- [x] Interactive singleton board with drag-and-drop
- [x] Student clash report with impact analysis
- [x] Conflict resolution console
- [x] Constraint builder UI
- [x] Room conflict resolution (28 moves, 0 remaining)
- [x] Semester lock and full freedom support
- [x] Co-schedule groups
- [x] LEO cohort pinning

### 6.2 In Progress (v2.0 — Student Rank Score)

- [x] 10-input weighted priority scoring per student-course-section placement (CFP, CYRP, SSP, MTP, CTAP, TL, PL, RL, SC, CR)
- [x] Student ranking 1–800 by constraint density
- [x] SSP multi-membership: students belong to 1, 2, or all 3 populations (LEO, Pathway, Academic Support)
- [x] TSSP (Teacher Special Population Priority): derived from SSP Teacher flag in Template 6
- [x] Per-semester approved 6-period load (Full-Year, S1-only, S2-only)
- [x] Template 6 header-based column lookup (48 columns, no hardcoded indices)
- [x] Template 8 student profiles reading (LEO, Pathway, Academic Support flags)
- [x] Engine reads TSSP from Template 6 SSP Teacher flag and SSP from Template 8
- [x] Course-Teacher Lock codes read from Template 6 instead of hardcoded
- [x] Current year course request priority data input (CYRP — improved formula, singletons 3-5)
- [x] Master teacher profile priority data input (MTP — cross-referenced with Template 6)
- [x] Current year teacher assignment priority data input (CTAP — sole teachers set to 5)
- [x] Engine refactor: replace single-tier `prio(c)` with composite placement scoring
- [x] Most-constrained-first scheduling order (composite-sorted, student rank tiebreaker)

### 6.3 Future

- [ ] Admin interface for entering/adjusting all 10 priority inputs
- [ ] Real-time constraint count and weighted sum display during data entry
- [ ] Student rank score dashboard — visual ranking of all 800 students
- [ ] What-if analysis: preview ranking impact of priority changes before committing
- [ ] Multi-year priority history tracking
- [ ] Automated priority recommendations based on historical data
