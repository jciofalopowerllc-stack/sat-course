# Don Bosco Prep — Schedule Engine Report Formats

Reference for all reports generated from `schedule_engine_v3.py` output. Report format definitions are stored in the engine's `REPORT_FORMATS` dict.

---

## 1. Master Section Report

**File:** `Master_Section_Report_2026_27.xlsx`

One row per course section showing teacher assignment, period, term, and enrollment.

| Column | Header | Width | Align |
|--------|--------|-------|-------|
| A | Teacher ID | 12 | Center |
| B | Teacher Name | 25 | Left |
| C | Period | 8 | Center |
| D | Term | 6 | Center |
| E | Course Code | 12 | Center |
| F | Section # | 10 | Center |
| G | Course Title | 40 | Left |
| H | Section Enrollment | 18 | Center |

- **Term values:** S1, S2, or FY
- **Sort:** Teacher Name, then Period
- **Source:** `schedule_solution_v3.json` + Template 6 (teacher IDs)
- **Features:** Auto-filter, freeze row 1, alternating row shading, dark-blue header

---

## 2. Teacher Schedule Review & Tally

**File:** `Teacher_Schedule_Review_and_Tally.xlsx`

Side-by-side comparison of 2025-26 vs 2026-27 schedules per teacher, with section and consecutive-period tallies.

| Column | Content |
|--------|---------|
| A | Teacher Name (repeated for each period row) |
| B | Period (A through G) |
| C | Spacer (gray fill) |
| D | 2026-27 S1 courses |
| E | 2026-27 S2 courses |
| F | Spacer (gray fill) |
| G | 2025-26 S1 courses |
| H | 2025-26 S2 courses |

**Per-teacher block (10 rows):**
- Row 1: Year headers (2026-2027, 2025-2026)
- Row 2: Semester sub-headers (S1, S2) + Teacher ID
- Rows 3-9: Period A through G with course assignments
- Row 10: TOTAL SECTIONS (red font)
- Row 11: TOTAL CONSECUTIVE PERIODS (red font if >= 4)
- Row 12: Blank separator

- **Empty slots:** "UNASSIGNED" in bold
- **Source:** `schedule_solution_v3.json` + `202526_Master_Schedule_With_Teacher_ID.xlsx`

---

## 3. Remaining Clashes

**File:** `Remaining_Clashes_v2.5.xlsx`

All unplaced student-course pairs with diagnostic root cause analysis.

| Column | Header | Width | Align |
|--------|--------|-------|-------|
| A | Student ID | 12 | Center |
| B | Student Name | 22 | Left |
| C | Grade | 8 | Center |
| D | Course Code | 12 | Center |
| E | Course Title | 35 | Left |
| F | Course Request Priority | 8 | Center |
| G | Priority Label | 18 | Center |
| H | Grad Req? | 10 | Center |
| I | Lost Period | 12 | Center |
| J | Lost Semester | 12 | Center |
| K | Root Cause | 20 | Left |
| L | Blocking Courses | 45 | Left |

- **Sort:** Course Request Priority (descending), then Grade
- **Tabs:** "Remaining Clashes" (detail) + "Summary" (by grade, priority label, grad req count)
- **Source:** `schedule_solution_v3.json` clashes array
- **Features:** Auto-filter, freeze row 1, alternating row shading, dark-red header

---

## 4. Student Schedule Report

**File:** `Student_Schedule_Report_2026_27.xlsx`

Complete student schedules with S1/S2 split per period, credit values, and clashes.

**Header rows:**
- Row 1: Student ID, Student Name, Grade, then merged "Period A" through "Period G" headers, Total Sections, Total Credits, Clashes
- Row 2: Blank under first 3 cols, then S1/S2 sub-headers under each period

| Column | Content |
|--------|---------|
| A | Student ID |
| B | Student Name |
| C | Grade |
| D | Period A — S1 |
| E | Period A — S2 |
| F | Period B — S1 |
| G | Period B — S2 |
| H | Period C — S1 |
| I | Period C — S2 |
| J | Period D — S1 |
| K | Period D — S2 |
| L | Period E — S1 |
| M | Period E — S2 |
| N | Period F — S1 |
| O | Period F — S2 |
| P | Period G — S1 |
| Q | Period G — S2 |
| R | Total Sections |
| S | Total Credits |
| T | Clashes |

