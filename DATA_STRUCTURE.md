# Data Structure — Master Schedule Builder

## Parents

Three entities that stand on their own. They don't belong to anything else.

1. **Student**
2. **Teacher**
3. **Room**

## Shared Resources

Used by multiple parents. They don't own anything — parents get placed into them.

1. **Cohort** — a group of Students (e.g., LEO Cohort A)
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
| Student > LEO II | Y or N | null — treated as N |
| Student > Pathway | Y or N | null — treated as N |
| Student > Academic Support | Y or N | null — treated as N |
| Student > Honors Track | Y or N | null — treated as N |
| Student > AP Track | Y or N | null — treated as N |
| Student > Has IEP | Y or N | null — treated as N |
| Student > IEP Max Class Size | number (e.g., 15) | null — no class size restriction |
| Student > IEP Required Periods | period letters (e.g., A, B) | null — no period restriction |
| Student > SSP (Student Special Priority) | calculated: LEO=5, Pathway=4, Academic Support=3, Standard=1 | not allowed — always calculated from population flags |
| Student > Course Request > Course Code | course code (e.g., 745) | not applicable — every request has a code |

**Cohort** is a shared resource. A student's cohort assignment is an input field in the Student file — NOT a separate file. The principal decides before the build which students belong to which cohort.

**Special population flags** (LEO II, Pathway, Academic Support, Honors Track, AP Track, IEP) are input fields in the Student file. They determine the student's SSP score and affect scheduling priority.

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
