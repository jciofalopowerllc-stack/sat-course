# Data Structure — Master Schedule Builder

## Parents

Three entities that stand on their own. They don't belong to anything else.

1. **Student**
2. **Teacher**
3. **Room**

## Shared Resources

Used by multiple parents. They don't own anything — parents get placed into them.

1. **Cohort** — a group of Students who must be assigned to a specific course code with the same teacher, during the same term and same period (e.g., LEO Cohort A). A cohort is a scheduling constraint, not just a label — the engine must keep all cohort members together in the same section.
2. **Term** — a time block: FY, S1, S2
3. **Period** — a time slot in the bell schedule: A, B, C, D, E, F, G

## Course Code

A shared link that connects Students, Teachers, and Rooms. A course code is not a parent — it is something that gets attached to all three parents.

## Section

The meeting point where a Student, Teacher, and Room come together at a specific Period + Term. A course code can have more than one section.

## Data Rules

- **Prescribed** = input. The principal decided before the build. The engine must respect it.
- **Assigned** = output. The engine decided during the build.
- **Null** = no data applies. The field intentionally has no value. The engine must select the least restrictive option.
- **Blank** = error. The user missed a field.

---

## Required Input Files

8 input files. No more, no less.

### Parent Files (one per parent)

| # | File | What it holds |
|---|------|--------------|
| 1 | **Student** | ID, grade level, course requests, cohort assignment, LEO/Pathway flags |
| 2 | **Teacher** | ID, department, prescribed courses, prescribed room, prescribed period, prescribed term, SSP, availability |
| 3 | **Room** | Room ID (S-234), capacity, type, available periods, prescribed courses, unavailable rooms |

### Shared Resource File

| # | File | What it holds |
|---|------|--------------|
| 4 | **Course** | Course code, title, department, credits, prerequisites, number of sections, prescribed term (FY/S1/S2) |

Term designation is a property of the course code — NOT a separate file. Cohort assignment is a field in the Student file — NOT a separate file.

### Constraint File

| # | File | What it holds |
|---|------|--------------|
| 5 | **Co-Schedule Groups** | Courses that must share the same period (links multiple course codes together) |

This requires its own file because it is a many-to-many relationship between course codes that cannot be stored as a single field in the Course file.

### Historical Files (for pre-build validation)

| # | File | What it holds |
|---|------|--------------|
| 6 | **Historical Grades** | Student ID, school year, course code, section, final grade, pass/fail |
| 7 | **Prior Year Master Schedule** | School year, course code, section, teacher ID, room |

### School Configuration

| # | File | What it holds |
|---|------|--------------|
| 8 | **School Settings** | Credit cap (35), periods (A-G), graduation requirements by grade level |

This is the rulebook — not a parent, not a shared resource, not a historical file. It defines the constraints the engine must enforce for the entire school.

---

## Parent Data Inputs

### Student

| Field | Values | Null Meaning |
|-------|--------|-------------|
| Student > ID Number | unique ID (e.g., 106245) | not allowed — every student has an ID |
| Student > Grade Level | 9, 10, 11, 12 | not allowed — every student has a grade |
| Student > Grade Level Priority Score | calculated from grade level | not allowed |
| Student > Cohort Name | cohort name (e.g., LEO Cohort A) | null — student not assigned to a cohort |
| Student > Cohort Locked | Y or N | null — treated as N (not locked) |
| Student > Cohort Priority Value | number (assigned based on cohort membership) | null — no cohort, no cohort priority |
| Student > SSP Programs | list of programs (e.g., Pathway, Academic Support) | null — student is not in any special program |
| Student > SSP Priority Value | number (assigned based on SSP membership) | null — no SSP, no SSP priority |
| Student > Has IEP | Y or N | null — treated as N |
| Student > IEP Max Class Size | number (e.g., 15) | null — no class size restriction |
| Student > IEP Required Periods | period letters (e.g., A, B) | null — no period restriction |
| Student > Course Request > Course Code | course code (e.g., 745) | not applicable — every request has a code |
| Student > Total Priority Score | calculated (see formula below) | not allowed — always calculated |

**Cohort vs. SSP — these are NOT the same thing:**

- **Cohort** = a hard scheduling constraint. A student in a cohort MUST stay with a specific group of students — same course, same teacher, same term, same period. Example: LEO II is a cohort. The engine has less flexibility, so the cohort priority value is HIGHER.
- **SSP (Special Student Population)** = the student belongs to one or more special programs (e.g., Engineering Pathway, Academic Support). SSP affects priority but does NOT restrict the student to stay with a group. The engine has more flexibility, so the SSP priority value is LOWER than cohort.
- **A student can belong to BOTH a cohort and one or more SSP programs.** When this happens, both priority values are used in the student's total priority score — they stack.

**Total Priority Score formula:**

> Student Total Priority = Grade Level Priority + Cohort Priority (if any) + SSP Priority (if any)

