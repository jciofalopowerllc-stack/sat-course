# Master Schedule Builder — Transfer Specification

**Source:** the "Schedule Optimizer" project (Claude.ai), which built a working master schedule for Don Bosco Prep
**Target:** the "Master Schedule Builder" project (Claude Code), a commercial web product
**Date:** August 11, 2026
**Purpose:** Transfer the design decisions that made the manual build outperform the coded product, so the code can be revised to match.

---

## HOW TO USE THIS DOCUMENT

This is not documentation. It is a **specification and audit checklist**.

Give it to Claude Code and ask it to do two things, in this order:

1. **Audit** the existing codebase against every rule in Sections 2 through 8, and report which rules the code already satisfies, which it violates, and which it does not address at all.
2. **Only then** propose changes.

Do not ask for code changes on the first pass. The audit is the valuable part — it will tell you where the two projects actually diverge, which is currently unknown.

---

## SECTION 1 — THE CENTRAL FINDING

The Claude.ai project outperformed the coded product. The reason is almost certainly not that it used a better algorithm. It is that it used a **worse** algorithm with **better rules**.

A hand-run process is slow, so it cannot afford to explore. It compensates by being extremely strict about what counts as a valid answer. A coded optimizer is fast, so it explores widely — and if its objective function is even slightly wrong, it will find a high-scoring solution that is educationally unacceptable.

The specific failure pattern to look for in the existing code:

> **A weighted scoring function that allows a high-value elective to outrank a graduation requirement.**

If the code computes anything resembling `score = w1*gradReq + w2*pathway + w3*apHonors + w4*elective` and then maximizes total score, it is structurally capable of leaving a senior one credit short of graduating in order to place three students into AP Studio Art. That trade is mathematically attractive and educationally indefensible. The manual process never made it because a human would never write it down.

**This is the single most important thing to check.**

---

## SECTION 2 — THE PRIORITY MODEL (replaces any weighted scoring)

### 2.1 Four tiers, fixed

| Tier | Name | Definition |
|---|---|---|
| 1 | Graduation Requirement | The course satisfies a year of a stated graduation requirement |
| 2 | Pathway Required | The course is required by the student's declared pathway |
| 3 | AP / Honors Elective | Advanced elective, not required |
| 4 | General Elective | Everything else |

### 2.2 Strict lexicographic ordering — NOT weighted

The optimizer must maximize Tier 1 placements **to completion**, freeze that result, then maximize Tier 2 against the remaining capacity, then Tier 3, then Tier 4.

**A higher tier is never traded for any quantity of a lower tier.** Not for ten. Not for a hundred. There is no exchange rate between tiers, and the code must not contain one.

Implementation note: this is a sequence of optimizations with each prior result held as a hard constraint, not a single optimization with large weights. Large weights are not the same thing — they are an exchange rate with a big number in it, and a sufficiently large volume of low-tier wins will eventually cross it.

### 2.3 The fairness guard

After each tier is maximized, run a **worst-served-student** pass before moving to the next tier.

Total placements is a bad objective on its own. It is satisfied by giving 700 students everything and 10 students almost nothing. Those 10 students are the ones whose parents call the school.

The guard: within the set of solutions that achieve the maximum count for the tier just solved, prefer the one that maximizes the number of requests granted to the least-served student. Repeat down the list (this is maximin, then leximin).

### 2.4 Scarcity as a within-tier tiebreak

Within a single tier, when two requests compete for the same resource, the one for the **scarcer** course wins.

Empirically measured in the source project: a request for a course with only one section fails roughly **5.7 times more often** than a request for a course with three or more sections. Placing scarce requests first costs nothing, because the abundant course still has room later. Placing abundant requests first destroys the scarce one permanently.

Scarcity should be computed as available seats across all sections of the course, not section count.

---

## SECTION 3 — POLICY IS DATA, NEVER CODE, NEVER INFERENCE

This is the second-largest lesson, and for a commercial product it matters more than the first, because it determines whether the product works at School #2.

### 3.1 Never infer classification from a course title

The source project made this error repeatedly and was corrected each time. The standing rule became absolute:

> **Tier, priority, requirement status, and pathway membership must come from a school-provided data file. They are never derived from the course title, course number, department, or any string-matching heuristic.**

Concrete failures this prevents:

- `AP Calculus BC` is a **Tier 1 graduation requirement** for a senior who needs a fourth year of math. `AP Statistics` for that same senior is a **Tier 3 elective**. Both are "AP Math." Title parsing cannot tell them apart.
- The same AP course is Tier 1 or Tier 3 **for different students in the same section**, depending on how many years of that subject each has already completed.
- `AP Italian`, `AP Spanish`, and `AP Latin` are fourth-year electives at this school, not requirements — despite being language courses at a school with a three-year language requirement.
- A Business course can satisfy half a year of the Social Studies requirement.

