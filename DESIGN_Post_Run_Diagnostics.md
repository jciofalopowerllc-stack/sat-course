# Design: Post-Run Diagnostics & Cross-Run Learning

**Author:** Claude (for JC Iofalo review)  
**Date:** 2026-08-05  
**Status:** DESIGN — awaiting JC approval before implementation

> **Universal Data Rule:** Every cell in every template (T1–T9) must contain a value. Use `N/A` for fields where no data applies. Blank cells are validation errors — engine refuses to run until corrected.

---

## The Problem

The engine builds fresh every run. It does not learn from its own results. When it places 752 Economics H in periods B,D and that causes 24 conflicts, the next run makes the same decision because it has no memory of what went wrong.

Additionally, the engine's Job 1 conflict prediction (`_predict_conflict_score()`) estimates student conflicts but cannot simulate them. It sees co-enrollment counts but can't see multi-course blocking chains like:

> "849/851 Theology occupies periods A,B,D,F. 440 Precalculus has sections in A,B,D,F,G. Every Gr12 student takes theology. Result: theology blocks 4 of 5 Precalculus periods. If the student also has something in G, they have ZERO options."

The engine can't reason about this chain because it evaluates one course at a time, not the interaction of all courses across all periods.

---

## The Solution: Phase A-1 (Post-Run Feedback Analysis)

A new phase that runs **inside the engine, after Job 2 completes**, analyzes the actual conflicts, and produces two outputs:

1. **`run_diagnostics.json`** — Machine-readable file the engine reads on the NEXT run
2. **System Improvement Report** — Human-readable summary printed to console

### How It Works

```
Run N:
  Job 1 → Place sections
  Job 2 → Place students → 228 conflicts
  Phase A-1 → Analyze conflicts → Write run_diagnostics.json

Run N+1:
  Load run_diagnostics.json from Run N
  Phase A-0 → Conflict matrix + diagnostic adjustments
  Job 1 → Place sections (with learned biases)
  Job 2 → Place students → fewer conflicts
  Phase A-1 → Analyze → Update run_diagnostics.json
```

### What Phase A-1 Analyzes

#### 1. Period Coverage Analysis
For every course with conflicts, compute:
- Which periods it covers vs. which it doesn't
- How many conflicts are caused by limited coverage
- Which UNCOVERED periods would eliminate the most conflicts if a section were placed there

Example output:
```json
{
  "752": {
    "conflicts": 24,
    "periods_covered": ["B", "D"],
    "periods_uncovered": ["A", "C", "E", "F", "G"],
    "best_uncovered_period": "G",
    "conflicts_if_moved_to_G": 8,
    "teacher": "Zawacki, Richard",
    "teacher_free_periods": ["G"],
    "recommendation": "MOVE_SECTION_TO_G",
    "blocked_by_teacher": false
  }
}
```

#### 2. Blocking Chain Analysis
Identify multi-course blocking chains that the single-course conflict predictor can't see:
- "849/851 in A,B,D,F blocks 4/5 periods of 440 Precalculus (A,B,D,F,G)"
- "440+448 together cover A,B,D,F,G + A,F = still missing C,E"

#### 3. Teacher Constraint Bottlenecks
Identify teachers whose load creates structural bottlenecks:
- Zawacki teaches 752+742+732 = 6 sections across A,B,C,D,E,F — only G is free
- This means 752 and 742 can NEVER be in the same period, limiting student options

#### 4. Conflict Hotspot Periods
Which periods are overloaded with conflict-causing courses:
- Period D: theology (849/851) + Forensics (546) + Bloomberg (758) + Economics H (752)
- Period G: Forensics (546) + Robotics (590/591) + Bloomberg (758) + A&P H (543)

### What the Engine Does With run_diagnostics.json

On the NEXT run, the engine loads the diagnostics and applies **period bias adjustments** to `_predict_conflict_score()`:

1. **Coverage penalty boost**: If Run N showed course X with 24 conflicts and only 2 periods covered, Run N+1 gives a STRONGER penalty for placing X in those same 2 periods and a STRONGER reward for uncovered periods. The adjustment is proportional to the conflict count from the prior run.

2. **Blocking chain awareness**: If Run N showed "849/851 in A,B,D,F blocks 440 which is in A,B,D,F,G", Run N+1 adds a bias that pushes 440 sections toward C,E (the periods NOT occupied by theology).

3. **Period hotspot cooling**: If Run N showed Period D has 4 high-conflict courses, Run N+1 adds a penalty multiplier for placing additional conflict-prone courses in Period D.

### What the Engine Does NOT Do