**Cohort** is a shared resource. A student's cohort assignment is an input field in the Student file — NOT a separate file. The principal decides before the build which students belong to which cohort.

**SSP programs** (LEO I, Pathway, Academic Support, etc.) are input fields in the Student file. A student can belong to more than one SSP program. LEO II is NOT an SSP — it is a cohort.

**LEO I vs. LEO II — these are NOT the same thing:**

- **LEO I** = SSP. The engine has flexibility to assign LEO I students into groups. No hard constraint during the LEO I year.
- **LEO II** = Cohort. The groups the engine created during LEO I are now locked. Those same students must stay together — same course, same teacher, same term, same period.
- LEO is a two-year pipeline: the engine's LEO I group assignments (output from year 1) become the prescribed cohort input for LEO II (year 2).

### Teacher

(to be defined)

### Room

Room ID is the room number (e.g., S-234). This is both the identifier and the name. No separate RM_ prefix ID — one clean code.

| Field | Values | Null Meaning |
|-------|--------|-------------|
| Room > Room ID | room number (e.g., S-234) | not allowed — every room has an ID |
| Room > Prescribed Room > Course Code | course code | null — room not locked to a course |
| Room > Unavailable Rooms > Course Code | list of room numbers | null — no rooms excluded |

**Don Bosco Prep vs. Commercial Product:**

- **Don Bosco Prep (now):** The principal prescribes which room a course uses, or provides a list of rooms that CANNOT be used. The engine works with what's left. No department matching needed.
- **Commercial Product (future):** Room > Department field will be added so the engine can automatically match rooms to courses and teachers by department. A new school won't have to prescribe every room manually.

---

## Shared Resource Data Inputs

### Course

| Field | Values | Null Meaning |
|-------|--------|-------------|
| Course > Course Code | unique code (e.g., 745) | not allowed — every course has a code |
| Course > Course Title | text (e.g., Catholic Social Teaching) | not allowed — every course has a title |
| Course > Department | department name (e.g., THEO, ENG, MATH) | not allowed — every course belongs to a department |
| Course > Credits | number (e.g., 5) | not allowed — every course has a credit value |
| Course > Grade Levels | list (e.g., 9, 10, 11, 12) | not allowed — every course has eligible grade levels |
| Course > Sections Needed | number (e.g., 8) | not allowed — every course needs at least 1 section |
| Course > Max Enrollment per Section | number (e.g., 25) | not allowed — every section has a cap |
| Course > Prescribed Term | FY, S1, S2 | null — engine selects least restrictive |
| Course > Prerequisites | course codes (e.g., 110) | null — no prerequisites |
| Course > Corequisites | course codes (e.g., 301) | null — no corequisites |
| Course > Graduation Requirement | subject area (e.g., English, Theology, Math, Science, History) | null — course is an elective |
| Course > Singleton | Y or N | not allowed — engine must know if only one section exists |
| Course > Cohort | cohort name (e.g., LEO Cohort A) | null — course is not a cohort course |

**Graduation Requirement vs. Elective:** If a course counts toward a grade level's graduation requirement, the `Graduation Requirement` field names the subject area it satisfies (e.g., "English" or "Theology"). If the field is null, the course is an elective. The engine uses this field combined with the School Settings file (graduation requirements by grade level) to verify that every student's course requests include all required subject areas for their grade.

---

## Pre-Build Validation Sources

### Student Course Request Checks

The engine needs to validate course requests before the build runs. This requires data from multiple sources:

| Check | Sources Needed |
|-------|---------------|
| Total credits within cap (35) | Student > Course Request > Course Code + Course Code > Credits |
| Duplicate requests in current year | Student > Course Request > Course Code (check for repeats within same student) |
| Already completed in previous year | Student > Course Request > Course Code + Historical Grades (same course code with Pass) |
| Prerequisites met | Student > Course Request > Course Code + Course Code > Prerequisite > Course Code + Historical Grades |
| Avoid failed-course teacher | Historical Grades (failed course + section) + Prior Year Master Schedule (section + teacher) |

### Historical Grades File

| Field | Purpose |
|-------|---------|
| Student ID | match to Student > ID Number |
| School Year | which year (23-24, 24-25, 25-26) |
| Course Code | clean, standalone column — NOT embedded in a combined string |
| Section | needed to cross-reference teacher from prior year master schedule |
| Final Grade | the grade earned |
| Pass/Fail | clear yes/no — did the student complete this course |

### Prior Year Master Schedule

| Field | Purpose |
|-------|---------|
| School Year | which year |
| Course Code | match to historical grades |
| Section | match to historical grades — this is the link between the two files |
| Teacher ID | who taught this section |
| Room | where this section met |

The engine cross-references these two files using Course Code + Section to connect a student's grade to the teacher and room from that year.

---

## Course Code Relationships

The same course code can appear under multiple parents:

| Relationship | Meaning |
|-------------|---------|
| Student > Course Code | this student is requesting this course |
| Teacher > Course Code | this teacher is prescribed to teach this course |
| Room > Course Code | this room is prescribed for this course |