- **Cell format:** `CourseCode: CourseTitle (Credits cr)`
- **Empty semester slot:** "UNASSIGNED" (bold red font)
- **Credits:** Per-course value from Template 7, column D
- **Total Credits:** Sum of all assigned course credits for the school year
- **Clashes:** Semicolon-separated list of unplaced courses (red font)
- **Sort:** Grade, then Student Name
- **Source:** `schedule_solution_v3.json` assignments + Template 7 (credits)
- **Features:** Auto-filter, freeze row 2, alternating row shading, merged period headers

---

## 5. Incomplete Student Schedules

**File:** `Incomplete_Student_Schedules_2026_27.xlsx`

Only students who have at least one UNASSIGNED period/semester slot. Same layout as the Student Schedule Report with an added Unassigned Slots column.

**Header rows:**
- Row 1: Student ID, Student Name, Grade, then merged "Period A" through "Period G" headers, Total Sections, Total Credits, Unassigned Slots, Clashes
- Row 2: Blank under first 3 cols, then S1/S2 sub-headers under each period

| Column | Content |
|--------|---------|
| A | Student ID |
| B | Student Name |
| C | Grade |
| D | Period A — S1 |
| E | Period A — S2 |
| F | Period B — S1 |
| G | Period B — S2 |
| H | Period C — S1 |
| I | Period C — S2 |
| J | Period D — S1 |
| K | Period D — S2 |
| L | Period E — S1 |
| M | Period E — S2 |
| N | Period F — S1 |
| O | Period F — S2 |
| P | Period G — S1 |
| Q | Period G — S2 |
| R | Total Sections |
| S | Total Credits |
| T | Unassigned Slots |
| U | Clashes |

- **Filter:** Students where any Period A–G × S1/S2 slot is UNASSIGNED
- **Cell format:** `CourseCode: CourseTitle (Credits cr)`
- **Empty semester slot:** "UNASSIGNED" (bold red font)
- **Unassigned Slots:** Count of empty S1/S2 slots across all 7 periods (bold red)
- **Sort:** Unassigned Slots (descending), then Grade, then Student Name
- **Tabs:** "Incomplete Schedules" (detail) + "Summary" (by grade, slot count distribution)
- **Source:** `schedule_solution_v3.json` assignments + Template 7 (credits)
- **Features:** Auto-filter, freeze row 2, alternating row shading, merged period headers, dark-red header

---

## 6. Course Request Report

**File:** `Course_Request_Report_2026_27.xlsx`

Per-course fulfillment showing total requests vs scheduled vs unscheduled with percentage.

| Column | Header | Width | Align | Notes |
|--------|--------|-------|-------|-------|
| A | Course Code | 13 | Center | Numeric, ascending |
| B | Course Title | 42 | Left | From Template 7 |
| C | Department | 22 | Left | From Template 7 |
| D | Total Requests | 16 | Center | Count of students requesting this course |
| E | Requests Scheduled | 18 | Center | Count successfully placed |
| F | Requests Unscheduled | 20 | Center | Bold red if > 0 |
| G | % Scheduled | 14 | Center | Format: 0.0% — green if 100%, red if < 75%, amber if < 90% |

- **Grand Total Row:** Bottom row with "GRAND TOTAL" label, blue fill, all columns summed
- **Sort:** Course Code (numeric ascending)
- **Source:** Template 2 (student requests) + `schedule_solution_v3.json` assignments + Template 7 (course info)
- **Features:** Auto-filter, freeze row 1, alternating row shading

---

## 7. Preflight Validation Report

**File:** `Preflight_Validation_Report.xlsx`

Auto-generated by the engine during Phase 0. Flags data issues before scheduling runs.

**Tabs:**
- Summary — counts by warning type
- Duplicates — students re-requesting courses they already passed
- Prereq-With Transcript — prerequisite violations for students with transcripts
- Prereq-No Transcript — prerequisite warnings for freshmen/transfers
- Grade Eligibility — students requesting courses outside their grade level

Each tab includes an ACTION column for review decisions.

- **Source:** Template 2 (requests), Template 7 (prereqs/grades), Template 8 (transcripts)
- **Generated by:** Engine Phase 0 (`schedule_engine_v3.py`)

---

## Generation Notes

- All reports read from `schedule_solution_v3.json` (engine output) unless noted otherwise
- Report generation scripts are in the session scratchpad directory
- `REPORT_FORMATS` dict in `schedule_engine_v3.py` stores the canonical column definitions
- Font: Arial for all reports (headers bold white on dark fill, data size 9-10)
- All reports use thin borders on all data cells
