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
| 2 | **Teacher** | ID, department, prescribed courses, prescribed room, prescribed period, prescribed term, Special Student Population, availability |
| 3 | **Room** | Room ID (e.g., J-322), capacity, available periods, available terms, shared room (co-schedule approved) |

### Shared Resource File

| # | File | What it holds |
|---|------|--------------|
| 4 | **Course** | Course code, title, department, credits, prerequisites, number of sections, prescribed term (FY/S1/S2) |

Term designation is a property of the course code — NOT a separate file. Cohort assignment is a field in the Student file — NOT a separate file.

### Constraint File

| # | File | What it holds |
|---|------|--------------|
| 5 | **Co-Schedule Groups** | Low-enrollment course sections grouped by the principal to share the same teacher, same room, and same period. Protects students from losing courses and teachers from losing full-time status. |

This requires its own file because a co-schedule group can contain 2, 3, or 4 course codes linked to one teacher, which is a many-to-many relationship that cannot be stored as a single field in the Course file.

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

## Universal Rules

1. **Higher grade level = higher priority. No exceptions.** Grade 12 is highest, Grade 9 is lowest. A senior in their last year cannot miss a course — a freshman has three more chances.

2. **Teacher load cap = 5 periods per semester.** Counted by PERIODS, not courses. A full-year (FY) course uses 1 period in S1 AND 1 period in S2. A semester course uses 1 period in ONE semester only. The cap is calculated per semester — no more than 5 periods in S1 and no more than 5 periods in S2, using any combination of FY and semester courses. The cap cannot be exceeded unless the teacher is approved for a 6th period (full-year, S1 only, or S2 only).

3. **35.0 credits is the ABSOLUTE cap for students (Don Bosco).**

4. **Student names allowed for Don Bosco engine. Student names/emails/contacts NEVER enter the commercial product scheduling database (PII isolation). Teacher names allowed for both engines.**

---

## Parent Data Inputs

### Student — Don Bosco Prep

The engine processes each student's data in this order:

| # | Step | Field | What the engine does |
|---|------|-------|---------------------|
| 1 | Identify | Student > ID Number | Unique student identifier |
| 2 | Identify | Student > Grade Level (9, 10, 11, 12) | What year the student is in |
| 3 | Validate | Student > NCAA (Y/N) | If Y, verify each course request is NCAA approved |
| 4 | Assign Point Value | Student > Grade Level Priority Value | Points assigned based on grade level |
| 5 | History | Student > Historical Courses Completed | What course requests the student already had scheduled |
| 6 | History | Student > Historical Cohort Membership | Was the student in a cohort in prior years |
| 7 | History | Student > Historical Special Student Population Membership | Was the student in a Special Student Population in prior years |
| 8 | Validate | Student > Current Year Course Requests | Cross-File Validation against 5, 6, 7 — confirm cohort, confirm Special Student Population, flag duplicate courses |
| 9 | Grades | Student > Historical Failed Course + Teacher | Avoid placing student with the same teacher |
| 10 | Grades | Student > Historical Prerequisite Courses (all required) + Final Grades | Verify student passed all required prerequisites |
| 11 | Grades | Student > Historical Prerequisite Courses (all required) + Final Exam Grades | Verify prerequisite exam grades (null = ignore) |
| 12 | Confirm | Student > LEO II (Y/N) | Cross-File Validation confirms cohort membership — this IS the cohort |
| 13 | Assign Point Value | Student > Cohort Priority Value | Points assigned if LEO II = Y |
| 14 | Confirm | Student > LEO I (Y/N) | Cross-File Validation confirms Special Student Population membership |
| 15 | Confirm | Student > Academic Support (Y/N) | Cross-File Validation confirms Special Student Population membership |
| 16 | Confirm | Student > Pathway (Y/N) | Cross-File Validation confirms Special Student Population membership |
| 17 | Assign Point Value | Student > Special Student Population Priority Value | Points assigned based on Special Student Population programs — stacks with Cohort unless LEO I → LEO II (same program, no stacking) |
| 18 | **Calculate** | **Student > Raw Priority Value** | **Grade Level + Cohort (if any) + Special Student Population (if any) — who the student IS. FIXED for the school year. No course, teacher, or room data. Saved to student's profile by school year.** |
| 19 | Assign Point Value | Student > Course Request > Course Code + Course Priority Value | Per-course priority (repeats for each course request) — includes the course's own restrictions (AP, Singleton, etc.) PLUS the prescribed teacher's restrictions PLUS the prescribed room's restrictions. Same course, multiple categories = highest value only |
| 20 | **Calculate** | **Student > Total Priority Value** | **Raw Priority Value (step 18) + Course Priority Values (step 19). Changes every run as courses are placed and removed from the student's request list. Saved to student's profile with run number and school year.** |

**Cohort vs. Special Student Population — these are NOT the same thing:**

- **Cohort** = a hard scheduling constraint. A student in a cohort MUST stay with a specific group of students — same course, same teacher, same term, same period. Don Bosco Prep has one cohort: LEO II. The engine has less flexibility, so the cohort priority value is HIGHER.
- **Special Student Population** = the student belongs to one or more special programs (e.g., Pathway, Academic Support). Special Student Population affects priority but does NOT restrict the student to stay with a group. The engine has more flexibility, so the Special Student Population priority value is LOWER than cohort.
- **A student can belong to BOTH a cohort and one or more Special Student Population programs.** When this happens, both priority values are used in the student's total priority score — they stack.

**Student Raw Priority Value formula (FIXED for the school year):**

> Student Raw Priority Value = Grade Level Priority Value + Cohort Priority Value (if any) + Special Student Population Priority Value (if any)

This is who the student IS — no course, teacher, or room data. Calculated once and saved to the student's profile by school year.

**Student Total Priority Value formula (CHANGES every run):**

> Student Total Priority Value = Raw Priority Value + Course Priority Values

Course Priority Values include the course's own restrictions (AP, Singleton, etc.) PLUS the prescribed teacher's restrictions PLUS the prescribed room's restrictions. After each run, placed courses are removed and the Total recalculates. Saved to the student's profile with run number and school year.

**Course-level priority categories** (e.g., AP, Singleton) add point values to the student's total. But when a single course qualifies for more than one category, the student receives only the HIGHER point value from that course — not both. This prevents double-counting from the same course.

**Example — Grade 12 student in LEO II, Academic Support, AP Art, and a Singleton elective:**

