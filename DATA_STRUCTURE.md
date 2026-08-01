# Data Structure — Master Schedule Builder

**Rule: All commercial product work happens ONLY after the Don Bosco Prep engine build is completed.** Everything in this document is for Don Bosco Prep unless explicitly labeled otherwise.

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

### Student — Don Bosco Prep

**Universal rule: Higher grade level = higher priority. No exceptions.** Grade 12 is highest, Grade 9 is lowest. A senior in their last year cannot miss a course — a freshman has three more chances.

The engine processes each student's data in this order:

| # | Step | Field | What the engine does |
|---|------|-------|---------------------|
| 1 | Identify | Student > ID Number | Unique student identifier |
| 2 | Identify | Student > Grade Level (9, 10, 11, 12) | What year the student is in |
| 3 | Validate | Student > NCAA (Y/N) | If Y, verify each course request is NCAA approved |
| 4 | Assign Point Value | Student > Grade Level Priority Value | Points assigned based on grade level |
| 5 | History | Student > Historical Courses Completed | What course requests the student already had scheduled |
| 6 | History | Student > Historical Cohort Membership | Was the student in a cohort in prior years |
| 7 | History | Student > Historical SSP Membership | Was the student in an SSP in prior years |
| 8 | Validate | Student > Current Year Course Requests | Cross-File Validation against 5, 6, 7 — confirm cohort, confirm SSP, flag duplicate courses |
| 9 | Grades | Student > Historical Failed Course + Teacher | Avoid placing student with the same teacher |
| 10 | Grades | Student > Historical Prerequisite Courses (all required) + Final Grades | Verify student passed all required prerequisites |
| 11 | Grades | Student > Historical Prerequisite Courses (all required) + Final Exam Grades | Verify prerequisite exam grades (null = ignore) |
| 12 | Confirm | Student > LEO II (Y/N) | Cross-File Validation confirms cohort membership — this IS the cohort |
| 13 | Assign Point Value | Student > Cohort Priority Value | Points assigned if LEO II = Y |
| 14 | Confirm | Student > LEO I (Y/N) | Cross-File Validation confirms SSP membership |
| 15 | Confirm | Student > Academic Support (Y/N) | Cross-File Validation confirms SSP membership |
| 16 | Confirm | Student > Pathway (Y/N) | Cross-File Validation confirms SSP membership |
| 17 | Assign Point Value | Student > SSP Priority Value | Points assigned based on SSP programs — stacks with Cohort unless LEO I → LEO II (same program, no stacking) |
| 18 | Assign Point Value | Student > Course Request > Course Code + Course Priority Value | Per-course priority (repeats for each course request) — same course, multiple categories = highest value only |
| 19 | Calculate | Student > Total Priority Score | Grade Level + Cohort (if any) + SSP (if any) + Course Priority Values |

**Cohort vs. SSP — these are NOT the same thing:**

- **Cohort** = a hard scheduling constraint. A student in a cohort MUST stay with a specific group of students — same course, same teacher, same term, same period. Don Bosco Prep has one cohort: LEO II. The engine has less flexibility, so the cohort priority value is HIGHER.
- **SSP (Special Student Population)** = the student belongs to one or more special programs (e.g., Pathway, Academic Support). SSP affects priority but does NOT restrict the student to stay with a group. The engine has more flexibility, so the SSP priority value is LOWER than cohort.
- **A student can belong to BOTH a cohort and one or more SSP programs.** When this happens, both priority values are used in the student's total priority score — they stack.

**Total Priority Score formula:**

> Student Total Priority = Grade Level Priority Value + Cohort Priority Value (if any) + SSP Priority Value (if any) + Course Priority Values

**Course-level priority categories** (e.g., AP, Singleton) add point values to the student's total. But when a single course qualifies for more than one category, the student receives only the HIGHER point value from that course — not both. This prevents double-counting from the same course.

**Example — Grade 12 student in LEO II, Academic Support, AP Art, and a Singleton elective:**

| Source | Category | Points |
|--------|----------|--------|
| Grade Level | 12 | (grade value) |
| LEO II | Cohort | (cohort value) |
| Academic Support | SSP | (SSP value) |
| AP Art | AP course | (AP value) |
| Singleton elective | Singleton | (singleton value) |
| **Total** | | **all five added together** |

**But if AP Art is also a Singleton:**

| Source | Category | Points |
|--------|----------|--------|
| Grade Level | 12 | (grade value) |
| LEO II | Cohort | (cohort value) |
| Academic Support | SSP | (SSP value) |
| AP Art | AP + Singleton → use HIGHER value only | (higher of AP or singleton value) |
| **Total** | | **no double-count from AP Art** |

**Rule: Different sources stack. Same course, multiple categories → highest value only.**

**LEO I vs. LEO II — these are NOT the same thing:**

- **LEO I** = SSP. The engine has flexibility to assign LEO I students into groups. No hard constraint during the LEO I year. LEO I automatically assigns the student to SSP as a member of Business Pathway.
- **LEO II** = Cohort. The groups the engine created during LEO I are now locked. Those same students must stay together — same course, same teacher, same term, same period. LEO I SSP membership does NOT carry over to LEO II — it is replaced by Cohort. The engine must not add LEO I SSP + LEO II Cohort together because that is the same program across two years and would overinflate the score. However, if the student also belongs to a separate SSP (e.g., Academic Support), that separate SSP DOES stack with the Cohort. Example: a LEO II student in Academic Support gets Grade Level + Cohort (LEO II) + SSP (Academic Support).
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

---

## Two-Level Priority System