If the code contains regular expressions against course names to determine importance, that is a defect, not a shortcut.

### 3.2 Graduation requirements are counted in years, not flagged on courses

The requirement is not "this course is required." It is "the student needs N years of this subject, and this course provides one of them."

The Don Bosco configuration, as an illustration of the shape the data must take:

| Subject | Years required | Notes |
|---|---|---|
| English | 4 | |
| Math | 4 | |
| Theology | 4 | |
| World Language | 3 | Spanish, Italian, or Latin — any one family |
| Science | 3 | Grade 12 science is **not** required |
| Social Studies | 3.5 | 0.5 may be satisfied by Business |
| Physical Education | PE 9 and PE 10 only | PE 11 and PE 12 not required |

Consequences the code must handle:

- **Tier depends on the student's transcript history, not the course.** The Nth year of a subject is Tier 1 if N is within the requirement, Tier 3 or 4 if beyond it.
- **Requirement families.** Three years of "a world language" is satisfied by any one of three course families. The code needs a family/group concept, not a per-course flag.
- **Fractional credits.** 3.5 years is a real requirement, and 0.5 of it comes from a different department.
- **Exactly-one resolution.** Where a student requests several courses that could each complete the same remaining requirement (this occurred with Grade 12 Social Studies), exactly one is designated Tier 1 — the highest AP/Honors value — and the remainder become electives. The code must resolve this deterministically rather than marking all of them Tier 1.

### 3.3 Everything above must be editable configuration in the product

No school has this exact table. A commercial product needs a **graduation requirements editor** where an administrator defines subjects, year counts, course families, fractional allowances, and grade-level exemptions. The Don Bosco values become a seeded example, not a default and never a constant.

Audit question for the code: *if a school required 2 years of language and 4 of science, how many files would have to change?* If the answer is more than zero, the policy is in the code.

---

## SECTION 4 — HARD CONSTRAINTS (violations = invalid solution, not penalty)

These must be enforced as constraints, not scored. A solution that breaks any of them is not a worse solution; it is not a solution.

### 4.1 Teacher load

- No teacher exceeds their **Max Teaching Periods** unless explicitly approved for a sixth period **in that specific term**, per the teacher profile file.
- **Semester balance:** no teacher may have an S1/S2 teaching-period gap of 2 or more. A 5/5 load is valid; 4/6 is not. This constraint alone forced four section moves in the source build.
- Sixth-period approvals are per-teacher **and per-term**. A teacher approved for S1 only is not approved for S2. The source school had 6 approved teachers across 9 term-assignments — the counts differ, and that is the point.

### 4.2 Co-scheduled blocks count as ONE period

Two or more sections sharing the same **teacher + term + period** are a co-scheduled block and consume **one** period of that teacher's load, not two.

This was a genuine bug source. If the code counts them separately, it will report teachers as overloaded who are not, and will reject valid schedules.

Co-scheduled blocks in the source school: Guitar, Programming, Robotics, Italian, Theater, AP Art, Studio Art. Each must maintain correct term, period, teacher, and room alignment across all its member sections — they move together or not at all.

### 4.3 Rooms

- **Non-shared rooms.** Certain rooms are restricted to one prescribed teacher and may not be assigned to anyone else, ever. Six such rooms existed at the source school. This is a hard constraint with zero tolerance.
- **Room capacity** is a hard cap. The Success Center seats 12, and every Academic Support section was clamped to 12.
- **Room eligibility sets.** Some course types may only be placed in certain room categories. "Engine Choice" sections were restricted to traditional classrooms only.
- Prescribed rooms in the source data are honored, not suggested.

### 4.4 Cohort integrity

Some student groups must stay together. The L.E.O. II program had two cohorts of 18 students who had to be enrolled in the same section of one specific course, in Semester 1, with the section number allowed to float.

The code needs a **cohort object** that binds a named set of students to a course with configurable term and section constraints. Note the specificity: cohort integrity applied to *one course only*, not to the students' full schedules.

### 4.5 Section capacity with controlled flex

Section caps may be raised by **+2** where doing so resolves an otherwise-unplaceable request. This is a bounded, explicit, and auditable flex — not an uncapped soft constraint. Every use of the +2 should appear in a report.

### 4.6 Seats are not reserved for the future

Do not hold seats open so that a student can complete a program in a later year. Maximize placement in the current year. A held seat is a guaranteed loss traded for a speculative gain.

---

## SECTION 5 — IDENTITY AND DATA JOINS