| Source | Category | Points |
|--------|----------|--------|
| Grade Level | 12 | (grade value) |
| LEO II | Cohort | (cohort value) |
| Academic Support | Special Student Population | (Special Student Population value) |
| AP Art | AP course | (AP value) |
| Singleton elective | Singleton | (singleton value) |
| **Total** | | **all five added together** |

**But if AP Art is also a Singleton:**

| Source | Category | Points |
|--------|----------|--------|
| Grade Level | 12 | (grade value) |
| LEO II | Cohort | (cohort value) |
| Academic Support | Special Student Population | (Special Student Population value) |
| AP Art | AP + Singleton → use HIGHER value only | (higher of AP or singleton value) |
| **Total** | | **no double-count from AP Art** |

**Rule: Different sources stack. Same course, multiple categories → highest value only.**

**LEO I vs. LEO II — these are NOT the same thing:**

- **LEO I** = Special Student Population. The engine has flexibility to assign LEO I students into groups. No hard constraint during the LEO I year. LEO I automatically assigns the student to Special Student Population as a member of Business Pathway.
- **LEO II** = Cohort. The groups the engine created during LEO I are now locked. Those same students must stay together — same course, same teacher, same term, same period. LEO I Special Student Population membership does NOT carry over to LEO II — it is replaced by Cohort. The engine must not add LEO I Special Student Population + LEO II Cohort together because that is the same program across two years and would overinflate the score. However, if the student also belongs to a separate Special Student Population (e.g., Academic Support), that separate Special Student Population DOES stack with the Cohort. Example: a LEO II student in Academic Support gets Grade Level + Cohort (LEO II) + Special Student Population (Academic Support).
- LEO is a two-year pipeline: the engine's LEO I group assignments (output from year 1) become the prescribed cohort input for LEO II (year 2).

**Student Template — Don Bosco Prep**

The student data is split across two sheets in the same file. Sheet 1 holds student-level data (one row per student). Sheet 2 holds transcript history (one row per course per year).

**Sheet 1: Student Profiles (one row per student)**

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Student ID | REQUIRED | Unique student identifier |
| B | Last Name | REQUIRED | Student's last name |
| C | First Name | REQUIRED | Student's first name |
| D | Grade Level | REQUIRED | 9, 10, 11, 12 |
| E | NCAA | REQUIRED | Y/N — is this student NCAA tracked |
| F | LEO II | REQUIRED | Y/N — cohort membership |
| G | LEO I | REQUIRED | Y/N — Special Student Population membership |
| H | Academic Support | REQUIRED | Y/N — Special Student Population membership |
| I | Pathway | REQUIRED | Y/N — Special Student Population membership |
| J | Cohort Name | OPTIONAL | Cohort name (e.g., LEO II Cohort A) — null = not in a cohort |
| K | Cohort Locked | OPTIONAL | Y/N — confirms cross-file cohort result. If Y and data doesn't match, engine flags conflict for user to resolve. Null = not applicable |

11 columns total.

**Sheet 2: Transcript History (one row per course per year)**

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Student ID | REQUIRED | Must match Sheet 1 |
| B | Academic Year | REQUIRED | e.g., 2023-2024 |
| C | Course Code | REQUIRED | Must match Course file |
| D | Course Title | REQUIRED | Course name |
| E | Department | REQUIRED | Department name |
| F | Credits | REQUIRED | Credit value |
| G | Final Grade | OPTIONAL | Numeric grade — null = incomplete |
| H | Passed (Y/N) | OPTIONAL | null = incomplete |
| I | Grade Level When Taken | REQUIRED | What grade the student was in |
| J | Notes | OPTIONAL | null = none |

10 columns total.

**Columns removed from the original Template 8 (not needed by Don Bosco engine):**

The original Template 8 had 21 columns on Sheet 1. The following 11 columns were removed:

- Credits Earned — engine calculates from transcript
- Credits Required — comes from School Settings file
- GPA Band — engine doesn't use GPA for priority
- Priority Level (P0-P5) — OLD priority system, engine now calculates automatically
- SSP (Student Special Priority) — OLD system value, replaced by Special Student Population Priority Value
- Has IEP — saved for commercial product
- IEP Max Class Size — saved for commercial product
- IEP Required Periods — saved for commercial product
- Honors Track — engine doesn't use "track" for priority
- AP Track — engine doesn't use "track" for priority
- Requests Total, Requests Fulfilled, Placement Rate, Conflicts Active — engine calculates at runtime, not input data

**Columns added (4 total):**

- Last Name — student names allowed for Don Bosco engine
- First Name — student names allowed for Don Bosco engine
- NCAA (Y/N) — engine Step 3 needs this to validate course requests
- LEO I (Y/N) — engine Step 14 needs this for Special Student Population confirmation

**Commercial product note:** IEP columns (Has IEP, IEP Max Class Size, IEP Required Periods) and runtime output columns (Requests Total, Requests Fulfilled, Placement Rate, Conflicts Active) may be needed for the commercial engine. Student names will NOT be included in the commercial product (PII isolation). Specifications will be defined after the Don Bosco Prep engine build is completed.

### Teacher — Don Bosco Prep

The teacher data is split across two sheets in the same file. Sheet 1 holds teacher-level data (one row per teacher). Sheet 2 holds course-level prescriptions (one row per teacher-course combination).

**Sheet 1: Teacher Profiles (one row per teacher)**

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Teacher ID | REQUIRED | Unique ID (e.g., 105826) |
| B | Last Name | REQUIRED | Teacher last name |
| C | First Name | REQUIRED | Teacher first name |
| D | Department | REQUIRED | Department name (e.g., MATH, ENG, THEO) |
| E | Max Teaching Periods | REQUIRED | Default 5 — the per-semester cap |
| F | Approved 6th Period FY | REQUIRED | Y/N — approved for 6 periods both semesters |
| G | Approved 6th Period S1 Only | REQUIRED | Y/N — approved for 6 periods in S1 only |
| H | Approved 6th Period S2 Only | REQUIRED | Y/N — approved for 6 periods in S2 only |
| I | Avail Period A | REQUIRED | Y/N — available to teach in Period A |
| J | Avail Period B | REQUIRED | Y/N |
| K | Avail Period C | REQUIRED | Y/N |
| L | Avail Period D | REQUIRED | Y/N |
| M | Avail Period E | REQUIRED | Y/N |
| N | Avail Period F | REQUIRED | Y/N |
| O | Avail Period G | REQUIRED | Y/N |
| P | Special Student Population Teacher | OPTIONAL | Which Special Student Population programs this teacher is part of (e.g., Academic Support, Pathway) — null if none |
| Q | Approved for Co-Scheduled Sections | REQUIRED | Y/N — is this teacher approved to teach co-scheduled sections |