The engine uses two separate priority calculations to build the master schedule. This is what makes this system different — priority values drive the entire build.

### Level 1 — Course Section Priority Value (which sections get placed first)

The engine ranks every course section by how restricted it is. The most restricted sections get placed into the master schedule first — because they have the fewest valid time slots and waiting too long means no slot remains.

**Formula:**

> Course Section Priority Value = (Locks × Weight) + Average Student Priority Value

- **Locks** = the total number of restrictions on the section from the Course file, Teacher file, and Room file. Each lock is multiplied by a weight to ensure locks always outrank student priority.
- **Average Student Priority Value** = the average priority of ALL students who requested this course. This ensures a section with fewer but higher-priority students is not bumped by a section with more but lower-priority students.

### What counts as a lock

Locks come from three files — Course, Teacher, and Room:

**From the Course file:**

| Lock | When it counts |
|------|---------------|
| Semester only (S1 or S2) | Course is not FY — restricted to half the schedule |
| Singleton | Only one section exists — zero flexibility |
| AP | Student chose AP over non-AP — contingent upon prerequisites being met |
| Graduation Requirement | Required course — must be placed |
| Cohort course | Must keep cohort students together |
| Co-Schedule Group | Must share a period with other courses |
| Prescribed Term | Course locked to a specific term |

**From the Teacher file (prescribed teacher's restrictions):**

| Lock | When it counts |
|------|---------------|
| Prescribed Teacher | Course has a specific teacher assigned |
| Teacher prescribed to a Period | That teacher is locked to a specific period |
| Teacher prescribed to a Term | That teacher is locked to a specific term |
| Teacher prescribed to a Room | That teacher is locked to a specific room |

**From the Room file (prescribed room's restrictions):**

| Lock | When it counts |
|------|---------------|
| Prescribed Room | Course has a specific room assigned |
| Unavailable Rooms | Rooms excluded for this course — reduces options |

### Why locks are weighted

If each lock and each student priority point counted equally (1 point each), a section with no locks but high-priority students could jump ahead of a heavily locked section. The locked section has fewer placement options and MUST go first — student priority cannot override that.

Weighting locks higher (e.g., each lock = 10 points, student priority max = 8) ensures:
- Locks always determine the primary order
- Student priority only makes a difference between sections with similar lock counts
- A section with more locks ALWAYS goes before a section with fewer locks, regardless of who requested it

### Level 2 — Student Priority Value (which students fill each section first)

Once a section is placed on the schedule, the engine fills it with students. Students are added in order of their Student Priority Value — highest first — until the section hits the enrollment cap. Students who don't make the cut are flagged and saved to a report for the principal to review.

**Formula:**

> Student Priority Value = Grade Level Priority Value + Cohort Priority Value (if any) + SSP Priority Value (if any)

**Components:**

| Component | What it measures |
|-----------|-----------------|
| Grade Level Priority Value | Higher grade = higher priority (12 highest, 9 lowest) — universal rule, no exceptions |
| Cohort Priority Value | Student is in a cohort (LEO II) — hard scheduling constraint, higher value |
| SSP Priority Value | Student is in an SSP (Academic Support, Pathway, etc.) — priority boost, lower value than cohort |

**Stacking rules:**
- Different sources stack: Grade Level + Cohort + SSP all add together
- Same program across years does NOT stack: LEO I SSP is replaced by LEO II Cohort, not added on top
- A student can belong to BOTH a cohort and a separate SSP: LEO II (Cohort) + Academic Support (SSP) = both values added

### Engine Build Order

1. Calculate Course Section Priority Value for every section (locks from Course + Teacher + Room files, weighted, plus average student priority)
2. Rank all sections from highest to lowest Course Section Priority Value
3. Place the highest-ranked section first — prescribed room, prescribed teacher, prescribed term
4. Fill the section with students — highest Student Priority Value first, until the cap is reached
5. Flag students who didn't make the cut — save to a report for the principal
6. Move to the next highest-ranked section
7. Repeat until all sections are placed

### Weighted Priority Tests

All tests use: each lock = 10 points, student priority range = 1-8.

| Test | Section A | Section B | Result |
|------|-----------|-----------|--------|
| Heavy locks vs. no locks | 5 locks (50) + avg 6 = **56** | 0 locks (0) + avg 1 = **1** | A first — correct |
| Same locks, different students | 3 locks (30) + avg 4 = **34** | 3 locks (30) + avg 1 = **31** | A first — higher-priority students break tie |
| High locks + low students vs. no locks + high students | 5 locks (50) + avg 1 = **51** | 0 locks (0) + avg 6 = **6** | A first — locks can't be overridden |
| Low locks + 1 high student vs. high locks + many students | 2 locks (20) + avg 7 = **27** | 5 locks (50) + avg 2 = **52** | B first — more locks wins |
| Few high-priority students vs. many low-priority students | 4 locks (40) + avg 6 = **46** | 4 locks (40) + avg 1 = **41** | A first — 2 students not bumped by 20 |
| Grade 12 AP S2 Singleton vs. no-lock FY course | 5 locks (50) + avg 4 = **54** | 0 locks (0) + avg 1 = **1** | A first — never bumped |
| Same locks, close call | 3 locks (30) + avg 7 = **37** | 3 locks (30) + avg 3 = **33** | A first — student priority breaks tie |

All 7 tests pass. Locks always determine the primary order. Student priority breaks ties between equally locked sections. No section with more locks is ever bumped by student priority alone.

### Actual point values

Point values for grade level, cohort, SSP, and lock weight will be selected after all data containers are fully defined — this ensures the student with the most restrictions always calculates highest and the most restricted course section is always placed first.