---

## Section Structure

A section is built under a course code. The engine attaches parents and shared resources to it.

```
Course Code > Section > Student    (engine assigns)
Course Code > Section > Teacher    (prescribed or engine assigns)
Course Code > Section > Room       (prescribed or engine assigns)
Course Code > Section > Period     (prescribed or engine assigns)
Course Code > Section > Term       (prescribed or engine assigns)
Course Code > Section > Cohort     (prescribed or null)
```

A section occupies a **time slot** = Period + Term pair.

Example — Course 849 (Catholic Social Teaching), 8 sections:

```
849 > Section 1 > Teacher = New THEO 2 Teacher
849 > Section 1 > Room    = (engine assigns)
849 > Section 1 > Period  = (engine assigns)
849 > Section 1 > Term    = S1
849 > Section 1 > Students = (engine assigns)

849 > Section 5 > Teacher = New THEO 2 Teacher
849 > Section 5 > Room    = (engine assigns)
849 > Section 5 > Period  = (engine assigns)
849 > Section 5 > Term    = S2
849 > Section 5 > Students = (engine assigns)
```

---

## Prescribed Relationships

Any parent can be prescribed to any shared resource or course code. If not prescribed, the value is null and the engine decides.

### Student Prescriptions

| Relationship | Values | Null |
|-------------|--------|------|
| Student > Course Code | course code (e.g., 745) | not applicable — requests always have a code |

### Teacher Prescriptions

| Relationship | Values | Null |
|-------------|--------|------|
| Teacher > Prescribed Course > Course Code | course code (e.g., 745) | engine selects least restrictive |
| Teacher > Prescribed Room > Teacher ID | room number (e.g., S-234) | engine selects least restrictive |
| Teacher > Prescribed Term > Teacher ID | FY, S1, S2 | engine selects least restrictive |
| Teacher > Prescribed Period > Teacher ID | A, B, C, D, E, F, G | engine selects least restrictive |
| Teacher > Prescribed Cohort > Teacher ID | cohort name (e.g., LEO Cohort A) | engine selects least restrictive |

### Room Prescriptions

| Relationship | Values | Null |
|-------------|--------|------|
| Room > Prescribed Course > Course Code | course code (e.g., 745) | engine selects least restrictive |

### Course Code Prescriptions

| Relationship | Values | Null |
|-------------|--------|------|
| Course Code > Prescribed Teacher | teacher ID/name | engine selects least restrictive |
| Course Code > Prescribed Room | room number | engine selects least restrictive |
| Course Code > Prescribed Term | FY, S1, S2 | engine selects least restrictive |
| Course Code > Prescribed Period | A, B, C, D, E, F, G | engine selects least restrictive |

---

## Cross-File Validation

The engine reads all 8 input files before the build. When data in one file can confirm or contradict data in another file, the engine connects the dots automatically. If everything matches, the engine fills in the value. If something doesn't match, the engine flags it for the principal to review.

**Rule:** The engine never guesses. It either proves a match across files or asks a human.

### How It Works

1. **Default** — Every field that can be auto-filled starts as null (no value).
2. **Cross-reference** — The engine checks multiple files for indicators that point to the same answer.
3. **All match** — The engine fills in the value automatically.
4. **Mismatch** — The engine flags the conflict for the principal to review and decide.
5. **Principal decides** — The engine waits for the human to verify before proceeding.

### Example: Student Cohort Membership

The engine uses the Course file's `Cohort` field as the master list of which course codes belong to which cohort. It does NOT need a cohort column in the historical files — the course code is the link.

| Step | What the engine does |
|------|---------------------|
| 1. Default | Student > Cohort Name starts as null (no cohort) |
| 2. Check Historical Grades | Look up the student's prior course codes → check each one in the Course file → did any belong to a cohort? |
| 3. Check Prior Year Master Schedule | Look up the student's prior sections → check those course codes in the Course file → did any belong to a cohort? |
| 4. Check Current Year Course Requests | Look up the student's requested course codes → check each one in the Course file → do any belong to a cohort? |
| 5a. All three match | Engine fills in Student > Cohort Name automatically (e.g., "LEO Cohort A") |
| 5b. Mismatch | Engine flags: "Student 106245 — cohort indicators found in 2 of 3 sources. Historical grades show LEO courses, current requests show LEO courses, but prior year schedule does not. Please verify." |
| 6. Principal reviews | Principal confirms or corrects. Engine proceeds. |

### Why This Works Without Changing the Historical Files

The **Course file** is the single source of truth for which course codes belong to a cohort. The engine looks up any course code — current or historical — in the Course file to check for a cohort indicator. No new columns needed in the Historical Grades or Prior Year Master Schedule files.

### Future Cross-File Validation Checks

The cohort example is the first. The same pattern applies anywhere data in one file can confirm or contradict data in another. Additional checks will be defined as we build out the remaining data containers.