17 columns total.

**Sheet 2: Teacher-Course Assignments (one row per teacher-course combination)**

Each row connects one teacher to one course they teach, with prescriptions specific to that combination. A teacher with 5 courses has 5 rows. Null = engine decides.

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Teacher ID | REQUIRED | Must match a Teacher ID in Sheet 1 |
| B | Course Code | REQUIRED | Must match a Course Code in the Course file |
| C | Prescribed Room | OPTIONAL | Room number (e.g., S-234) — null = engine decides |
| D | Prescribed Period | OPTIONAL | A, B, C, D, E, F, G — null = engine decides |
| E | Prescribed Term | OPTIONAL | FY, S1, S2 — null = engine decides |
| F | Prescribed Cohort | OPTIONAL | Cohort name (e.g., LEO II Cohort A) — null = not a cohort course |

6 columns total.

**Why two sheets:** A teacher can teach multiple courses, and each course can have a different prescribed room, period, term, and cohort. One row per teacher with one room column cannot capture this. The assignment sheet connects each teacher-course combination to its own prescriptions.

**PII rule for teachers:** Teacher names (Last Name, First Name) are ALLOWED in the scheduling database for both Don Bosco Prep and the commercial product. PII isolation applies to student names only.

**Columns removed from the original Template 6 (not needed by Don Bosco engine):**

The original Template 6 had 48 columns. The following 32 columns were removed because the engine does not use them:

- Department 2 (secondary department)
- Employment Status
- Contract Type
- Hire Year
- Seniority Rank
- Max Consecutive Periods
- Requires 2 Consecutive Free
- Prep Periods Required
- Duty Periods
- Preferred Periods (soft preference — engine uses prescribed, not preferred)
- Avoid Periods (soft constraint — engine uses prescribed, not preferred)
- Preferred Room (replaced by Prescribed Room in Sheet 2)
- Preferred Wing
- Primary Subjects
- Secondary Subjects
- Master Teacher
- AP/Honors Teacher
- Certification Type, Subject, Expiry
- Course-Teacher Lock (replaced by Sheet 2)
- Sole Teacher for Courses
- Prior Year Periods Taught
- Prior Year Room
- All Reference/computed columns (Sections Assigned, Unique Courses, Full-Year Load, S1 Load, S2 Load, Singleton Courses, Computed MTP Score, Courses Assigned)

**Commercial product note:** Some of these removed columns may be needed for the commercial engine. Specifications for the commercial version of this template will be defined after the Don Bosco Prep engine build is completed.

**Teacher Processing Order:**

The engine processes each teacher's data in this order:

| # | Step | Field | What the engine does |
|---|------|-------|---------------------|
| 1 | Identify | Teacher > ID | Unique teacher identifier |
| 2 | Identify | Teacher > Department | What department the teacher belongs to |
| 3 | Validate | Teacher > Availability (Periods A-G) | Which periods the teacher is available — N = unavailable |
| 4 | Validate | Teacher > Max Teaching Periods | Per-semester cap (default 5) |
| 5 | Validate | Teacher > 6th Period Approval (FY/S1/S2) | Can the teacher exceed the 5-period cap? |
| 6 | Confirm | Teacher > Special Student Population Teacher | Is the teacher part of a Special Student Population program? |
| 7 | Load | Teacher > Course Assignments (Sheet 2) | Load all course assignments for this teacher |
| 8 | Count Locks | Teacher > Prescribed Room | Each course with a prescribed room = 1 lock |
| 9 | Count Locks | Teacher > Prescribed Period | Each course with a prescribed period = 1 lock |
| 10 | Count Locks | Teacher > Prescribed Term | Each course with a prescribed term = 1 lock |
| 11 | Count Locks | Teacher > Prescribed Cohort | Each course with a prescribed cohort = 1 lock |
| 12 | Count Locks | Teacher > Unavailable Periods | Each period where availability = N = 1 lock |
| 13 | Assign Point Value | Teacher > Total Lock Value | All locks from steps 8-12 × weight (10 points each) |
| 14 | **Calculate** | **Teacher > Raw Priority Value** | **Total Lock Value ONLY — no student or room data. FIXED for the school year. Saved to teacher's profile by school year.** |
| 15 | Identify | Teacher > All Students with Course Requests | From ALL students across ALL of this teacher's courses, build the full student list |
| 16 | Rank | Teacher > Student List by Priority Value | Rank all students from high to low |
| 17 | Assign Point Value | Teacher > Top Student Priority Value | The highest-scoring student's value |
| 18 | Load | Teacher > Prescribed Room Priority Value | Room Total Priority Value for the prescribed room (0 if none) |
| 19 | **Calculate** | **Teacher > Total Priority Value** | **Raw Priority Value (step 14) + Top Student Priority Value (step 17) + Prescribed Room Priority Value (step 18). Changes every run. Saved to teacher's profile with run number and school year.** |

After each section is placed, the engine returns to step 15 — rebuilds the student list with remaining students, re-ranks, gets new top student, and recalculates step 19. Step 14 (Raw) never changes.

### Room — Don Bosco Prep

Room ID is the room number (e.g., J-322). This is both the identifier and the name. No separate RM_ prefix ID — one clean code.

**Room Template — Don Bosco Prep (1 sheet)**

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Room ID | REQUIRED | Room number (e.g., J-322, Audit., Band) |
| B | Capacity | REQUIRED | Max seats in the room |
| C | Available Periods | REQUIRED | Which periods the room is available, comma-separated (e.g., A,B,C,D,E,F,G) |
| D | Available Terms | REQUIRED | Which terms the room is available (FY, S1, S2) — null = available all terms |
| E | Shared Room | REQUIRED | Y/N — is this room approved for co-scheduled sections |

5 columns total.

**Columns removed from the original Template 9 (not needed by Don Bosco engine):**

The original Template 9 had 16 columns. The following 12 columns were removed:

- Room Number — duplicate of Room ID (engine uses room number as the ID)
- Building — engine doesn't use for scheduling
- Wing — engine doesn't use for scheduling
- Floor — engine doesn't use for scheduling
- Room Type — engine doesn't use for Don Bosco (principal prescribes rooms)
- Has Projector — engine doesn't use equipment
- Has Smartboard — engine doesn't use equipment
- Has Lab Stations — engine doesn't use equipment
- Has Computers — engine doesn't use equipment
- ADA Accessible — engine doesn't use for scheduling
- Home Teacher — handled by Prescribed Room in Teacher-Course Assignments
- Adjacent Rooms — engine doesn't use room adjacency