A full day of the source project was lost to a single join failure.

The L.E.O. cohort file's first column was labeled in a way that implied Student ID, but actually contained **Course Request ID**. The join produced **zero matches**, silently. The fix was to match on student name instead.

Requirements for the product:

1. **Every join must report its match rate.** A join returning 0 of 36 rows must halt the build with a visible error, never proceed with an empty result.
2. **Fallback matching keys.** ID first, then name, with fuzzy handling for case, whitespace, and `Last, First` versus `First Last`.
3. **A pre-flight validation stage** that runs before any optimization: check that every referenced course exists, every teacher exists, every room exists, every student ID resolves, and every ID column contains the type of ID its header claims.
4. **A validation report the user sees before the build starts**, not after it fails.

Related: the source project also discovered a student in the request data who was **inactive** in the school's information system. The product should reconcile the active roster against the request file and flag discrepancies rather than scheduling ghosts.

---

## SECTION 6 — DIAGNOSTICS THE PRODUCT MUST PRODUCE

This is where the product can beat both projects, and it is the most commercially valuable section.

The source project's most useful output was not the schedule. It was the analysis of **why** 128 requests could not be placed. That analysis is what a school will pay for, because it tells them what to change next year.

### 6.1 Required failure attribution

For every unplaced request, record the **structural cause**, not just "no seat available." The source project's four causes:

| Cause | Share of failures |
|---|---|
| Course taught by a single teacher | **81%** (104 of 128) |
| Course offered as a singleton (one section) | 41% (52 of 128) |
| Senior schedule congestion | 51% (65 of 128) |
| Co-scheduled block locked to one period | 16% (20 of 128) |

Causes overlap; report them as overlapping tags, not a partition.

### 6.2 Required structural metrics

- **Seat utilization.** The source school ran at **58.9%** — 6,426 students in 10,902 seats. The finding: the school was not short of capacity, it was short of *choice*. Any product that reports only fill rate misses this entirely.
- **Under-enrolled section report.** 41 sections held 5 or fewer students, consuming 41 teacher periods to serve 97 students total. Theater Arts ran 3 sections for 6 students; Music ran 8 sections for 31. Surfacing this lets a school redirect staffing into the sections that are actually blocking students.
- **Single-teacher course exposure.** 123 of 143 courses had exactly one qualified teacher. This is the highest-leverage metric in the entire analysis and should be on the dashboard.
- **Full-year vs semester exposure.** 96 of 143 courses were full-year only. A full-year elective requires the student to be free at that period in *both* terms, making it the most restrictive object in the build. Flag these.
- **Period-level congestion.** 34 seniors were unscheduled at S2 period G — nearly triple any other slot. A single number that points at a single fixable slot.
- **Catalogue integrity.** Chorus received 10 requests with no section existing anywhere. Four English courses received requests after the build began. The product should freeze the catalogue at request-open and flag requests against nonexistent courses immediately.

### 6.3 The output should be prescriptive

Each diagnostic should carry a recommended action. Examples generated by the source project:

- Set a published **minimum viable enrollment** (suggest 8) before requests open — frees an estimated 20–25 teacher periods.
- Open second sections for the specific bottleneck courses, named.
- Convert full-year electives to semester where pedagogically possible.
- Break the single-period lock on pathway blocks. The Studio Art Block alone caused 9 failures while Studio Art III sat with 30 empty seats *inside that block* — students could not reach the block, the course was not full.
- Cross-train a second teacher for the 15 highest-demand single-teacher courses. **No new headcount, and the highest-impact change available.**

---

## SECTION 7 — HUMAN-IN-THE-LOOP AND THE RULINGS LEDGER

The source build required roughly a dozen judgment calls that no algorithm could have made correctly on its own. Examples:

- Which of two AP Math courses counts as a senior's fourth year of math.
- A student holding two conflicting math courses, one of which was wrong.
- Two students each enrolled in both an AP and an Honors section of the same subject.
- A source file (T7) that contradicted itself on which room a Geometry section used.

**The product must not attempt to resolve these silently.** It must:

1. **Detect the ambiguity** and stop.
2. **Present the specific choice** to the administrator with the data behind it.
3. **Record the decision** in a persistent rulings ledger.
4. **Apply the recorded decision automatically** on every subsequent run.

The source project maintained a **SCHEDULING RULES sheet with 24 numbered rules**, embedded inside every output workbook. This is the model. Every ruling has an ID, a date, the decision, and the reason. It travels with the output so the schedule can always be explained.

For a commercial product, this becomes the **exception queue** — and it is likely the feature that distinguishes it from competitors, because it converts the optimizer from a black box into an auditable process.

**Contradictory source data is normal, not exceptional.** Design for it.

