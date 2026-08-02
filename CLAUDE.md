# Don Bosco Prep 2026-27 Master Schedule Builder

## Project Rules

### Engine
- Use **schedule_engine_v3.py** (v3 engine) — NOT v4
- Do NOT change template FORMAT — only add/update data within existing columns
- Do NOT make decisions without user (JC Iofalo) approval

### Semester Locks (2026-27)
- **758 Bloomberg Market Concepts**: S2 ONLY — cannot be placed in S1
- **766**: S1 only
- **765**: S2 only
- These are enforced in `SEMESTER_LOCKS` dict in `schedule_engine_v3.py` (line ~1389) AND in Template 7 `Prescribed Term` column

### Pinned Periods (2026-27)
- **745 LEO I**: Period C (S1), Period E (S1)
- **734 LEO II**: Period C (S2), Period D (S2)

### Key Files
- `schedule_engine_v3.py` — Main engine (4-phase: Period Assignment → Student Seating → Bump Conflicts → Optimization)
- `course_priorities.json` — Graduation requirements, pathway courses, priority config
- `detect_pathways.py` — Pathway detection from Historical Grades + Course Requests
- `templates/` — All input templates (T2, T4, T6, T7, T8, T9, Prior Year, Historical Grades)
- `templates/202526_Master_Schedule_With_Teacher_ID.xlsx` — Official 2025-26 master schedule with teacher names and IDs
- `schedule_solution_v3.json` — Engine output (current: v2.2, 99 clashes, 98.4% placement)

### Current Results (v2.2)
- 99 clashes (all grades 11-12), 98.4% placement
- 0 graduation requirement clashes, 100% grad req fulfillment
- 0 grades 9-10 clashes
- Root cause: 98 period_saturation, 1 singleton_collision