**Columns added (1 total):**

- Available Terms — engine Step 3 needs this for lock calculation

**Commercial product note:** Building, Wing, Floor, Room Type, equipment columns, and ADA Accessible may be needed for the commercial engine. A Room > Department field will be added so the engine can automatically match rooms to courses and teachers by department. Specifications will be defined after the Don Bosco Prep engine build is completed.

**Room Processing Order:**

The engine processes each room's data in this order:

| # | Step | Field | What the engine does |
|---|------|-------|---------------------|
| 1 | Identify | Room > Room ID | Unique room identifier (e.g., S-234) |
| 2 | Validate | Room > Available Periods | Which periods the room is available — each unavailable period = 1 lock |
| 3 | Validate | Room > Available Terms | Which terms the room is available — each unavailable term = 1 lock |
| 4 | Count Locks | Room > Availability Locks | Total unavailable periods and terms × weight (10 points each) |
| 5 | Count | Room > Demand | Number of course sections prescribed to this room — more sections competing = more restricted |
| 6 | **Calculate** | **Room > Raw Priority Value** | **Availability Locks (step 4) + Demand (step 5). FIXED for the school year. No teacher or student data. Saved to room's profile by school year.** |
| 7 | Identify | Room > All Teachers Prescribed to Room | From ALL teachers with course assignments in this room, build the full teacher list |
| 8 | Rank | Room > Teacher List by Priority Value | Rank all teachers from high to low |
| 9 | Assign Point Value | Room > Top Teacher Priority Value | The highest-scoring teacher's value |
| 10 | Identify | Room > All Students with Course Requests | From ALL students who have a course request for any course prescribed to this room, build the full student list |
| 11 | Rank | Room > Student List by Priority Value | Rank all students from high to low |
| 12 | Assign Point Value | Room > Top Student Priority Value | The highest-scoring student's value |
| 13 | **Calculate** | **Room > Total Priority Value** | **Raw Priority Value (step 6) + Top Teacher Priority Value (step 9) + Top Student Priority Value (step 12). Changes every run. Saved to room's profile with run number and school year.** |

After each section is placed, the engine returns to step 7 — rebuilds the teacher and student lists with remaining data, re-ranks, gets new top teacher and top student, and recalculates step 13. Step 6 (Raw) never changes.

**Profile Storage Rule — applies to ALL three parents:**