- It does NOT auto-fix. It adjusts scoring weights, not hard rules.
- It does NOT override teacher constraints, prescribed periods, or pairing rules.
- It does NOT move sections that are already locked (co-schedule, pairing groups).
- It does NOT replace JC's judgment. The System Improvement Report presents findings; JC decides.
- It does NOT accumulate across many runs — only the MOST RECENT run's diagnostics are used (prevents stale data from biasing future runs).

---

## System Improvement Report (Console Output)

Printed after every Job 2 run. Every recommendation includes **full teacher background details** so the decision-maker can evaluate feasibility without looking up Template 6.

### Design Principle: Full Context With Every Recommendation

A recommendation like "move section to Period A — Saggio is free" is incomplete. The decision-maker needs to know:
- Is Saggio prescribed to teach this course? (Template 6)
- How many sections? What term types?
- What is Saggio's max load? Is he at cap?
- What ELSE does Saggio teach? (full course load)
- Is this a MOVE (relocating existing section) or an ADD (requiring extra period)?
- **What does Saggio's FULL SCHEDULE look like right now — and what does it become after the move?**

Without this context, the decision-maker cannot say yes or no. The report MUST provide it.

### Design Principle: Revised Schedule Preview

A feasibility assessment tells the decision-maker WHETHER a move is possible. But the decision-maker also needs to see the COMPLETE IMPACT — what the teacher's entire period-by-period schedule looks like before and after the change. A move from Period F to Period A might be "feasible" in isolation, but the decision-maker needs to see that Period A already has a co-scheduled pair, or that the move creates 3 consecutive teaching periods, or that it leaves a gap that could be used differently.

The **Revised Schedule Preview** shows:
1. **Current Schedule** — Periods A-G, S1 and S2 columns, every course the teacher is currently assigned to
2. **Revised Schedule** — The same grid after the recommended move is applied, with `◀ CHANGED` markers on affected periods

This lets the decision-maker compare before/after at a glance and catch side effects the engine's feasibility check cannot evaluate (consecutive period fatigue, preferred prep periods, departmental preferences, etc.).

### Format:

```
============================================================
SYSTEM IMPROVEMENT REPORT
============================================================

[CRITICAL] 710 World History — 70 conflicts, 86 spare seats
  Problem: Covers 4/7 periods (B,C,D,F); 510 Biology blocks 48 students
  Impact:  70 students cannot take World History (graduation required)
  Fix:     Move 1 section to Period A (from Period F) — Saggio, Jack is free.
           Est. reduction: 7 conflicts
  ── Teacher Details ──
    Saggio, Jack (ID: 117711):
      Max load: 5 periods | Using: 5 S1, 5 S2 | AT CAP
      Free periods: A,F
      Prescribed teaching load (Template 6):
        710 World History × 3 FY ◀ THIS COURSE
        723 Introduction to Political Science × 1 S1
        741 Psychology × 1 S1 + 1 S2
        751 American Government & Politics × 1 S1
      ⚠ FEASIBILITY: Saggio has Period A free BUT is at max load (5).
        This is a MOVE (not an add) — relocate existing section, no extra period needed.
      ── Current Schedule ──
        Period │ S1                                       │ S2
        ───────┼──────────────────────────────────────────┼──────────────────────────────────────────
          A    │ —                                        │ —
          B    │ 710 World History                        │ 710 World History
          C    │ 723 Introduction to Political Science    │ 741 Psychology
          D    │ 710 World History                        │ 710 World History
          E    │ 741 Psychology                           │ 751 American Government & Politics
          F    │ 710 World History                        │ 710 World History
          G    │ —                                        │ —
      ── Revised Schedule (if recommendation accepted) ──
        Period │ S1                                       │ S2
        ───────┼──────────────────────────────────────────┼──────────────────────────────────────────
          A    │ 710 World History                        │ 710 World History ◀ CHANGED
          B    │ 710 World History                        │ 710 World History
          C    │ 723 Introduction to Political Science    │ 741 Psychology
          D    │ 710 World History                        │ 710 World History
          E    │ 741 Psychology                           │ 751 American Government & Politics
          F    │ —                                        │ — ◀ CHANGED
          G    │ —                                        │ —
    Winters, Jack (ID: 105883):
      Max load: 5 periods | Using: 5 S1, 5 S2 | AT CAP
      Free periods: B
      Prescribed teaching load (Template 6):
        710 World History × 3 FY, prescribed room: I-012 ◀ THIS COURSE
        731 U.S. History II H × 3 FY
      ✓ FEASIBILITY: Not the recommended teacher for this move.
      ── Current Schedule ──
        Period │ S1                                       │ S2
        ───────┼──────────────────────────────────────────┼──────────────────────────────────────────
          A    │ 710 World History                        │ 710 World History
          B    │ —                                        │ —
          C    │ 731 U.S. History II H                    │ 731 U.S. History II H
          D    │ 710 World History                        │ 710 World History
          E    │ 731 U.S. History II H                    │ 731 U.S. History II H
          F    │ 710 World History                        │ 710 World History
          G    │ 731 U.S. History II H                    │ 731 U.S. History II H
      (No schedule change for this teacher under current recommendation)
  Action:  ENGINE CAN FIX — next run will bias toward better placement
  Decision: [ACTION NEEDED]

...
```