---

## SECTION 8 — OUTPUT AND DELIVERABLE DESIGN

A hard-won lesson, and the source of the single largest complaint in the project's history.

> **One consolidated multi-sheet workbook. Never a sprawl of separate files.**

The source project at one point produced 16+ separate output files. This was described as a significant failure. The corrected pattern was a single 10-sheet workbook containing the schedule, the enrollment, the audits, the exceptions, and the rules — all in one object.

For the web product this translates to:

- One export artifact per build, with internal navigation.
- The rules ledger **embedded in the export**, not stored only in the app.
- Every export self-describing: what was built, when, under which rules, with which exceptions.
- **Build versioning**, so a school can compare run to run and see what changed.

Secondary formatting lessons that proved to matter:

- Departmental views (one tab per department) were more usable than one flat sheet.
- Visual separators between teacher blocks improved readability — but **broke Excel's autofilter**. The product should offer visual grouping and filtering as alternative modes, not both at once.
- Summary tabs should use live formulas, so a user editing the detail sees the totals move.
- **Watch double-counting in summaries.** Five teachers spanned two departments each, so the sum of per-department teacher counts was 68 while the true unique count was 63. Report unique counts and show the overlap.

---

## SECTION 9 — ACCEPTANCE TESTS

The code should pass all of these before it is considered improved. Each is drawn from a real event in the source build.

| # | Test | Expected behavior |
|---|---|---|
| 1 | A schedule exists where 1 graduation requirement can be placed OR 20 electives, not both | Places the graduation requirement. Every time. |
| 2 | Total placements are equal in two solutions, but one leaves a student with 1 of 7 requests | Selects the other solution. |
| 3 | A singleton course and a 4-section course compete for the same student period | Singleton is placed. |
| 4 | A senior needs a 4th math year and requests AP Calc BC and AP Statistics | AP Calc BC → Tier 1, AP Statistics → Tier 3. No title parsing involved. |
| 5 | Two sections share teacher + term + period | Counted as ONE period against that teacher's load. |
| 6 | A teacher would land at 4 periods in S1 and 6 in S2 | Rejected as invalid. |
| 7 | A teacher is approved for a 6th period in S1 only, and the solver wants one in S2 | Rejected. |
| 8 | A non-shared room is the only room available for another teacher's section | Section goes unplaced. The room is not used. |
| 9 | An 18-student cohort cannot fit in one section | Halts and raises an exception. Does not split the cohort. |
| 10 | A join key column contains the wrong ID type | Build halts with a named error before optimization begins. |
| 11 | A source file contradicts itself on a room assignment | Exception queue, not a silent pick. |
| 12 | 10 requests reference a course with no sections anywhere | Flagged at validation, not discovered at the end. |
| 13 | Graduation requirements are changed to 2 years language, 4 years science | Zero code changes required. |
| 14 | A build completes with unplaced requests | Every unplaced request carries a structural cause tag. |

---

## SECTION 10 — THE PROMPT TO GIVE CLAUDE CODE

Copy the block below into Claude Code after you have placed this file in the project folder.

---

I have added a file called `MASTER_SCHEDULE_BUILDER_TRANSFER_SPEC.md` to the project root. It contains the design rules from a separate, manually-run scheduling project that outperformed this codebase on a real school build.

Please do the following, and do not write any code yet:

1. Read the spec in full.
2. Audit this codebase against Sections 2 through 8. For each numbered rule, tell me one of: SATISFIED (and where in the code), VIOLATED (and where), or NOT ADDRESSED.
3. Pay particular attention to Section 2.2. Tell me explicitly whether this codebase uses lexicographic tier ordering or a weighted scoring function. If it uses weights, show me the exact lines.
4. Tell me whether any graduation requirement, tier value, or course classification is currently derived from a course title, course number, or department string. Show me every instance.
5. Rank the gaps you find by how much they would change the output quality on a real school build.

Write the audit to a file called `SPEC_AUDIT.md`. After I have read it, we will decide together what to change and in what order.

---

## SECTION 11 — WHAT NOT TO COPY

For balance, the source project was worse than the code product in real ways. Do not import these:

- It was slow and largely manual.
- It required constant human correction, and made the same class of error more than once.
- It produced file sprawl before it was corrected.
- Its rules lived in a spreadsheet tab rather than in version control.
- It was tuned to one school. **Every specific number in this document — 4 years of English, +2 section flex, minimum enrollment of 8, the six restricted rooms — is Don Bosco Prep's configuration, not a universal truth.** The *shapes* transfer. The *values* must be configurable.

The goal is not to make the code project imitate the manual process. It is to give the code project the manual process's strictness while keeping its speed.