| Data Saved | When | Changes? |
|-----------|------|----------|
| Raw Priority Value | Once, before Run #1 | NO — fixed for the school year |
| Total Priority Value (Run #1) | After Run #1 | YES — different each run |
| Total Priority Value (Run #2) | After Run #2 | YES |
| Total Priority Value (Run #N) | After each run | YES — until all sections placed |
| School Year | Stored with each record | Allows year-over-year comparison |

Every student, teacher, and room has a complete history: their raw score plus how their total score changed across every run, stored by school year. The principal can pull up any record and see exactly what happened and why.

---

## Shared Resource Data Inputs

### Course — Don Bosco Prep

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Course Code | REQUIRED | Unique code (e.g., 745) |
| B | Course Title | REQUIRED | Course name (e.g., AP Calculus AB) |
| C | Department | REQUIRED | Department name (e.g., MATH, ENG, THEO) |
| D | Credits | REQUIRED | Credit value (e.g., 5, 2.5) |
| E | Prescribed Term | REQUIRED | FY, S1, S2 |
| F | Grade Levels | REQUIRED | Eligible grades, comma-separated (e.g., 11, 12) |
| G | Sections Needed | REQUIRED | Number of sections (e.g., 8) |
| H | Max Enrollment per Section | REQUIRED | Seat cap (e.g., 25) |
| I | Singleton | REQUIRED | Y/N — only one section exists |
| J | AP | REQUIRED | Y/N — is this an AP course |
| K | Graduation Requirement | OPTIONAL | Subject area satisfied (e.g., English, Math, Science, History, Theology) — null = elective |
| L | Cohort | OPTIONAL | Cohort name (e.g., LEO II Cohort A) — null = not a cohort course |
| M | NCAA | OPTIONAL | Y/N — is this course NCAA approved — null = not applicable |
| N | Prerequisites | OPTIONAL | Course codes, comma-separated (e.g., 110, 421) — null = none |
| O | Corequisites | OPTIONAL | Course codes, comma-separated — null = none |

15 columns total.

**Graduation Requirement vs. Elective:** If a course counts toward a grade level's graduation requirement, the `Graduation Requirement` field names the subject area it satisfies (e.g., "English" or "Theology"). If the field is null, the course is an elective. The engine uses this field combined with the School Settings file (graduation requirements by grade level) to verify that every student's course requests include all required subject areas for their grade.

**Columns removed from the original Template 7 (not needed by Don Bosco engine):**

The original Template 7 had 28 columns. The following 17 columns were removed:

- Level (Regular/Honors/AP) — replaced by clear AP (Y/N) field
- Type (Full-Year/Semester) — duplicate of Prescribed Term
- Min Enrollment — engine doesn't use minimum enrollment
- Priority Level (0-5) — OLD priority system, engine now calculates automatically
- CFP (Course Flexibility) — OLD scoring, conflicts with new system
- CYRP (Current Year Required) — OLD scoring, conflicts with new system
- CTAP (Course-Teacher Affinity) — OLD scoring, conflicts with new system
- TL (Teacher Lock) — OLD scoring, locks now counted automatically from Teacher-Course Assignments
- PL (Period Lock) — OLD scoring, locks now counted automatically
- RL (Room Lock) — OLD scoring, locks now counted automatically
- Required Certification — engine doesn't use teacher certification
- Required Room Type — handled by Prescribed Room in Teacher-Course Assignments
- Required Equipment — engine doesn't use equipment
- Total Requests — engine calculates from Student file
- Demand Ratio — engine calculates
- Prior Year Sections — engine gets from Prior Year Master Schedule file
- Prior Year Avg Enrollment — engine calculates

**Columns added (not in original Template 7):**

- AP (Y/N) — engine needs a clear yes/no, old "Level" field mixed AP with Honors
- NCAA (Y/N) — engine needs to validate NCAA students' course requests

**Commercial product note:** Some removed columns may be needed for the commercial engine. Specifications will be defined after the Don Bosco Prep engine build is completed.

**Course Section Processing Order:**

The engine processes each course section's data in this order:

| # | Step | Field | What the engine does |
|---|------|-------|---------------------|
| 1 | Identify | Course Section > Course Code | Which course this section belongs to |
| 2 | Identify | Course Section > Section Number | Which section of the course (e.g., Section 1 of 8) |
| 3 | Load | Course Section > Course Characteristics | Load AP, Singleton, Graduation Requirement, Prescribed Term, Cohort, Co-Schedule from Course file |
| 4 | Check | Course Section > Semester Only | Is this a semester-only course (S1 or S2)? If yes, add Semester Only points |
| 5 | **Calculate** | **Course Section > Raw Priority Value** | **Sum of all applicable course characteristics (AP + Singleton + Grad Req + Semester Only + Cohort + Co-Schedule + Prescribed Term). FIXED for the school year. No student, teacher, or room data. Saved by school year.** |
| 6 | Identify | Course Section > Assigned Teacher | Load the teacher assigned to this section from Teacher-Course Assignments |
| 7 | Load | Course Section > Teacher Total Priority Value | The assigned teacher's Total Priority Value |
| 8 | Identify | Course Section > Assigned Room | Load the room assigned to this section (prescribed or engine-assigned) |
| 9 | Load | Course Section > Room Total Priority Value | The assigned room's Total Priority Value |
| 10 | Identify | Course Section > All Students with Course Requests | From ALL students who requested THIS course, with THIS teacher, in THIS room — build the student list |
| 11 | Rank | Course Section > Student List by Priority Value | Rank all students from high to low |
| 12 | Assign Point Value | Course Section > Top Student Priority Value | The highest-scoring student's value |
| 13 | **Calculate** | **Course Section > Total Priority Value** | **Raw Priority Value (step 5) + Top Student Priority Value (step 12) + Teacher Total Priority Value (step 7) + Room Total Priority Value (step 9). Changes every run. Saved with run number and school year.** |

After each section is placed, the engine returns to step 10 for all remaining sections — rebuilds student lists with remaining students, re-ranks, gets new top students, reloads updated Teacher and Room Totals, and recalculates step 13. Step 5 (Raw) never changes.

### Co-Schedule Groups — Don Bosco Prep

Co-scheduling is a protection mechanism for low-enrollment courses. The principal decides which course sections are grouped together. All sections in a co-schedule group share the same teacher, same room, and same period. This protects students from losing courses due to low enrollment and protects teachers from losing full-time status.

A co-schedule group can contain 2, 3, or 4 course sections. The engine decides the optimal term and period for the group.

**Co-Schedule File (one row per course in the group):**

| Column | Field | Required? | Values |
|--------|-------|-----------|--------|
| A | Co-Schedule Group Name | REQUIRED | Group identifier (e.g., "Dennehy Art Block") |
| B | Course Code | REQUIRED | Must match a Course Code in the Course file |
| C | Teacher ID | REQUIRED | Must match a Teacher ID in the Teacher file — same teacher for all rows in the group |
| D | Prescribed Room | OPTIONAL | Room number (e.g., Art Room J-322) — null = engine decides |

**Example:**

| Group Name | Course Code | Teacher ID | Prescribed Room |
|-----------|-------------|------------|----------------|
| Dennehy Art Block | 253 | Dennehy | Art Room J-322 |
| Dennehy Art Block | 243 | Dennehy | Art Room J-322 |
| Dennehy Art Block | 248 | Dennehy | Art Room J-322 |

**Co-Scheduled Priority Value:**

The engine calculates a separate priority value for each co-schedule group. This value is used to place the entire group as one unit — the engine does not place co-scheduled sections individually.

The Co-Scheduled Priority Value uses the same calculations as a regular Course Section Priority Value (Top Student + Teacher + Room), except it combines the data from ALL sections in the group:

- **Top Student** = the highest-scoring student from ALL students across ALL courses in the co-schedule group
- **Teacher Priority Value** = the teacher's Total Priority Value (same teacher for all sections)
- **Room Priority Value** = the prescribed room's Total Priority Value (0 if no room prescribed)

The Co-Scheduled Priority Value follows the same recalculation cycle — after the group is placed, students are removed, scores recalculate, and the engine moves to the next most restricted section or group.

**Raw vs Total — same rule applies:**

- **Co-Schedule Raw Priority Value** = sum of all Course Section Raw values from all sections in the group + teacher locks + room locks. Fixed for the school year.
- **Co-Schedule Total Priority Value** = Raw + Top Student + Teacher + Room. Changes every run. Saved with run number and school year.

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

**Governing Principle: The schedule is only as flexible as its most restricted elements. Highest gets placed earliest.**

This is the governing principle of the entire engine. The most restricted section gets placed first. The most restricted student fills the seat first. The most restricted teacher gets their sections scheduled first. The most restricted room gets its sections assigned first. After each placement, everything recalculates so the NEXT most restricted element rises to the top. Every decision is backed by math.

The engine uses two separate priority calculations to build the master schedule. This is what makes this system different — priority values drive the entire build.

### Level 1 — Course Section Priority Value (which sections get placed first)

The engine ranks every course section by how restricted it is. The most restricted sections get placed into the master schedule first — because they have the fewest valid time slots and waiting too long means no slot remains.

**Raw Priority Value (fixed for the year):**

> Course Section Raw Priority Value = sum of all applicable course characteristics (AP, Singleton, Graduation Requirement, Semester Only, Cohort Course, Co-Schedule Group, Prescribed Term)

This is how restricted the section is based on its own characteristics. It does not change between runs. See "Actual Point Values" section for specific point values per characteristic.

**Total Priority Value (changes every run):**

> Course Section Total Priority Value = Course Section Raw Priority Value + Top Student Priority Value + Teacher Total Priority Value + Room Total Priority Value

- **Course Section Raw Priority Value** = the section's own characteristics — AP, Singleton, Graduation Requirement, etc. Fixed for the year.
- **Top Student Priority Value** = from all students who requested THIS course, with THIS teacher, in THIS room — the one with the highest Student Priority Value. Only students connected to this specific section are used, not all students who requested the course across all sections.
- **Teacher Total Priority Value** = the Teacher Priority Value of the teacher assigned to this section (includes the teacher's own locks, their top student, and their prescribed room — documented in the Teacher Total Priority Value section below).
- **Room Total Priority Value** = the Room Priority Value of the room assigned to this section (includes room availability, demand, top teacher, and top student — documented in the Room Total Priority Value section below).

All three parents feed into each other: Student Priority includes teacher and room restrictions through course request priority values. Teacher Priority includes the top student and prescribed room. Room Priority includes the top teacher and top student. They are all factors for one another.

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

Weighting locks higher (each lock = 10 points, student grade level range = 10-40) ensures:
- Locks always determine the primary order
- Student priority only makes a difference between sections with similar lock counts
- A section with more locks ALWAYS goes before a section with fewer locks, regardless of who requested it

### Level 2 — Student Priority Value (which students fill each section first)

Once a section is placed on the schedule, the engine fills it with students. Students are added in order of their Student Priority Value — highest first — until the section hits the enrollment cap. Students who don't make the cut are flagged and saved to a report for the principal to review.

**Formula:**

> Student Priority Value = Grade Level Priority Value + Cohort Priority Value (if any) + Special Student Population Priority Value (if any)

**Components:**

| Component | What it measures |
|-----------|-----------------|
| Grade Level Priority Value | Higher grade = higher priority (12 highest, 9 lowest) — universal rule, no exceptions |
| Cohort Priority Value | Student is in a cohort (LEO II) — hard scheduling constraint, higher value |
| Special Student Population Priority Value | Student is in a Special Student Population (Academic Support, Pathway, etc.) — priority boost, lower value than cohort |

**Stacking rules:**
- Different sources stack: Grade Level + Cohort + Special Student Population all add together
- Same program across years does NOT stack: LEO I Special Student Population is replaced by LEO II Cohort, not added on top
- A student can belong to BOTH a cohort and a separate Special Student Population: LEO II (Cohort) + Academic Support (Special Student Population) = both values added

### Engine Build Order

1. Calculate Course Section Raw Priority Value for every section (AP, Singleton, Grad Req, etc.) — fixed for the year
2. Calculate all three parent priority values: Student, Teacher, Room — all feed into each other
3. Calculate Course Section Total Priority Value for every section (Course Section Raw + Top Student + Teacher Total + Room Total)
4. Rank all sections from highest to lowest Course Section Total Priority Value
5. Place the highest-ranked section first — prescribed room, prescribed teacher, prescribed term
6. Fill the section with students — highest Student Priority Value first, until the cap is reached
7. Flag students who didn't make the cut — save to a report for the principal
8. Remove placed students from all priority calculations
9. Recalculate ALL parent priority values (Student, Teacher, Room) with remaining students
10. Recalculate ALL Course Section Total Priority Values with updated parent values (Raw does not change)
11. Re-rank all remaining sections
12. Place the next highest-ranked section
13. Repeat steps 6-12 until all sections are placed or flagged — this cycle runs thousands of times

### Conflict Resolution

When two sections compete for the same period or room, the engine does NOT guess. It compares their Course Section Priority Values. The section with the higher value stays. The section with the lower value gets moved to a different period.

This is the same priority system used for placement order — highest value always wins. The engine will automatically defer to the section with the higher value and place the competing section into a different period because it does not outweigh the other.

### Data Removal Rule

After each run (each time a section is placed), ONLY the data tied to that specific section is removed. Nothing disappears completely until ALL of its sections or course requests are placed.

**Student:**
- The placed course is removed from the student's request list
- That course's priority points are removed from the student's score
- The student STAYS in the pool for all remaining course requests
- The student's score recalculates — it goes DOWN because one course is fulfilled

**Teacher:**
- The placed section is removed from the teacher's section list
- Students who got seats in that section are removed from the teacher's student pool for that course
- The teacher STAYS in the pool for all remaining sections they teach
- The teacher's score recalculates — new top student emerges from remaining students

**Room:**
- The placed section is removed from the room's demand count
- The teacher and students from that section are removed from the room's pool
- The room STAYS in the pool for all remaining sections prescribed to it
- The room's score recalculates — new top teacher, new top student from remaining sections

**Course:**
- The placed section is done, but if the course has multiple sections (e.g., English 12 has 8 sections), only the placed section is removed
- The remaining sections stay in the pool with their own recalculated scores

**Why this works:** Every run starts with a clean, accurate picture of what's left. A student who just got their most restricted course placed will have a LOWER score on the next run — they don't keep jumping the line. A teacher whose top student was just placed gets a new, lower top student. Scores always reflect reality at THAT moment — not reality from a previous run. This eliminates inflated priority and stale rankings.

### Run Log (Audit Trail)

The engine stores the priority values for every Student, Teacher, Room, and Course Section at EVERY run. This creates a complete history from Run #1 through the final run — every score, every decision, every placement.

**What is stored at each run:**

| Data Point | What it records |
|-----------|----------------|
| Run Number | Which run this is (1, 2, 3, ... thousands) |
| Section Placed | Which course section was placed in this run |
| Period + Term Assigned | Where the section was placed (e.g., Period C, S1) |
| Course Section Priority Value | The section's score at the time of placement |
| Top Student Priority Value | The top student's score used in the section's calculation |
| Teacher Total Priority Value | The teacher's score used in the section's calculation |
| Room Total Priority Value | The room's score used in the section's calculation |
| Students Seated | List of student IDs who received seats |
| Students Not Seated | List of student IDs who requested the course but did not make the cut |
| Score Changes | Which students, teachers, and rooms had their scores recalculated and what the new scores are |

**Why this matters:** The run log makes the schedule 100% defensible. Every placement can be traced back to the exact scores that determined it. No opinion, no guesswork — only math.

### Clash Report

When the engine cannot place a section without creating a conflict, the run log proves exactly WHY.

**What the clash report shows:**

- Which section could not be placed
- Which previously placed section is blocking it, and in which run it was placed
- The priority scores of both sections at the time of the conflict
- Which prescribed decisions (made by the principal) caused the clash

**Example — student didn't get a seat:**

"AP Art Section 1 was placed in Run #38 with a Course Section Priority Value of 54. Student #101's priority value at Run #38 was 6, ranking them #27 out of 32 students who requested that section. The section cap is 25. Students ranked #1 through #25 by priority filled the seats. Student #101 ranked #27 and did not receive a seat."

**Example — principal's prescriptions contradict each other:**

"Teacher Smith was prescribed to Period C (principal's decision) AND prescribed to Room Lab-1 (principal's decision), but Room Lab-1 is only available during Periods D and E. These two prescriptions contradict each other."

**The principal can see exactly which of THEIR decisions caused the problem.** The system does not say "it didn't fit." It says "here is the math that proves why it didn't fit, and here is exactly which prescribed input created the conflict."

### Resolution Options

When a clash is found, the engine does not just report the problem. It provides the principal with a ranked list of data-backed options to resolve it.

**Each option includes:**

| Data Point | What it shows |
|-----------|--------------|
| Option Letter | A, B, C, etc. |
| What Changes | Plain English description of the change (e.g., "Move Section X to Period D") |
| Score Impact | How many priority points are gained or lost by making this change |
| Side Effects | Which other students, teachers, or sections are affected |
| Recommended | YES or NO — the engine recommends the option with the lowest score impact |

**Example:**

"Student #101 did not receive a seat in AP Art Section 1. Here are the options:"

| Option | What Changes | Score Impact | Side Effects | Recommended |
|--------|-------------|-------------|-------------|-------------|
| A | Increase AP Art Section 1 cap from 25 to 27 | No score change | 2 additional students seated, room capacity must support 27 | YES |
| B | Create AP Art Section 2 | -12 points (new section has fewer locks) | Requires a second teacher and room for AP Art | NO |
| C | Remove Student #88 (lowest priority in section, score 3) and replace with Student #101 (score 6) | +3 points net gain | Student #88 loses seat, flagged for principal review | NO |

**The principal chooses. The engine provides the math. The schedule is defensible.**

### Cohort Scoring Rule

When calculating the priority value for a cohort section, the engine uses the HIGHEST student score from the cohort — NOT the average.

**Why:** The cohort is only as flexible as its most restricted member. All cohort students are locked together — the engine cannot pick and choose. If the top student in the cohort is a Grade 12 with a score of 8, the entire group must be placed on that student's timeline. Using the average would hide the most restricted student behind lower-scoring members and cause the group to be placed too late.

Each cohort section (e.g., LEO II Cohort A vs. LEO II Cohort B) is scored independently. Different locked student lists, possibly different teachers and rooms — different scores. The cohort with the higher top student gets placed first.

### Weighted Priority Tests

All tests use the new formula: Course Section Total = Course Section Raw + Top Student Priority Value + Teacher Total Priority Value + Room Total Priority Value.

Point values: AP = 30, Singleton = 25, Grad Req = 20, Semester Only = 15, Cohort = 15, Co-Schedule = 15, Prescribed Term = 10. Each teacher/room lock = 10. Room demand = 5 per section. Student grade levels: 9 = 10, 10 = 20, 11 = 30, 12 = 40. Cohort = 50, Special Student Population = 25.

| Test | Section A | Section B | Result |
|------|-----------|-----------|--------|
| AP Singleton S2 vs. regular FY elective | Raw 70 (30+25+15) + top student 40 + teacher 30 + room 20 = **160** | Raw 0 + top student 40 + teacher 0 + room 10 = **50** | A first — course characteristics dominate |
| Same course characteristics, different top students | Raw 20 + top student 115 (Gr12+Cohort+Special Student Population) + teacher 30 + room 20 = **185** | Raw 20 + top student 10 (Gr9) + teacher 30 + room 20 = **80** | A first — higher-priority student breaks tie |
| High course raw + low students vs. low raw + high students | Raw 70 + top student 10 + teacher 20 + room 10 = **110** | Raw 0 + top student 115 + teacher 20 + room 10 = **145** | B first — but B has higher Total because student and teacher scores are high enough to overcome. Course Raw alone is a floor, not an override of all other factors combined |
| Heavy teacher locks vs. no locks | Raw 20 + top student 40 + teacher 80 (8 locks) + room 20 = **160** | Raw 20 + top student 40 + teacher 0 + room 20 = **80** | A first — teacher locks dominate |
| Cohort student vs. non-cohort | Raw 15 + top student 90 (Gr12+Cohort) + teacher 30 + room 20 = **155** | Raw 15 + top student 40 (Gr12) + teacher 30 + room 20 = **105** | A first — cohort student raises section priority |
| AP Singleton Grad Req Cohort Course vs. regular semester elective | Raw 90 (30+25+20+15) + top student 40 + teacher 30 + room 20 = **180** | Raw 15 + top student 40 + teacher 0 + room 10 = **65** | A first — most restricted section always wins |
| Same total, different composition | Raw 50 + top student 30 + teacher 20 + room 10 = **110** | Raw 0 + top student 40 + teacher 50 + room 20 = **110** | Tie — engine uses Course Section Raw as tiebreaker. A first (Raw 50 vs 0) |

All 7 tests pass. Course Section Raw creates a permanent floor that prevents late-run score collapse. Teacher and room locks add significant weight. Student priority breaks ties between similarly restricted sections. The most restricted section is always placed first.

### Room Total Priority Value

The engine calculates a priority value for each prescribed room. A room with more restrictions and higher-demand teachers and students must be scheduled first — waiting too long means no valid periods remain.

**Formula:**

> Room Total Priority Value = Room Availability Locks (×10) + Room Demand + Top Teacher Priority Value + Top Student Priority Value

**Components:**

| Component | What it measures |
|-----------|-----------------|
| Room Availability Locks | Number of periods/terms the room is NOT available — fewer available slots = more restricted |
| Room Demand | Number of course sections competing for this room — more sections = harder to schedule |
| Top Teacher Priority Value | From ALL teachers prescribed to this room, the one with the highest Teacher Total Priority Value |
| Top Student Priority Value | From ALL students who have a course request for any course prescribed to this room, the one with the highest Student Priority Value |

### Teacher Total Priority Value

The engine calculates a priority value for each teacher. A teacher with more restrictions, higher-demand students, and a more restricted prescribed room must be scheduled first.

**Formula:**

> Teacher Total Priority Value = Teacher Locks (×10) + Top Student Priority Value + Prescribed Room Priority Value

**Components:**

| Component | What it measures |
|-----------|-----------------|
| Teacher Locks | Prescribed period, prescribed term, prescribed room, prescribed cohort — each lock × 10 |
| Top Student Priority Value | From ALL students across ALL of the teacher's prescribed courses, the one with the highest Student Priority Value |
| Prescribed Room Priority Value | The Room Total Priority Value of the room prescribed to this teacher (0 if no room is prescribed) |

### Recalculation Cycle

The engine does NOT calculate priority values once and use them for the entire build. Priority values are LIVE — they change every time a section is placed.

**After each section is placed, the engine:**

1. Removes all students who received seats from the requesting pool
2. Recalculates the Teacher Total Priority Value using the remaining students — new top student emerges
3. Recalculates the Room Total Priority Value using the remaining teachers and students — new top teacher and top student emerge
4. Recalculates the Course Section Total Priority Value using the updated parent values (Raw does not change)
5. Re-ranks ALL sections, teachers, and rooms with their new scores
6. Places the next most restricted section
7. Repeats until all sections are placed or flagged for the overflow report

**Why this matters:**

Without recalculation, a teacher who started with one high-priority student could stay ranked high even after that student is already placed. That would waste prime schedule positions on sections that no longer need them. The recalculation cycle ensures the engine is always working on the most restricted situation REMAINING — not the most restricted situation that existed at the start.

**Example:**

1. Teacher Smith has 60 students across all courses — top student priority = 8
2. Engine places Teacher Smith's AP Singleton SEM II section — 22 students get seats
3. Those 22 students are removed from Teacher Smith's student list
4. Teacher Smith now has 38 students — new top student priority = 6
5. Teacher Smith's total score drops
6. Engine re-ranks ALL teachers — maybe Teacher Jones now ranks higher
7. Engine places Teacher Jones's most restricted section next
8. Cycle repeats until every section is placed

### Actual Point Values

All data containers are fully defined. The point values below ensure the student with the most restrictions always calculates highest and the most restricted course section is always placed first.

Every entity has two scores:
- **Raw Priority Value** = uses only the entity's own data. FIXED for the school year. Does not change between runs.
- **Total Priority Value** = Raw + data from connected parents. Changes every run as sections are placed and data is removed.

---

#### Student Raw Priority Value (fixed for the year)

Who the student IS — no course, teacher, or room data.

| Component | Points |
|-----------|--------|
| Grade 12 | 40 |
| Grade 11 | 30 |
| Grade 10 | 20 |
| Grade 9 | 10 |
| Cohort (LEO II) | 50 |
| Special Student Population (LEO I, Academic Support, Pathway) | 25 |

Maximum Student Raw = 40 + 50 + 25 = **115**
Minimum Student Raw = 10 + 0 + 0 = **10**

**Formula:** Student Raw = Grade Level + Cohort (if any) + Special Student Population (if any)

#### Student Total Priority Value (changes every run)

**Formula:** Student Total = Student Raw + Course Request Priority Values

Course Request Priority Values come from step 19 of the Student processing order. They include the course's own restrictions PLUS the prescribed teacher's restrictions PLUS the prescribed room's restrictions. Same course, multiple categories = highest value only.

---

#### Course Section Raw Priority Value (fixed for the year)

How restricted the section is based on its own characteristics. These values stack — each characteristic independently restricts the section's placement options.

| Component | Points |
|-----------|--------|
| AP | 30 |
| Singleton | 25 |
| Graduation Requirement | 20 |
| Semester Only (S1 or S2) | 15 |
| Cohort Course | 15 |
| Co-Schedule Group | 15 |
| Prescribed Term | 10 |

Examples:
- AP Singleton, S2-only, Grad Req = 30 + 25 + 15 + 20 = **90**
- Cohort Course, Prescribed Term = 15 + 10 = **25**
- Regular FY elective with 8 sections = **0**

**Formula:** Course Section Raw = sum of all applicable course characteristics

#### Course Section Total Priority Value (changes every run)

**Formula:** Course Section Total = Course Section Raw + Top Student Priority Value + Teacher Total Priority Value + Room Total Priority Value

Only students requesting THAT course, with THAT teacher, in THAT room are used to calculate the Top Student Priority Value. After each placement, students are removed, scores recalculate, and the engine moves to the next most restricted section.

---

#### Teacher Raw Priority Value (fixed for the year)

How locked down the teacher is based on their own prescriptions and availability.

| Component | Points per lock |
|-----------|----------------|
| Prescribed Room | 10 |
| Prescribed Period | 10 |
| Prescribed Term | 10 |
| Prescribed Cohort | 10 |
| Unavailable Period | 10 |

Example: Teacher with 3 prescribed rooms, 1 prescribed period, 2 unavailable periods = 6 locks × 10 = **60**

**Formula:** Teacher Raw = total number of locks × 10

#### Teacher Total Priority Value (changes every run)

**Formula:** Teacher Total = Teacher Raw + Top Student Priority Value + Prescribed Room Priority Value

Top Student = the highest-scoring student from all students who have a course request for any of this teacher's courses. After each placement, students are removed, the teacher's student list is rebuilt, and the top student recalculates.

---

#### Room Raw Priority Value (fixed for the year)

How restricted the room is based on availability and demand.

| Component | Points |
|-----------|--------|
| Each unavailable period | 10 per lock |
| Each unavailable term | 10 per lock |
| Demand (sections prescribed to room) | 5 per section |

Example: Room unavailable Period G, available all terms, 6 sections prescribed = 10 + 0 + 30 = **40**

**Formula:** Room Raw = (unavailable periods × 10) + (unavailable terms × 10) + (sections prescribed × 5)

#### Room Total Priority Value (changes every run)

**Formula:** Room Total = Room Raw + Top Teacher Priority Value + Top Student Priority Value

Top Teacher = the highest-scoring teacher from all teachers prescribed to this room. Top Student = the highest-scoring student from all students who have a course request for any course prescribed to this room. After each placement, lists are rebuilt and scores recalculate.

---

#### Co-Schedule Group Raw Priority Value (fixed for the year)

Combined restrictions from all sections in the group.

| Component | Points |
|-----------|--------|
| All Course Section Raw values from all sections in the group | Sum of all |
| All teacher locks from the shared teacher | 10 per lock |
| All room locks from the prescribed room (if any) | 10 per lock |

**Formula:** Co-Schedule Group Raw = sum of all section Raw values + teacher locks + room locks

#### Co-Schedule Group Total Priority Value (changes every run)

**Formula:** Co-Schedule Group Total = Co-Schedule Group Raw + Top Student Priority Value + Teacher Total Priority Value + Room Total Priority Value

Top Student = the highest-scoring student from ALL students across ALL courses in the co-schedule group. The co-schedule group is placed as one unit — the engine does not place co-scheduled sections individually.

---

#### Why these values work

The governing principle: "The schedule is only as flexible as its most restricted elements. Highest gets placed earliest."

1. **Locks outweigh student priority.** One teacher lock (10 points) is meaningful against a student grade level spread of 10-40. A teacher with 5 locks (50 points) already matches the maximum student raw score. This ensures locked sections are always placed before flexible ones.

2. **Course Section Raw creates a floor.** An AP Singleton (55 points raw) can never be outranked by a regular elective (0 points raw) no matter how high the student, teacher, or room scores are in later runs. The section's own restrictions are permanent.

3. **Grade level always matters within the same restriction level.** A Grade 12 student (40) always outranks a Grade 9 student (10) when all other factors are equal. The 10-point gap between grades is large enough to break ties but small enough that it never overrides locks or course characteristics.

4. **Cohort outranks Special Student Population.** Cohort (50) is double Special Student Population (25) because a cohort is a hard constraint (locked group) while Special Student Population is flexible (engine has options).

5. **After each run, only placed data is removed.** The Raw values never change. The Total values recalculate using only remaining data. This prevents late-run score collapse on inherently restricted sections.