---

## Data Structure: run_diagnostics.json

```json
{
  "run_timestamp": "2026-08-05T14:30:00",
  "engine_mode": "full",
  "scenario_filter": "--grades 12",
  "total_conflicts": 228,
  "placement_rate": 85.5,
  "course_diagnostics": {
    "440": {
      "title": "Precalculus",
      "conflicts": 26,
      "periods_covered": ["A", "B", "D", "F", "G"],
      "periods_uncovered": ["C", "E"],
      "enrollment": 46,
      "capacity": 140,
      "spare_seats": 94,
      "top_blockers": [
        {"code": "851", "students_blocked": 26},
        {"code": "849", "students_blocked": 24},
        {"code": "140", "students_blocked": 17}
      ],
      "teacher_free_periods": {
        "DeLeon, Marco": ["B", "C", "E", "G"],
        "Gettler, Mary": ["C", "D", "E"]
      },
      "best_move": {
        "from_period": "D",
        "to_period": "C",
        "teacher": "DeLeon, Marco",
        "estimated_conflict_reduction": 12
      },
      "recommendation": "MOVE_SECTION",
      "severity": "CRITICAL"
    }
  },
  "period_hotspots": {
    "D": {
      "conflict_courses": ["849", "851", "546", "752", "758"],
      "total_conflicts_involving_D": 67,
      "recommendation": "REDISTRIBUTE"
    }
  },
  "blocking_chains": [
    {
      "chain": ["849/851 (A,B,D,F)", "440 (A,B,D,F,G)"],
      "students_affected": 26,
      "description": "Theology blocks 4/5 Precalculus periods"
    }
  ],
  "teacher_bottlenecks": {
    "Zawacki, Richard": {
      "sections": 6,
      "free_periods": ["G"],
      "courses_affected": ["752", "742", "732"],
      "total_conflicts": 37
    }
  }
}
```

---

## Implementation Plan

**Step 1:** Build Phase A-1 diagnostic analyzer (runs after Job 2)
- Reads actual conflict data from the completed run
- Computes all analyses above
- Writes `run_diagnostics.json`
- Prints System Improvement Report to console

**Step 2:** Build diagnostic loader in Phase A-0
- At engine startup, check for `run_diagnostics.json`
- If found, load and apply period bias adjustments to conflict scoring
- Print what adjustments were applied

**Step 3:** Adjust `_predict_conflict_score()` to incorporate biases
- Add a `_diagnostic_bias` dict that maps (course, period) → score adjustment
- Positive bias = avoid this period (prior run showed conflicts here)
- Negative bias = prefer this period (prior run showed this period would have helped)

**Step 4:** Add `run_diagnostics.json` to the engine's known files in CLAUDE.md

---

## What This Solves

| Current Problem | How This Fixes It |
|-----------------|-------------------|
| Engine places 752 in B,D every run — same 24 conflicts | Next run biases 752 toward G (Zawacki's free period) |
| Engine can't see theology→precalculus blocking chain | Blocking chain analysis identifies the pattern, biases 440 toward C,E |
| 590 Robotics: both sections in Period G | Coverage analysis flags 1/7 coverage, biases toward spreading |
| No visibility into WHY conflicts happen | System Improvement Report explains each conflict with actionable fixes |
| JC has to manually diagnose problems | Report presents diagnosis + recommendation — JC just decides yes/no |

---

## What This Does NOT Solve (Requires JC Decision)

1. **Teacher bottlenecks requiring new hires or reassignments** — e.g., Zawacki teaching all economics courses limits period flexibility. The report flags this but can't fix it.
2. **Section count decisions** — if a course needs a 3rd section to cover more periods, that's JC's call.
3. **Pairing group period selection** — theology occupying A,B,D,F is by design. If that needs to change, JC decides.
4. **Prescribed period overrides** — some sections are locked to specific periods in Template 6. The report flags when this causes conflicts but doesn't override.
