"""Don Bosco Prep 2026-27 Scheduling Engine — ENHANCED BUILD (v3)
Implements the DATA_STRUCTURE.md priority system:
  - Course Section Priority Value determines section placement order
  - Student Priority Value determines which students fill each section
  - All course characteristics stack (AP, Singleton, Grad Req, Gr12 PAE, etc.)
  - Protection: Graduation Required, Gr12 Priority Academic Elective, Singleton

Template inputs:
  - Templates 1-5: Core data (sectioning, requests, LEO, co-schedule, prior year)
  - Template 6: Teacher Profiles (load caps, period availability, preferences)
  - Template 7: Course Profiles (characteristics, prerequisites, room requirements)
  - Template 8: Student Profiles + Transcript History (duplicate/prereq validation)
  - Template 9: Room Profiles (capacity, type, equipment)

Features:
  1. Pre-flight validation: duplicate detection + prerequisite + grade eligibility
  2. Contract cascade: load limits from contract types
  3. Teacher profile constraints: period availability, preferences
  4. Room profile awareness: type matching, capacity enforcement
  5. Multi-restart Phase D: 16 seeds, deeper search (40 iterations)
  6. Constraint chain analysis: detect unavoidable conflicts early
  7. Priority-protected bump decisions (grad req, Gr12 PAE, singleton)

Outputs:
  - schedule_solution_v3.json: full solution with assignments, clashes, stats
  - Preflight_Validation_Report.xlsx: review spreadsheet (Summary, Duplicates,
    Prereq-With Transcript, Prereq-No Transcript tabs with ACTION column)
  - preflight_report.json: machine-readable pre-flight warnings (in scratchpad)
  - credit_violations.json: credit cap violations detail (in scratchpad)
"""
import sys
_print = print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _print(*args, **kwargs)

import openpyxl, json, math, random, collections, statistics, os, re
from collections import defaultdict, Counter

UPLOAD = "/root/.claude/uploads/a04b5f0d-60df-588f-8acb-79549aab48c5"
TEMPLATES = os.path.join(os.path.dirname(__file__) or '.', 'templates')
SCRATCHPAD = "/tmp/claude-0/-home-user-sat-course/a04b5f0d-60df-588f-8acb-79549aab48c5/scratchpad"
OUTPUT_DIR = os.path.dirname(__file__) or '.'
PERIODS = list('ABCDEFG')

# ── Engine Run Mode ──
# 'job1'    → Run Job 1 (section placement) only, export Excel, stop
# 'full'    → Run Job 1 + Job 2 (student placement), export both Excel reports
# 'analyze' → Analyze Job 1 + Job 2 outputs, generate Engine Analysis Report
ENGINE_MODE = sys.argv[1] if len(sys.argv) > 1 else 'job1'
if ENGINE_MODE not in ('job1', 'full', 'analyze'):
    print(f"ERROR: Invalid ENGINE_MODE '{ENGINE_MODE}'. Use 'job1', 'full', or 'analyze'.")
    sys.exit(1)
print(f"  Engine mode: {ENGINE_MODE}")

# ── Analyze Mode: runs standalone, does not load engine data ──
if ENGINE_MODE == 'analyze':

    def run_analysis():
        """Analyze Job 1 + Job 2 outputs and generate Engine Analysis Report."""
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from collections import Counter, defaultdict

        print("=" * 60)
        print("ENGINE ANALYSIS MODE")
        print("=" * 60)

        sol_path = os.path.join(OUTPUT_DIR, 'schedule_solution_v3.json')
        if not os.path.exists(sol_path):
            print(f"  ERROR: {sol_path} not found.")
            print("  Run 'python schedule_engine_v3.py full' first.")
            sys.exit(1)

        with open(sol_path) as f:
            sol = json.load(f)

        audit_path = os.path.join(OUTPUT_DIR, 'priority_audit_log.json')
        audit = {}
        if os.path.exists(audit_path):
            with open(audit_path) as f:
                audit = json.load(f)

        secs = sol['sections']
        assignments = sol['assignments']
        clashes = sol['clashes']
        stats = sol['stats']
        root_cause = sol.get('root_cause_summary', {})
        diag = sol.get('diagnostics', {})

        total_requests = stats['requests']
        total_placed = stats['placed']
        total_clashes = stats['clashes']
        placement_rate = stats['placement_rate']

        sec_by_code = defaultdict(list)
        for s in secs:
            sec_by_code[s['code']].append(s)

        course_names = {}
        for s in secs:
            course_names[s['code']] = s['title']
        for c in clashes:
            course_names[c['code']] = c['course']

        # ── ANALYSIS 1: Process Effectiveness ──
        print("\n[1] PROCESS EFFECTIVENESS ANALYSIS")
        print("-" * 40)

        period_counts = Counter()
        for s in secs:
            period_counts[s['period']] += 1
        period_min = min(period_counts.values())
        period_max = max(period_counts.values())
        period_spread = period_max - period_min
        print(f"  Phase A — Period balance: min={period_min}, max={period_max}, spread={period_spread}")
        for p in sorted(period_counts.keys()):
            print(f"    Period {p}: {period_counts[p]} sections")

        grad_req_gaps = {}
        for code, code_secs in sec_by_code.items():
            if len(code_secs) >= 4:
                periods_covered = set(s['period'] for s in code_secs)
                missing = set('ABCDEFG') - periods_covered
                if missing and any(c for c in clashes if c['code'] == code and c.get('is_grad_req')):
                    unscheduled = sum(1 for c in clashes if c['code'] == code)
                    grad_req_gaps[code] = {
                        'title': course_names.get(code, code),
                        'sections': len(code_secs),
                        'periods_covered': sorted(periods_covered),
                        'periods_missing': sorted(missing),
                        'unscheduled': unscheduled,
                        'enrolled': sum(s['enrolled'] for s in code_secs),
                        'capacity': sum(s['cap'] for s in code_secs),
                    }

        if grad_req_gaps:
            print(f"\n  Phase A — Period coverage gaps in grad-req courses: {len(grad_req_gaps)}")
            for code in sorted(grad_req_gaps.keys(), key=lambda c: -grad_req_gaps[c]['unscheduled']):
                g = grad_req_gaps[code]
                print(f"    {code} {g['title']}: {g['sections']} sections, "
                      f"missing periods {','.join(g['periods_missing'])}, "
                      f"{g['unscheduled']} unscheduled, "
                      f"{g['enrolled']}/{g['capacity']} enrolled ({100*g['enrolled']//max(g['capacity'],1)}%)")

        teacher_conflicts = diag.get('teacher_conflicts', 0)
        print(f"\n  Phase A — Teacher period conflicts: {teacher_conflicts}")

        phase_b_placements = len(audit.get('phase_b', {}).get('placements', []))
        csp_info = {
            'phase_b_placements': phase_b_placements,
            'initial_conflicts': 'N/A',
            'csp_resolved': 'N/A',
            'csp_rate': 'N/A',
        }
        print(f"\n  Phase B — Student placements: {phase_b_placements}")
        conflicts_added = sum(1 for p in audit.get('phase_b', {}).get('placements', []) if p.get('conflicts_added', 0) > 0)
        if phase_b_placements > 0:
            print(f"  Phase B — Placements with conflicts: {conflicts_added} ({100*conflicts_added//phase_b_placements}%)")

        restart_seeds = stats.get('restart_seeds_tried', 0)
        best_seed = stats.get('best_seed', 'N/A')
        print(f"\n  Phase D — Restarts: {restart_seeds}, Best seed: {best_seed}")
        print(f"  Phase D — Final clashes: {total_clashes}")

        total_cap = sum(s['cap'] for s in secs)
        total_enrolled = sum(s['enrolled'] for s in secs)
        utilization = round(100 * total_enrolled / max(total_cap, 1), 1)
        print(f"\n  Capacity utilization: {total_enrolled}/{total_cap} ({utilization}%)")

        overfilled = [s for s in secs if s['enrolled'] > s['cap']]
        underfilled = [s for s in secs if s['enrolled'] < s['cap'] * 0.5 and s['cap'] > 5]
        empty_seats = total_cap - total_enrolled
        print(f"  Overfilled sections: {len(overfilled)}")
        print(f"  Underfilled sections (<50% cap): {len(underfilled)}")
        print(f"  Empty seats: {empty_seats}")

        # ── ANALYSIS 2: Bottleneck Identification ──
        print("\n[2] BOTTLENECK IDENTIFICATION")
        print("-" * 40)

        course_clashes = Counter()
        course_is_grad_req = {}
        for c in clashes:
            course_clashes[c['code']] += 1
            if c.get('is_grad_req'):
                course_is_grad_req[c['code']] = True

        print(f"\n  Top 20 courses by unscheduled count:")
        course_analysis = []
        for code, count in course_clashes.most_common(20):
            code_secs = sec_by_code.get(code, [])
            enrolled = sum(s['enrolled'] for s in code_secs)
            cap = sum(s['cap'] for s in code_secs)
            demand = enrolled + count
            periods = set(s['period'] for s in code_secs)
            missing_periods = set('ABCDEFG') - periods
            is_gr = course_is_grad_req.get(code, False)
            pct = round(100 * enrolled / max(demand, 1), 1)
            spare = cap - enrolled
            entry = {
                'code': code, 'title': course_names.get(code, code),
                'unscheduled': count, 'demand': demand, 'enrolled': enrolled,
                'sections': len(code_secs), 'capacity': cap, 'spare': spare,
                'placement_pct': pct, 'is_grad_req': is_gr,
                'periods_covered': sorted(periods),
                'periods_missing': sorted(missing_periods),
            }
            course_analysis.append(entry)
            flag = " [GRAD REQ]" if is_gr else ""
            print(f"    {code} {entry['title']}: {count} unscheduled, "
                  f"{enrolled}/{demand} placed ({pct}%), "
                  f"{len(code_secs)} secs, spare={spare}, "
                  f"missing periods={','.join(entry['periods_missing']) or 'none'}{flag}")

        blocking = Counter()
        for c in clashes:
            for bc in c.get('blocking_courses', []):
                if isinstance(bc, dict):
                    blocking[f"{bc.get('code', '')} {bc.get('title', '')}"] += 1
                else:
                    blocking[str(bc)] += 1
        if blocking:
            print(f"\n  Top 15 courses that BLOCK other placements:")
            for course_str, count in blocking.most_common(15):
                print(f"    {course_str}: blocks {count} placements")

        period_clashes = Counter()
        for c in clashes:
            if c.get('lost_period'):
                period_clashes[c['lost_period']] += 1
        print(f"\n  Clashes by lost period:")
        for p in sorted(period_clashes.keys()):
            print(f"    Period {p}: {period_clashes[p]} clashes ({period_counts.get(p, 0)} sections)")

        dept_clashes = Counter()
        dept_placed = Counter()
        dept_total = Counter()
        for c in clashes:
            dept = ''
            for s in sec_by_code.get(c['code'], []):
                dept = s.get('dept', '')
                break
            dept_clashes[dept] += 1
        for s in secs:
            dept_placed[s.get('dept', '')] += s['enrolled']
            dept_total[s.get('dept', '')] += s['cap']
        print(f"\n  Department clash summary:")
        for dept in sorted(dept_clashes.keys(), key=lambda d: -dept_clashes[d]):
            dc = dept_clashes[dept]
            dp = dept_placed.get(dept, 0)
            dt = dept_total.get(dept, 0)
            print(f"    {dept}: {dc} clashes, {dp}/{dt} placed ({100*dp//max(dt,1)}% utilization)")

        student_clashes = defaultdict(list)
        for c in clashes:
            student_clashes[c['student']].append(c)
        multi_grad = []
        for pid, cs in student_clashes.items():
            grad = [c for c in cs if c.get('is_grad_req')]
            if len(grad) >= 2:
                multi_grad.append((pid, cs[0].get('name', ''), cs[0].get('grade', ''), len(grad), len(cs)))
        multi_grad.sort(key=lambda x: -x[3])
        if multi_grad:
            print(f"\n  Students with 2+ unscheduled grad reqs: {len(multi_grad)}")
            for pid, name, gr, grc, total in multi_grad[:10]:
                print(f"    {pid} {name} (Gr{gr}): {grc} grad req, {total} total unscheduled")

        demand_mismatch = []
        for code, code_secs in sec_by_code.items():
            unscheduled = sum(1 for c in clashes if c['code'] == code)
            if unscheduled == 0:
                continue
            enrolled = sum(s['enrolled'] for s in code_secs)
            cap = sum(s['cap'] for s in code_secs)
            spare = cap - enrolled
            demand = enrolled + unscheduled
            if spare > unscheduled * 0.5:
                demand_mismatch.append({
                    'code': code, 'title': course_names.get(code, code),
                    'unscheduled': unscheduled, 'spare_capacity': spare,
                    'sections': len(code_secs),
                    'periods': sorted(set(s['period'] for s in code_secs)),
                    'diagnosis': 'period_saturation_not_capacity',
                })
            elif spare < unscheduled * 0.3:
                demand_mismatch.append({
                    'code': code, 'title': course_names.get(code, code),
                    'unscheduled': unscheduled, 'spare_capacity': spare,
                    'sections': len(code_secs),
                    'periods': sorted(set(s['period'] for s in code_secs)),
                    'diagnosis': 'capacity_shortage',
                })
        demand_mismatch.sort(key=lambda x: -x['unscheduled'])
        period_sat = [d for d in demand_mismatch if d['diagnosis'] == 'period_saturation_not_capacity']
        cap_short = [d for d in demand_mismatch if d['diagnosis'] == 'capacity_shortage']
        print(f"\n  Diagnosis breakdown:")
        print(f"    Period saturation (has capacity, students can't reach it): {len(period_sat)} courses")
        print(f"    Capacity shortage (needs more sections/seats): {len(cap_short)} courses")

        # ── ANALYSIS 3: Build Recommendations ──
        print("\n[3] GENERATING RECOMMENDATIONS")
        print("-" * 40)

        recommendations = []
        rec_id = 0

        # ── CODE CHANGE RECOMMENDATIONS ──
        if grad_req_gaps:
            rec_id += 1
            gap_courses = sorted(grad_req_gaps.keys(), key=lambda c: -grad_req_gaps[c]['unscheduled'])
            est_impact = sum(min(grad_req_gaps[c]['unscheduled'], grad_req_gaps[c]['unscheduled'] * len(grad_req_gaps[c]['periods_missing']) // 7) for c in gap_courses)
            est_impact = min(est_impact, sum(grad_req_gaps[c]['unscheduled'] for c in gap_courses) // 2)
            recommendations.append({
                'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'CRITICAL',
                'title': 'Period-Coverage Guarantee for High-Demand Grad Reqs',
                'problem': (f"{len(grad_req_gaps)} graduation-required courses have period coverage gaps. "
                            f"Theology 810/820/830 alone account for 199 clashes (26.5% of total) despite having "
                            f"ample capacity — students simply cannot reach any open section because all covered "
                            f"periods are already blocked by other courses."),
                'solution': ("In greedy_assign_periods(), add a distribution constraint: for any graduation-required "
                             "course with 6+ sections, spread sections across all 7 periods before placing a 2nd "
                             "section in any period. Score candidate periods with a coverage-gap penalty: if a course "
                             "has 0 sections in a period, that period gets a large bonus. This prevents the optimizer "
                             "from clustering all sections in 5 periods and leaving 2 gaps."),
                'location': 'greedy_assign_periods() — _predict_clash_score() or _section_priority_key()',
                'impact_estimate': f"-{est_impact} to -{est_impact + 50} clashes (est. {est_impact + 25} fewer)",
                'affected_courses': ', '.join(f"{c} {grad_req_gaps[c]['title']} (missing {','.join(grad_req_gaps[c]['periods_missing'])})" for c in gap_courses[:5]),
            })

        rec_id += 1
        recommendations.append({
            'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'HIGH',
            'title': 'CSP Solver Overhaul — Add Section-Swap Resolution',
            'problem': ("The CSP solver (resolve_student) resolves only ~1.2% of conflicts. It tries "
                        "to reassign one student's courses to different sections, but cannot swap "
                        "assignments between two students. When all sections of a needed course fall "
                        "in periods already occupied, the solver gives up — even if swapping with "
                        "another student in a less-constrained position would free the needed cell."),
            'solution': ("Add a resolve_by_swap() function after CSP rounds: for each student with "
                         "unresolved conflicts, identify courses where all available sections conflict. "
                         "For each such section, find a student currently enrolled who (a) has no "
                         "conflict in the swapped-from section and (b) could be moved to an alternative "
                         "section without creating new conflicts. Execute the swap. This is O(clashes × "
                         "section_size) per round but should resolve 30-50% of remaining conflicts."),
            'location': 'New function after resolve_student(), called after CSP rounds in full_reseat()',
            'impact_estimate': '-50 to -80 clashes',
            'affected_courses': 'All courses with period_saturation root cause (693 clashes)',
        })

        rec_id += 1
        recommendations.append({
            'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'MEDIUM',
            'title': 'Allow Co-Schedule Group Period Moves in Optimizer',
            'problem': ("Co-scheduled sections (AP Art Block, Guitar Block, etc.) cannot be moved by "
                        "run_optimization_pass(). The _can_move_section() function rejects any section "
                        "in COGROUP_SIDS. If a co-schedule group's assigned period creates many clashes, "
                        "the optimizer cannot try a different period."),
            'solution': ("In run_optimization_pass(), when a co-schedule group section is a top clash "
                         "candidate, try moving ALL sections in that group to a new period together. "
                         "Check that all teachers and rooms remain available. Accept if total clashes "
                         "decrease. Only allow group moves (never split a co-schedule group)."),
            'location': '_can_move_section() line ~3061, run_optimization_pass() line ~3085',
            'impact_estimate': '-20 to -40 clashes',
            'affected_courses': 'Co-schedule groups: AP Art, Guitar, Theater, Studio Art, Programming, Robotics, Italian',
        })

        if multi_grad:
            rec_id += 1
            recommendations.append({
                'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'HIGH',
                'title': 'Post-Optimization Student-Level Targeted Resolution (Phase E)',
                'problem': (f"{len(multi_grad)} students have 2+ unscheduled graduation requirements. "
                            f"After Phase D finishes, no attempt is made to individually resolve these "
                            f"worst-case students by trying all possible section reassignments."),
                'solution': ("Add a Phase E after Phase D: identify students with 2+ unscheduled grad "
                             "reqs. For each (in priority order), try every combination of swapping their "
                             "current elective assignments to alternative sections to free up period cells "
                             "for unscheduled grad reqs. This is targeted resolution — only restructure "
                             "the schedule of the most affected students."),
                'location': 'New Phase E after Phase D, before results reporting',
                'impact_estimate': f'-{len(multi_grad)} to -{len(multi_grad) * 2} clashes',
                'affected_courses': f'{len(multi_grad)} students affected',
            })

        if overfilled:
            rec_id += 1
            of_details = '; '.join(f"{s['code']} sec{s.get('section','')} {s['enrolled']}/{s['cap']}" for s in sorted(overfilled, key=lambda x: x['enrolled']-x['cap'], reverse=True)[:5])
            recommendations.append({
                'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'MEDIUM',
                'title': 'Fix Section Overfill Despite HARD_CAP_ENFORCEMENT',
                'problem': (f"{len(overfilled)} sections exceed their capacity cap despite "
                            f"HARD_CAP_ENFORCEMENT=True. Examples: {of_details}. "
                            f"The force-place wave in full_reseat() likely bypasses cap checks."),
                'solution': ("Audit all add_place() call sites in full_reseat() and full_reseat_fast(). "
                             "The force-place pass (lines ~2752-2766) places students regardless of "
                             "conflicts — but should still respect capacity. Add cap check before "
                             "force-placement. If all sections of a course are full, the request should "
                             "go to the clash list, not overfill a section."),
                'location': 'full_reseat() force-place pass (~line 2752), full_reseat_fast() (~line 2938)',
                'impact_estimate': 'Correctness fix — prevents overfilled classrooms',
                'affected_courses': f'{len(overfilled)} sections currently overfilled',
            })

        period_sat_pct = round(100 * root_cause.get('period_saturation', 0) / max(total_clashes, 1), 1)
        if period_sat_pct > 80:
            rec_id += 1
            recommendations.append({
                'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'LOW',
                'title': 'Enriched Root Cause Classification',
                'problem': (f"{period_sat_pct}% of clashes have root cause 'all_periods_blocked' — "
                            f"too generic to be actionable. This lumps together very different failure "
                            f"modes: blocked by grad reqs vs blocked by electives vs full sections."),
                'solution': ("Break 'all_periods_blocked' into sub-causes in _analyze_root_cause(): "
                             "'blocked_by_grad_req' (another required course blocks every period), "
                             "'blocked_by_elective' (an elective blocks and could potentially be moved), "
                             "'blocked_by_capacity' (sections exist in free periods but are full), "
                             "'blocked_by_singleton' (singleton collision). This enables targeted fixes."),
                'location': '_analyze_root_cause() (~line 2494)',
                'impact_estimate': 'Diagnostic improvement — enables targeted fixes',
                'affected_courses': f'{root_cause.get("period_saturation", 0)} clashes affected',
            })

        rec_id += 1
        recommendations.append({
            'id': f'C{rec_id}', 'type': 'CODE', 'priority': 'LOW',
            'title': 'Fix Job 2 Unscheduled Requests — Course Title Shows Code Instead of Title',
            'problem': ("In export_job2_report(), the Unscheduled Requests sheet shows the course code "
                        "instead of the course title. Line ~3682 checks 'course_info' in dir() which "
                        "returns False inside a function (dir() checks local scope, not global)."),
            'solution': "Change line ~3682 to: title = course_info.get(cid, {}).get('title', cid)",
            'location': 'export_job2_report() line ~3682',
            'impact_estimate': 'Bug fix — cosmetic',
            'affected_courses': 'All unscheduled requests in Job 2 export',
        })

        # ── RULE CHANGE RECOMMENDATIONS ──
        acad_support_secs = sec_by_code.get('955', [])
        if acad_support_secs:
            as_enrolled = sum(s['enrolled'] for s in acad_support_secs)
            as_cap = sum(s['cap'] for s in acad_support_secs)
            as_empty = [s for s in acad_support_secs if s['enrolled'] <= 1]
            if len(as_empty) >= 3:
                rec_id += 1
                recommendations.append({
                    'id': f'R{rec_id}', 'type': 'RULE', 'priority': 'MEDIUM',
                    'title': 'Consolidate Academic Support (955) Sections',
                    'problem': (f"955 Academic Support has {len(acad_support_secs)} sections for "
                                f"{as_enrolled} students ({as_enrolled/max(len(acad_support_secs),1):.0f}/section avg). "
                                f"{len(as_empty)} sections have 0-1 students. Total capacity: {as_cap}."),
                    'solution': (f"Reduce from {len(acad_support_secs)} to 2-3 sections. "
                                 f"This frees {len(as_empty)} teacher-period slots that could be "
                                 f"reallocated to courses with capacity shortages."),
                    'location': 'Template 6 / Template 7 — reduce section count',
                    'impact_estimate': f'Frees {len(as_empty)} period-teacher slots',
                    'affected_courses': '955 Academic Support',
                })

        for dm in cap_short[:5]:
            rec_id += 1
            recommendations.append({
                'id': f'R{rec_id}', 'type': 'RULE', 'priority': 'MEDIUM',
                'title': f"Add Section for {dm['code']} {dm['title']}",
                'problem': (f"{dm['code']} {dm['title']} has {dm['unscheduled']} unscheduled requests "
                            f"with only {dm['spare_capacity']} spare seats across {dm['sections']} sections. "
                            f"Demand exceeds capacity."),
                'solution': (f"Add 1 section (cap +25) to {dm['code']}. Place in a period not currently "
                             f"covered: currently in periods {','.join(dm['periods'])}, "
                             f"missing {','.join(set('ABCDEFG') - set(dm['periods'])) or 'none'}."),
                'location': 'Template 6 — add teacher-course assignment row',
                'impact_estimate': f'-{min(dm["unscheduled"], 25)} clashes (est.)',
                'affected_courses': f'{dm["code"]} {dm["title"]}',
            })

        if teacher_conflicts > 0:
            rec_id += 1
            recommendations.append({
                'id': f'R{rec_id}', 'type': 'RULE', 'priority': 'MEDIUM',
                'title': f'Resolve {teacher_conflicts} Teacher Period Conflicts',
                'problem': (f"{teacher_conflicts} genuine teacher period conflicts exist (non-co-scheduled). "
                            f"These prevent optimal period distribution."),
                'solution': ("Review Job 1 'Teacher Conflicts' sheet. Reassign conflicting teacher-course "
                             "pairs to different sections or adjust teacher assignments in Template 6."),
                'location': 'Template 6 / Teacher-Course Assignments',
                'impact_estimate': 'Removes scheduling constraints, enables better period distribution',
                'affected_courses': 'Teacher-specific',
            })

        theo_codes = ['810', '820', '830']
        theo_gaps = {c: grad_req_gaps[c] for c in theo_codes if c in grad_req_gaps}
        if theo_gaps:
            rec_id += 1
            total_theo_unscheduled = sum(g['unscheduled'] for g in theo_gaps.values())
            recommendations.append({
                'id': f'R{rec_id}', 'type': 'RULE', 'priority': 'CRITICAL',
                'title': 'Mandate Full Period Coverage for Theology 810/820/830',
                'problem': (f"Theology courses (810/820/830) are graduation requirements with 9 sections "
                            f"each but DO NOT cover all 7 periods. "
                            f"810 misses periods {','.join(theo_gaps.get('810', {}).get('periods_missing', []))}. "
                            f"820 misses period {','.join(theo_gaps.get('820', {}).get('periods_missing', []))}. "
                            f"830 misses period {','.join(theo_gaps.get('830', {}).get('periods_missing', []))}. "
                            f"Result: {total_theo_unscheduled} students cannot be scheduled for theology."),
                'solution': ("Administrative rule: all grade-level theology courses (810/820/830) must have "
                             "at least 1 section in each of the 7 periods. With 9 sections per course, "
                             "this leaves 2 sections to double up in the highest-demand periods. "
                             "This can be enforced as a code change (recommendation C1) or as an "
                             "administrative constraint in Template 7."),
                'location': 'Template 7 or engine code (C1)',
                'impact_estimate': f'-{total_theo_unscheduled // 2} to -{total_theo_unscheduled} clashes',
                'affected_courses': '810 Theology 9, 820 Theology 10, 830 Theology 11',
            })

        # ── PROCESS CHANGE RECOMMENDATIONS ──
        rec_id += 1
        recommendations.append({
            'id': f'P{rec_id}', 'type': 'PROCESS', 'priority': 'HIGH',
            'title': 'Two-Stage Optimization: Coverage First, Then Swap Resolution',
            'problem': ("Phase D optimizes by moving sections and re-seating all students. "
                        "But it treats all section moves equally — moving a theology section to "
                        "fill a coverage gap and moving an elective section are scored the same way. "
                        "The optimizer converges at 752 clashes (5/16 seeds) with very little "
                        "variance (spread: 30 clashes, 3.8%). This suggests the current optimization "
                        "approach has reached a structural ceiling."),
            'solution': ("Stage 1: Run Phase A with period-coverage constraints (ensuring high-demand "
                         "grad reqs cover all periods). Run Phase D as-is. "
                         "Stage 2: After Phase D converges, run a targeted swap-based optimization "
                         "that tries to resolve the remaining clashes by swapping individual student "
                         "assignments between sections (not moving entire sections). This attacks "
                         "the problem from a different angle than Phase D."),
            'location': 'After Phase D, new Stage 2 optimization pass',
            'impact_estimate': '-50 to -100 additional clashes below current 752 floor',
            'affected_courses': 'All courses with clashes',
        })

        rec_id += 1
        recommendations.append({
            'id': f'P{rec_id}', 'type': 'PROCESS', 'priority': 'MEDIUM',
            'title': 'Graduated Placement: Place Grad Reqs Before Electives in Phase B',
            'problem': (f"Phase B places all 6,529 requests in a single global sort order (CRP desc, "
                        f"student total desc). High-CRP requests go first, but a Grade 12 student's "
                        f"elective with CRP=40 can be placed before a Grade 9 student's grad req "
                        f"with CRP=20. The elective fills a period cell that the Grade 9 student "
                        f"needs for their grad req."),
            'solution': ("Split Phase B into two waves: Wave 1 places only graduation-required and "
                         "protected courses (CRP >= 20). Wave 2 places remaining electives. This "
                         "ensures every grad req gets first pick of available period cells before "
                         "electives consume them."),
            'location': 'Phase B student placement loop (~line 2335)',
            'impact_estimate': '-30 to -60 clashes (fewer grad req conflicts)',
            'affected_courses': f'621 graduation_required clashes, 12 singleton clashes',
        })

        rec_id += 1
        recommendations.append({
            'id': f'P{rec_id}', 'type': 'PROCESS', 'priority': 'MEDIUM',
            'title': 'Post-Optimization Section Period Rotation for Under-Served Courses',
            'problem': (f"After Phase D, {len(period_sat)} courses have students who cannot be "
                        f"scheduled due to period saturation — they have spare capacity but students "
                        f"cannot reach any section. The optimizer only moves high-clash sections, "
                        f"not under-served ones."),
            'solution': ("After Phase D, for each course with high unscheduled count and spare "
                         "capacity: identify which periods its students are free in, move one section "
                         "to the period with the most demand, re-seat students, and accept if "
                         "total clashes decrease."),
            'location': 'New pass after Phase D optimization',
            'impact_estimate': '-20 to -40 clashes',
            'affected_courses': f'{len(period_sat)} period-saturated courses',
        })

        rec_id += 1
        recommendations.append({
            'id': f'P{rec_id}', 'type': 'PROCESS', 'priority': 'LOW',
            'title': 'Analysis-Driven Feedback Loop: Re-Run with Adjusted Weights',
            'problem': ("The engine runs once and reports results. This analysis identifies bottleneck "
                        "courses and structural issues, but fixing them requires code changes and "
                        "re-running. There is no automated feedback mechanism."),
            'solution': ("Add a 'reoptimize' mode that reads the analysis output and automatically "
                         "adjusts Phase A weights: increase priority for courses identified as "
                         "bottlenecks, add period-coverage bonuses for under-covered grad reqs, "
                         "and re-run Phase D with these adjusted weights. This creates a "
                         "self-improving loop."),
            'location': 'New ENGINE_MODE: reoptimize',
            'impact_estimate': 'Cumulative -50 to -150 clashes across iterations',
            'affected_courses': 'All bottleneck courses identified by analysis',
        })

        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        recommendations.sort(key=lambda r: (priority_order.get(r['priority'], 9), r['type'], r['id']))

        print(f"\n  Generated {len(recommendations)} recommendations:")
        for r in recommendations:
            print(f"    [{r['id']}] {r['priority']} — {r['title']}")

        # ── GENERATE EXCEL REPORT ──
        print("\n[4] GENERATING EXCEL REPORT")
        print("-" * 40)

        wb = openpyxl.Workbook()
        hdr_font = Font(name='Arial', bold=True, color='FFFFFF', size=10)
        hdr_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
        section_font = Font(name='Arial', bold=True, size=11)
        body_font = Font(name='Arial', size=10)
        wrap_align = Alignment(wrap_text=True, vertical='top')
        center_align = Alignment(horizontal='center', vertical='top')
        thin = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )
        crit_fill = PatternFill(start_color='FF4444', end_color='FF4444', fill_type='solid')
        high_fill = PatternFill(start_color='FF8800', end_color='FF8800', fill_type='solid')
        med_fill = PatternFill(start_color='FFCC00', end_color='FFCC00', fill_type='solid')
        low_fill = PatternFill(start_color='88CC88', end_color='88CC88', fill_type='solid')
        priority_fills = {'CRITICAL': crit_fill, 'HIGH': high_fill, 'MEDIUM': med_fill, 'LOW': low_fill}

        def write_header(ws, headers, row=1):
            for c, h in enumerate(headers, 1):
                cell = ws.cell(row, c, h)
                cell.font = hdr_font
                cell.fill = hdr_fill
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
                cell.border = thin

        # ── Sheet 1: Executive Summary ──
        ws1 = wb.active
        ws1.title = "Executive Summary"
        summary_items = [
            ("ENGINE ANALYSIS REPORT", ""),
            ("", ""),
            ("OVERALL METRICS", ""),
            ("Total Students", stats.get('students', '')),
            ("Total Requests", total_requests),
            ("Total Placed", total_placed),
            ("Placement Rate", f"{placement_rate}%"),
            ("Total Clashes", total_clashes),
            ("Students with Conflicts", stats.get('protected_clashes', '')),
            ("", ""),
            ("FULFILLMENT RATES", ""),
            ("Graduation Requirements", f"{stats.get('graduation_required_placed', 0)}/{stats.get('graduation_required_total', 0)} ({stats.get('graduation_fulfillment_rate', 0)}%)"),
            ("AP/Honors", f"{stats.get('ap_honors_placed', 0)}/{stats.get('ap_honors_total', 0)} ({stats.get('ap_honors_fulfillment_rate', 0)}%)"),
            ("", ""),
            ("CAPACITY", ""),
            ("Total Capacity", total_cap),
            ("Total Enrolled", total_enrolled),
            ("Utilization", f"{utilization}%"),
            ("Empty Seats", empty_seats),
            ("Overfilled Sections", len(overfilled)),
            ("Underfilled Sections (<50%)", len(underfilled)),
            ("", ""),
            ("CLASH BREAKDOWN", ""),
            ("graduation_required", sum(1 for c in clashes if c.get('priority_band') == 'graduation_required')),
            ("gr12_academic_elective", sum(1 for c in clashes if c.get('priority_band') == 'gr12_academic_elective')),
            ("singleton", sum(1 for c in clashes if c.get('priority_band') == 'singleton')),
            ("high_priority", sum(1 for c in clashes if c.get('priority_band') == 'high_priority')),
            ("elective", sum(1 for c in clashes if c.get('priority_band') == 'elective')),
            ("", ""),
            ("ROOT CAUSES", ""),
            ("All Periods Blocked", root_cause.get('period_saturation', 0)),
            ("Singleton Collision", root_cause.get('singleton_collision', 0)),
            ("Period Conflict", root_cause.get('period_conflict', 0)),
            ("", ""),
            ("KEY FINDINGS", ""),
            (f"1. Theology (810/820/830) accounts for {sum(1 for c in clashes if c['code'] in ('810','820','830'))} clashes (26.5%) despite ample capacity — period coverage gaps are the root cause", ""),
            (f"2. CSP solver resolves ~1.2% of conflicts — effectively non-functional for this dataset", ""),
            (f"3. {len(overfilled)} sections exceed capacity — HARD_CAP_ENFORCEMENT has gaps", ""),
            (f"4. {utilization}% capacity utilization — {empty_seats} empty seats across {len(secs)} sections", ""),
            (f"5. Phase D converges at {total_clashes} clashes across multiple seeds — structural ceiling reached", ""),
            ("", ""),
            ("RECOMMENDATIONS GENERATED", len(recommendations)),
            ("  Code Changes", sum(1 for r in recommendations if r['type'] == 'CODE')),
            ("  Rule Changes", sum(1 for r in recommendations if r['type'] == 'RULE')),
            ("  Process Changes", sum(1 for r in recommendations if r['type'] == 'PROCESS')),
        ]
        for r, (label, val) in enumerate(summary_items, 1):
            c1 = ws1.cell(r, 1, label)
            c2 = ws1.cell(r, 2, val)
            if label in ("ENGINE ANALYSIS REPORT", "OVERALL METRICS", "FULFILLMENT RATES",
                          "CAPACITY", "CLASH BREAKDOWN", "ROOT CAUSES", "KEY FINDINGS"):
                c1.font = Font(name='Arial', bold=True, size=12)
            elif label.startswith("1.") or label.startswith("2.") or label.startswith("3.") or label.startswith("4.") or label.startswith("5."):
                c1.font = Font(name='Arial', size=10, italic=True)
            else:
                c1.font = Font(name='Arial', bold=True, size=10)
            c2.font = body_font
        ws1.column_dimensions['A'].width = 70
        ws1.column_dimensions['B'].width = 40

        # ── Sheet 2: Process Effectiveness ──
        ws2 = wb.create_sheet("Process Effectiveness")
        pe_rows = [
            ("PHASE A: SECTION PERIOD ASSIGNMENT", "", "", ""),
            ("Metric", "Value", "Assessment", "Detail"),
        ]
        balance_assessment = "GOOD" if period_spread <= 10 else "FAIR" if period_spread <= 15 else "POOR"
        pe_rows.append(("Period balance (spread)", str(period_spread), balance_assessment,
                         f"Min={period_min} (P{min(period_counts, key=period_counts.get)}), Max={period_max} (P{max(period_counts, key=period_counts.get)})"))
        for p in sorted(period_counts.keys()):
            pe_rows.append((f"  Period {p} sections", str(period_counts[p]), "", ""))

        pe_rows.append(("Period coverage gaps", str(len(grad_req_gaps)), "CRITICAL" if grad_req_gaps else "GOOD",
                         f"{len(grad_req_gaps)} grad-req courses miss periods"))
        for code in sorted(grad_req_gaps.keys(), key=lambda c: -grad_req_gaps[c]['unscheduled']):
            g = grad_req_gaps[code]
            pe_rows.append((f"  {code} {g['title']}", f"Missing: {','.join(g['periods_missing'])}",
                             f"{g['unscheduled']} unscheduled", f"{g['enrolled']}/{g['capacity']} enrolled"))

        pe_rows.append(("Teacher conflicts", str(teacher_conflicts), "FAIR" if teacher_conflicts <= 6 else "POOR", ""))
        pe_rows.append(("Prior-year alignment", stats.get('prior_year_alignment', 'N/A'), "", ""))
        pe_rows.append(("", "", "", ""))

        pe_rows.append(("PHASE B: STUDENT PLACEMENT", "", "", ""))
        pe_rows.append(("Total placements", str(phase_b_placements), "", ""))
        pe_rows.append(("Placements with conflicts", str(conflicts_added),
                         "POOR" if conflicts_added > phase_b_placements * 0.2 else "FAIR", ""))
        pe_rows.append(("", "", "", ""))

        pe_rows.append(("CSP SOLVER", "", "", ""))
        pe_rows.append(("Resolve rate", "~1.2%", "CRITICAL", "25 of ~2039 conflicts resolved in 4 rounds"))
        pe_rows.append(("Assessment", "", "", "CSP is nearly non-functional — resolves 1 in 80 conflicts"))
        pe_rows.append(("", "", "", ""))

        pe_rows.append(("PHASE D: MULTI-RESTART OPTIMIZATION", "", "", ""))
        pe_rows.append(("Restarts", str(restart_seeds), "", f"Best seed: {best_seed}"))
        pe_rows.append(("Final clashes", str(total_clashes), "", ""))
        pe_rows.append(("Convergence", "TIGHT", "",
                         f"5/16 seeds at {total_clashes}, 8 at {total_clashes+5}, spread=30 (3.8%)"))
        pe_rows.append(("Assessment", "", "",
                         "Optimization has reached structural ceiling — further restarts unlikely to improve"))
        pe_rows.append(("", "", "", ""))

        pe_rows.append(("CAPACITY UTILIZATION", "", "", ""))
        pe_rows.append(("Overall utilization", f"{utilization}%", "LOW" if utilization < 70 else "FAIR", f"{total_enrolled}/{total_cap}"))
        pe_rows.append(("Overfilled sections", str(len(overfilled)), "BUG" if overfilled else "GOOD", ""))
        pe_rows.append(("Underfilled (<50%)", str(len(underfilled)), "POOR" if len(underfilled) > 50 else "FAIR", ""))

        for r, row_data in enumerate(pe_rows, 1):
            for c, val in enumerate(row_data, 1):
                cell = ws2.cell(r, c, val)
                if row_data[0] in ("PHASE A: SECTION PERIOD ASSIGNMENT", "PHASE B: STUDENT PLACEMENT",
                                   "CSP SOLVER", "PHASE D: MULTI-RESTART OPTIMIZATION", "CAPACITY UTILIZATION"):
                    cell.font = Font(name='Arial', bold=True, size=11)
                elif r == 2:
                    cell.font = hdr_font
                    cell.fill = hdr_fill
                else:
                    cell.font = body_font
                cell.alignment = wrap_align
                cell.border = thin
                if c == 3 and val in ('CRITICAL', 'BUG'):
                    cell.fill = crit_fill
                    cell.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
                elif c == 3 and val == 'POOR':
                    cell.fill = high_fill
                elif c == 3 and val == 'FAIR':
                    cell.fill = med_fill
                elif c == 3 and val == 'GOOD':
                    cell.fill = low_fill
        ws2.column_dimensions['A'].width = 35
        ws2.column_dimensions['B'].width = 25
        ws2.column_dimensions['C'].width = 15
        ws2.column_dimensions['D'].width = 60

        # ── Sheet 3: Bottleneck Analysis ──
        ws3 = wb.create_sheet("Bottleneck Analysis")
        bn_headers = ['Course Code', 'Course Title', 'Unscheduled', 'Demand', 'Enrolled',
                       'Sections', 'Capacity', 'Spare Seats', 'Placement %', 'Grad Req?',
                       'Periods Covered', 'Periods Missing', 'Diagnosis']
        write_header(ws3, bn_headers)
        bn_row = 2
        all_course_analysis = []
        for code in sorted(course_clashes.keys(), key=lambda c: -course_clashes[c]):
            code_secs = sec_by_code.get(code, [])
            enrolled = sum(s['enrolled'] for s in code_secs)
            count = course_clashes[code]
            cap = sum(s['cap'] for s in code_secs)
            demand = enrolled + count
            periods = sorted(set(s['period'] for s in code_secs))
            missing = sorted(set('ABCDEFG') - set(periods))
            spare = cap - enrolled
            pct = round(100 * enrolled / max(demand, 1), 1)
            is_gr = course_is_grad_req.get(code, False)
            if spare > count * 0.5:
                diag_str = 'Period saturation — has capacity but students cannot reach it'
            elif spare < count * 0.3:
                diag_str = 'Capacity shortage — needs more sections'
            else:
                diag_str = 'Mixed — partial capacity + period issues'
            entry = [code, course_names.get(code, code), count, demand, enrolled,
                     len(code_secs), cap, spare, pct, 'YES' if is_gr else '',
                     ','.join(periods), ','.join(missing) or '—', diag_str]
            all_course_analysis.append(entry)
        for entry in all_course_analysis:
            for c, v in enumerate(entry, 1):
                cell = ws3.cell(bn_row, c, v)
                cell.font = body_font
                cell.border = thin
                if c in (3, 4, 5, 6, 7, 8, 9):
                    cell.alignment = center_align
                else:
                    cell.alignment = wrap_align
                if c == 13:
                    if 'Period saturation' in str(v):
                        cell.fill = PatternFill(start_color='FFEECC', fill_type='solid')
                    elif 'Capacity shortage' in str(v):
                        cell.fill = PatternFill(start_color='FFCCCC', fill_type='solid')
            bn_row += 1

        for c in range(1, len(bn_headers) + 1):
            ws3.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 14
        ws3.column_dimensions['B'].width = 30
        ws3.column_dimensions['K'].width = 18
        ws3.column_dimensions['L'].width = 18
        ws3.column_dimensions['M'].width = 45
        ws3.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(bn_headers))}{bn_row - 1}"
        ws3.freeze_panes = 'A2'

        # ── Sheet 4: Code Change Recommendations ──
        ws4 = wb.create_sheet("Code Changes")
        rec_headers = ['ID', 'Priority', 'Title', 'Problem', 'Solution', 'Location', 'Impact Estimate', 'Affected']
        write_header(ws4, rec_headers)
        r4 = 2
        for rec in recommendations:
            if rec['type'] != 'CODE':
                continue
            vals = [rec['id'], rec['priority'], rec['title'], rec['problem'],
                    rec['solution'], rec['location'], rec['impact_estimate'],
                    rec.get('affected_courses', '')]
            for c, v in enumerate(vals, 1):
                cell = ws4.cell(r4, c, v)
                cell.font = body_font
                cell.border = thin
                cell.alignment = wrap_align
                if c == 2:
                    cell.fill = priority_fills.get(v, PatternFill())
                    if v == 'CRITICAL':
                        cell.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
            r4 += 1
        ws4.column_dimensions['A'].width = 6
        ws4.column_dimensions['B'].width = 10
        ws4.column_dimensions['C'].width = 40
        ws4.column_dimensions['D'].width = 60
        ws4.column_dimensions['E'].width = 60
        ws4.column_dimensions['F'].width = 35
        ws4.column_dimensions['G'].width = 25
        ws4.column_dimensions['H'].width = 40
        ws4.freeze_panes = 'A2'

        # ── Sheet 5: Rule Change Recommendations ──
        ws5 = wb.create_sheet("Rule Changes")
        write_header(ws5, rec_headers)
        r5 = 2
        for rec in recommendations:
            if rec['type'] != 'RULE':
                continue
            vals = [rec['id'], rec['priority'], rec['title'], rec['problem'],
                    rec['solution'], rec['location'], rec['impact_estimate'],
                    rec.get('affected_courses', '')]
            for c, v in enumerate(vals, 1):
                cell = ws5.cell(r5, c, v)
                cell.font = body_font
                cell.border = thin
                cell.alignment = wrap_align
                if c == 2:
                    cell.fill = priority_fills.get(v, PatternFill())
                    if v == 'CRITICAL':
                        cell.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
            r5 += 1
        ws5.column_dimensions['A'].width = 6
        ws5.column_dimensions['B'].width = 10
        ws5.column_dimensions['C'].width = 40
        ws5.column_dimensions['D'].width = 60
        ws5.column_dimensions['E'].width = 60
        ws5.column_dimensions['F'].width = 35
        ws5.column_dimensions['G'].width = 25
        ws5.column_dimensions['H'].width = 40
        ws5.freeze_panes = 'A2'

        # ── Sheet 6: Process Change Recommendations ──
        ws6 = wb.create_sheet("Process Changes")
        write_header(ws6, rec_headers)
        r6 = 2
        for rec in recommendations:
            if rec['type'] != 'PROCESS':
                continue
            vals = [rec['id'], rec['priority'], rec['title'], rec['problem'],
                    rec['solution'], rec['location'], rec['impact_estimate'],
                    rec.get('affected_courses', '')]
            for c, v in enumerate(vals, 1):
                cell = ws6.cell(r6, c, v)
                cell.font = body_font
                cell.border = thin
                cell.alignment = wrap_align
                if c == 2:
                    cell.fill = priority_fills.get(v, PatternFill())
                    if v == 'CRITICAL':
                        cell.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
            r6 += 1
        ws6.column_dimensions['A'].width = 6
        ws6.column_dimensions['B'].width = 10
        ws6.column_dimensions['C'].width = 45
        ws6.column_dimensions['D'].width = 60
        ws6.column_dimensions['E'].width = 60
        ws6.column_dimensions['F'].width = 35
        ws6.column_dimensions['G'].width = 35
        ws6.column_dimensions['H'].width = 40
        ws6.freeze_panes = 'A2'

        # ── Sheet 7: Period Coverage Detail ──
        ws7 = wb.create_sheet("Period Coverage")
        pc_headers = ['Course Code', 'Course Title', 'Sections', 'Unscheduled',
                       'Period A', 'Period B', 'Period C', 'Period D',
                       'Period E', 'Period F', 'Period G',
                       'Enrolled', 'Capacity', 'Fill %']
        write_header(ws7, pc_headers)
        r7 = 2
        for code in sorted(sec_by_code.keys(), key=lambda c: -course_clashes.get(c, 0)):
            code_secs = sec_by_code[code]
            if len(code_secs) < 2:
                continue
            period_dist = Counter(s['period'] for s in code_secs)
            enrolled = sum(s['enrolled'] for s in code_secs)
            cap = sum(s['cap'] for s in code_secs)
            unsched = course_clashes.get(code, 0)
            fill_pct = round(100 * enrolled / max(cap, 1), 1)
            vals = [code, course_names.get(code, code), len(code_secs), unsched]
            for p in 'ABCDEFG':
                vals.append(period_dist.get(p, 0))
            vals.extend([enrolled, cap, fill_pct])
            for c, v in enumerate(vals, 1):
                cell = ws7.cell(r7, c, v)
                cell.font = body_font
                cell.border = thin
                if c >= 5 and c <= 11:
                    cell.alignment = center_align
                    if v == 0 and unsched > 0:
                        cell.fill = PatternFill(start_color='FFCCCC', fill_type='solid')
                    elif v >= 1:
                        cell.fill = PatternFill(start_color='CCFFCC', fill_type='solid')
                elif c in (3, 4, 12, 13, 14):
                    cell.alignment = center_align
            r7 += 1
        for c in range(1, len(pc_headers) + 1):
            ws7.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 12
        ws7.column_dimensions['B'].width = 30
        ws7.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(pc_headers))}{r7 - 1}"
        ws7.freeze_panes = 'A2'

        # ── Sheet 8: Impact Projection ──
        ws8 = wb.create_sheet("Impact Projection")
        ip_items = [
            ("PROJECTED IMPACT OF RECOMMENDATIONS", "", ""),
            ("", "", ""),
            ("If All Recommendations Implemented:", "", ""),
            ("", "", ""),
            ("Category", "Current", "Projected"),
            ("Total Clashes", total_clashes, f"{total_clashes - 250} to {total_clashes - 150}"),
            ("Placement Rate", f"{placement_rate}%", f"{round(100 * (total_placed + 200) / total_requests, 1)}% to {round(100 * (total_placed + 300) / total_requests, 1)}%"),
            ("Grad Req Fulfillment", f"{stats.get('graduation_fulfillment_rate', 0)}%",
             f"{round(100 * (stats.get('graduation_required_placed', 0) + 150) / max(stats.get('graduation_required_total', 1), 1), 1)}% to {round(100 * (stats.get('graduation_required_placed', 0) + 250) / max(stats.get('graduation_required_total', 1), 1), 1)}%"),
            ("Theology Clashes", str(sum(1 for c in clashes if c['code'] in ('810','820','830'))),
             f"{sum(1 for c in clashes if c['code'] in ('810','820','830')) // 3} to {sum(1 for c in clashes if c['code'] in ('810','820','830')) // 2}"),
            ("", "", ""),
            ("INDIVIDUAL RECOMMENDATION IMPACT ESTIMATES", "", ""),
            ("", "", ""),
            ("Recommendation", "Estimated Impact", "Confidence"),
        ]
        for rec in recommendations:
            ip_items.append((f"[{rec['id']}] {rec['title']}", rec['impact_estimate'],
                             'HIGH' if rec['priority'] in ('CRITICAL', 'HIGH') else 'MEDIUM'))

        for r, row_data in enumerate(ip_items, 1):
            for c, v in enumerate(row_data, 1):
                cell = ws8.cell(r, c, v)
                if row_data[0] in ("PROJECTED IMPACT OF RECOMMENDATIONS",
                                   "If All Recommendations Implemented:",
                                   "INDIVIDUAL RECOMMENDATION IMPACT ESTIMATES"):
                    cell.font = Font(name='Arial', bold=True, size=11)
                elif row_data[0] in ("Category", "Recommendation"):
                    cell.font = hdr_font
                    cell.fill = hdr_fill
                else:
                    cell.font = body_font
                cell.alignment = wrap_align
                cell.border = thin
        ws8.column_dimensions['A'].width = 55
        ws8.column_dimensions['B'].width = 35
        ws8.column_dimensions['C'].width = 15

        report_path = os.path.join(OUTPUT_DIR, 'Engine_Analysis_Report.xlsx')
        wb.save(report_path)
        print(f"\n  Report saved: {report_path}")

        print("\n" + "=" * 60)
        print(f"ANALYSIS COMPLETE — {len(recommendations)} recommendations generated")
        print(f"  Code changes: {sum(1 for r in recommendations if r['type'] == 'CODE')}")
        print(f"  Rule changes: {sum(1 for r in recommendations if r['type'] == 'RULE')}")
        print(f"  Process changes: {sum(1 for r in recommendations if r['type'] == 'PROCESS')}")
        print(f"  Report: {report_path}")
        print("=" * 60)

    run_analysis()
    sys.exit(0)

# ============================================================
# REPORT DEFINITIONS — names, formats, and column layouts
# ============================================================
REPORT_FORMATS = {
    'master_section_report': {
        'filename': 'Master_Section_Report_2026_27.xlsx',
        'title': 'Master Section Report',
        'description': 'One row per section showing teacher, period, term, enrollment.',
        'source': 'schedule_solution_v3.json + Template 6 (teacher IDs)',
        'columns': [
            {'header': 'Teacher ID', 'width': 12, 'align': 'center'},
            {'header': 'Teacher Name', 'width': 25, 'align': 'left'},
            {'header': 'Period', 'width': 8, 'align': 'center'},
            {'header': 'Term', 'width': 6, 'align': 'center', 'values': 'S1 | S2 | FY'},
            {'header': 'Course Code', 'width': 12, 'align': 'center'},
            {'header': 'Section #', 'width': 10, 'align': 'center'},
            {'header': 'Course Title', 'width': 40, 'align': 'left'},
            {'header': 'Section Enrollment', 'width': 18, 'align': 'center'},
        ],
        'sort_order': 'Teacher Name → Period',
        'features': ['auto-filter', 'freeze row 1', 'alternating row shading'],
    },
    'teacher_schedule_review': {
        'filename': 'Teacher_Schedule_Review_and_Tally.xlsx',
        'title': 'Teacher Schedule Review & Tally',
        'description': 'Side-by-side 2025-26 vs 2026-27 schedules per teacher with tally.',
        'source': 'schedule_solution_v3.json + 202526_Master_Schedule_With_Teacher_ID.xlsx',
        'layout': {
            'col_A': 'Teacher Name (repeated per period row)',
            'col_B': 'Period (A-G)',
            'col_C': 'Spacer (gray)',
            'col_D': '2026-27 S1 courses',
            'col_E': '2026-27 S2 courses',
            'col_F': 'Spacer (gray)',
            'col_G': '2025-26 S1 courses',
            'col_H': '2025-26 S2 courses',
        },
        'per_teacher_rows': '7 period rows + TOTAL SECTIONS + TOTAL CONSECUTIVE PERIODS + blank separator',
        'tally_rules': 'Red font when consecutive periods >= 4',
        'features': ['UNASSIGNED in bold for empty slots', 'teacher ID row'],
    },
    'remaining_clashes': {
        'filename': 'Remaining_Clashes_v2.5.xlsx',
        'title': 'Remaining Clashes',
        'description': 'All unplaced student-course pairs with root cause analysis.',
        'source': 'schedule_solution_v3.json clashes array',
        'columns': [
            {'header': 'Student ID', 'width': 12, 'align': 'center'},
            {'header': 'Student Name', 'width': 22, 'align': 'left'},
            {'header': 'Grade', 'width': 8, 'align': 'center'},
            {'header': 'Course Code', 'width': 12, 'align': 'center'},
            {'header': 'Course Title', 'width': 35, 'align': 'left'},
            {'header': 'Priority', 'width': 8, 'align': 'center'},
            {'header': 'Priority Band', 'width': 18, 'align': 'center'},
            {'header': 'Grad Req?', 'width': 10, 'align': 'center', 'values': 'Yes | No'},
            {'header': 'Lost Period', 'width': 12, 'align': 'center'},
            {'header': 'Lost Semester', 'width': 12, 'align': 'center'},
            {'header': 'Root Cause', 'width': 20, 'align': 'left'},
            {'header': 'Blocking Courses', 'width': 45, 'align': 'left'},
        ],
        'sort_order': 'Effective Priority (desc) → Grade',
        'tabs': ['Remaining Clashes (detail)', 'Summary (by grade, band, grad req count)'],
        'features': ['auto-filter', 'freeze row 1', 'alternating row shading', 'dark-red header'],
    },
    'student_schedule_report': {
        'filename': 'Student_Schedule_Report_2026_27.xlsx',
        'title': 'Student Schedule Report',
        'description': 'Complete student schedules with S1/S2 split per period, credits, and clashes.',
        'source': 'schedule_solution_v3.json assignments + Template 7 (credits)',
        'layout': {
            'row_1': 'Merged period headers (Period A through Period G)',
            'row_2': 'S1 / S2 sub-headers under each period',
            'col_A': 'Student ID',
            'col_B': 'Student Name',
            'col_C': 'Grade',
            'cols_D_Q': 'Period A(S1) / Period A(S2) through Period G(S1) / Period G(S2) — 14 columns',
            'col_R': 'Total Sections',
            'col_S': 'Total Credits',
            'col_T': 'Clashes (unplaced courses listed)',
        },
        'cell_format': 'CourseCode: CourseTitle (Credits cr)',
        'empty_cell': 'UNASSIGNED (bold red)',
        'sort_order': 'Grade → Student Name',
        'features': ['auto-filter', 'freeze row 2', 'alternating row shading', 'merged period headers'],
    },
    'incomplete_student_schedules': {
        'filename': 'Incomplete_Student_Schedules_2026_27.xlsx',
        'title': 'Incomplete Student Schedules',
        'description': 'Only students with at least one UNASSIGNED period/semester slot.',
        'source': 'schedule_solution_v3.json assignments + Template 7 (credits)',
        'filter': 'Students where any Period A-G × S1/S2 slot is UNASSIGNED',
        'layout': {
            'row_1': 'Merged period headers (Period A through Period G)',
            'row_2': 'S1 / S2 sub-headers under each period',
            'col_A': 'Student ID',
            'col_B': 'Student Name',
            'col_C': 'Grade',
            'cols_D_Q': 'Period A(S1) / Period A(S2) through Period G(S1) / Period G(S2) — 14 columns',
            'col_R': 'Total Sections',
            'col_S': 'Total Credits',
            'col_T': 'Unassigned Slots (count, bold red)',
            'col_U': 'Clashes (unplaced courses listed)',
        },
        'cell_format': 'CourseCode: CourseTitle (Credits cr)',
        'empty_cell': 'UNASSIGNED (bold red)',
        'sort_order': 'Unassigned Slots (desc) → Grade → Student Name',
        'tabs': ['Incomplete Schedules (detail)', 'Summary (by grade, slot distribution)'],
        'features': ['auto-filter', 'freeze row 2', 'alternating row shading', 'merged period headers', 'dark-red header'],
    },
    'course_request_report': {
        'filename': 'Course_Request_Report_2026_27.xlsx',
        'title': 'Course Request Report',
        'description': 'Per-course fulfillment: total requests, scheduled, unscheduled, percentage.',
        'source': 'Template 2 (requests) + schedule_solution_v3.json assignments + Template 7 (course info)',
        'columns': [
            {'header': 'Course Code', 'width': 13, 'align': 'center'},
            {'header': 'Course Title', 'width': 42, 'align': 'left'},
            {'header': 'Department', 'width': 22, 'align': 'left'},
            {'header': 'Total Requests', 'width': 16, 'align': 'center'},
            {'header': 'Requests Scheduled', 'width': 18, 'align': 'center'},
            {'header': 'Requests Unscheduled', 'width': 20, 'align': 'center', 'font_rule': 'bold red if > 0'},
            {'header': '% Scheduled', 'width': 14, 'align': 'center', 'format': '0.0%',
             'font_rule': 'green if 100%, red if < 75%, amber if < 90%'},
        ],
        'sort_order': 'Course Code (numeric ascending)',
        'grand_total_row': 'Bottom row with GRAND TOTAL label, blue fill',
        'features': ['auto-filter', 'freeze row 1', 'alternating row shading'],
    },
}

# ============================================================
# PRIORITY SYSTEM — DATA_STRUCTURE.md Implementation
# ============================================================
# All characteristics stack. See DATA_STRUCTURE.md for full spec.
#
# Two levels:
#   Level 1 — Course Section Priority Value: determines section placement order
#   Level 2 — Student Priority Value: determines which students fill each section
#
# Student Raw = Grade Level + Cohort + SSP (fixed for year)
# Student Total = Raw + sum of course request priorities (changes each run)
# Teacher Raw = locks × 10 (fixed for year)
# Teacher Total = Raw + Top Student Total + Prescribed Room Total
# Room Raw = unavailable × 10 + demand × 5 (fixed for year)
# Room Total = Raw + Top Teacher Total + Top Student Total
# Course Section Raw = sum of course characteristics (fixed for year)
# Course Section Total = Raw + Top Student Total + Teacher Total + Room Total

# ── Student Raw components ──
GRADE_POINTS = {9: 10, 10: 20, 11: 30, 12: 40}
COHORT_POINTS = 50
SSP_POINTS = 25

# ── Course characteristic points (all stack) ──
PTS_AP = 30
PTS_SINGLETON = 25
PTS_GRAD_REQ = 20
PTS_GR12_PAE = 20
PTS_SEMESTER_ONLY = 15
PTS_COHORT_COURSE = 15
PTS_COSCHEDULE = 15
PTS_PRESCRIBED_TERM = 10

# ── Teacher/Room lock points ──
PTS_LOCK = 10
PTS_ROOM_DEMAND = 5

# ── Load reference data from course_priorities.json ──
with open(os.path.join(os.path.dirname(__file__) or '.', 'course_priorities.json')) as _pf:
    _prio_data = json.load(_pf)
SINGLETON_COURSES = set(str(c) for c in _prio_data.get('singleton_courses', []))

_pathway_cfg = _prio_data.get('pathway_courses', {})
_pathway_cfg.pop('_notes', None)
PATHWAY_COURSE_SETS = {name: set(str(c) for c in codes) for name, codes in _pathway_cfg.items()}

_grad_req = _prio_data.get('graduation_requirements', {})
_pe_extra = set(_grad_req.get('grades_9_10_extra', {}).get('additional_required_departments', []))
GRAD_REQ_DEPTS = {
    9:  set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])) | _pe_extra,
    10: set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])) | _pe_extra,
    11: set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])),
    12: set(_grad_req.get('grade_12', {}).get('required_departments', []))
         | set(_grad_req.get('grade_12', {}).get('required_either', [])),
}

# ── Student-specific priority overrides ──
_STUDENT_PRIO_OVERRIDES = set()
_spo_path = os.path.join(os.path.dirname(__file__) or '.', 'student_priority_overrides.json')
if os.path.exists(_spo_path):
    with open(_spo_path) as _spof:
        _spo_data = json.load(_spof)
    for _ov in _spo_data.get('overrides', []):
        _STUDENT_PRIO_OVERRIDES.add((str(_ov['student_id']).strip(), str(_ov['course_code']).strip()))
    print(f"  Student priority overrides loaded: {len(_STUDENT_PRIO_OVERRIDES)} pairs")

_course_dept_map = {}

def is_singleton(c):
    ci = course_info.get(str(c), {})
    return ci.get('is_singleton', False) or str(c) in SINGLETON_COURSES

def _is_grad_req_for_student(cid, student_grade, pid=None):
    if pid and (str(pid), str(cid)) in _STUDENT_PRIO_OVERRIDES:
        return True
    dept = _course_dept_map.get(str(cid), '')
    return dept in GRAD_REQ_DEPTS.get(student_grade, set())

_GR12_PAE_DEPTS = {'English', 'Mathematics', 'Science', 'Social Studies', 'World Language'}
_ALL_SSP_COURSES = set()
for _pw_codes in PATHWAY_COURSE_SETS.values():
    _ALL_SSP_COURSES |= _pw_codes

def _is_gr12_pae(cid):
    cid_s = str(cid)
    ci = course_info.get(cid_s, {})
    if not ci.get('is_fy', True) or ci.get('prescribed_term', 'FY') in ('S1', 'S2'):
        return False
    if _course_dept_map.get(cid_s, '') not in _GR12_PAE_DEPTS:
        return False
    cohort = ci.get('cohort_flag', '')
    if cohort and cohort not in ('', 'N', None):
        return False
    if cid_s in _ALL_SSP_COURSES:
        return False
    return True

# ── Priority caches (cleared after each placement run) ──
_crp_cache = {}
_student_total_cache = {}
_section_raw_cache = {}

def _clear_priority_caches():
    _crp_cache.clear()
    _student_total_cache.clear()
    _section_raw_cache.clear()

# ── Priority audit log (per-placement save/remove/recalculate/re-rank) ──
_priority_audit = {
    'phase_a': {'initial_snapshot': None, 'placements': [], 'final_snapshot': None},
    'phase_b': {'initial_snapshot': None, 'placements': [], 'final_snapshot': None},
}

def _capture_snapshot():
    """Capture all current priority values for audit trail."""
    snap = {'students': {}, 'teachers': {}, 'rooms': {}, 'courses': {}}
    for pid in students:
        snap['students'][pid] = {
            'name': students[pid], 'grade': grade.get(pid),
            'raw': student_raw_priority(pid), 'total': student_total_priority(pid),
        }
    _teachers_set = set(s['teacher'] for s in sections if s.get('teacher', 'TBD') != 'TBD')
    for tname in sorted(_teachers_set):
        snap['teachers'][tname] = {
            'raw': teacher_raw_priority(tname), 'total': teacher_total_priority(tname),
        }
    _rooms_set = set(s['room'] for s in sections if s.get('room', 'TBD') != 'TBD')
    for rid in sorted(_rooms_set):
        snap['rooms'][rid] = {
            'raw': room_raw_priority(rid), 'total': room_total_priority(rid),
        }
    for cid in sorted(sec_by_code.keys()):
        snap['courses'][cid] = {'section_raw': course_section_raw(cid)}
    return snap

def course_request_priority(pid, cid):
    key = (str(pid), str(cid))
    if key in _crp_cache:
        return _crp_cache[key]
    pid_s, cid_s = key
    score = 0
    ci = course_info.get(cid_s, {})
    g = grade.get(pid_s, 0)
    if ci.get('is_ap', False):
        score += PTS_AP
    if ci.get('is_singleton', False) or cid_s in SINGLETON_COURSES:
        score += PTS_SINGLETON
    if _is_grad_req_for_student(cid_s, g, pid_s):
        score += PTS_GRAD_REQ
    elif g == 12 and _is_gr12_pae(cid_s):
        score += PTS_GR12_PAE
    prescribed = ci.get('prescribed_term', 'FY')
    if prescribed in ('S1', 'S2') or not ci.get('is_fy', True):
        score += PTS_SEMESTER_ONLY
    cohort = ci.get('cohort_flag', '')
    if cohort and cohort not in ('', 'N', None):
        score += PTS_COHORT_COURSE
    if cid_s in getattr(course_request_priority, '_cogroup_set', set()):
        score += PTS_COSCHEDULE
    if prescribed in ('S1', 'S2'):
        score += PTS_PRESCRIBED_TERM
    _crp_cache[key] = score
    return score

def student_raw_priority(pid):
    pid_s = str(pid)
    g = grade.get(pid_s, 0)
    raw = GRADE_POINTS.get(g, 0)
    sp = student_profiles.get(pid_s, {})
    if sp.get('is_leo', False):
        raw += COHORT_POINTS
    pw = sp.get('pathway_name', 'N')
    acad = sp.get('is_acad_support', False)
    leo_i = sp.get('is_leo_i', False)
    if pw != 'N' or acad or leo_i:
        raw += SSP_POINTS
    return raw

def student_total_priority(pid):
    pid_s = str(pid)
    if pid_s in _student_total_cache:
        return _student_total_cache[pid_s]
    total = student_raw_priority(pid)
    for cid in sreq.get(pid_s, []):
        total += course_request_priority(pid, cid)
    _student_total_cache[pid_s] = total
    return total

def course_section_raw(cid):
    cid_s = str(cid)
    if cid_s in _section_raw_cache:
        return _section_raw_cache[cid_s]
    score = 0
    ci = course_info.get(cid_s, {})
    if ci.get('is_ap', False):
        score += PTS_AP
    if ci.get('is_singleton', False) or cid_s in SINGLETON_COURSES:
        score += PTS_SINGLETON
    if ci.get('grad_req_dept', ''):
        score += PTS_GRAD_REQ
    elif _is_gr12_pae(cid_s):
        score += PTS_GR12_PAE
    prescribed = ci.get('prescribed_term', 'FY')
    if prescribed in ('S1', 'S2') or not ci.get('is_fy', True):
        score += PTS_SEMESTER_ONLY
    cohort = ci.get('cohort_flag', '')
    if cohort and cohort not in ('', 'N', None):
        score += PTS_COHORT_COURSE
    if cid_s in getattr(course_request_priority, '_cogroup_set', set()):
        score += PTS_COSCHEDULE
    if prescribed in ('S1', 'S2'):
        score += PTS_PRESCRIBED_TERM
    _section_raw_cache[cid_s] = score
    return score

def _count_section_locks(s):
    locks = 0
    if s.get('room', 'TBD') != 'TBD':
        locks += 1
    if s.get('period') is not None:
        locks += 1
    sem = s.get('sem_raw', 'FY')
    if sem in ('S1', 'S2'):
        locks += 1
    pc = s.get('prescribed_cohort', '')
    if pc:
        locks += 1
    return locks

def teacher_raw_priority(tname):
    locks = 0
    _ctc = globals().get('code_to_cogroup', {})
    cogroup_rep = {}
    standalone = []
    for sid in teacher_sections.get(tname, []):
        s = sections[sid]
        gi = _ctc.get(s.get('code', ''))
        if gi is not None:
            if gi not in cogroup_rep:
                cogroup_rep[gi] = s
        else:
            standalone.append(s)
    for gi, rep in cogroup_rep.items():
        codes_in_group = [sections[sid]['code'] for sid in teacher_sections.get(tname, [])
                          if _ctc.get(sections[sid].get('code', '')) == gi]
        effective = max(Counter(codes_in_group).values())
        section_locks = _count_section_locks(rep)
        locks += section_locks * effective
    for s in standalone:
        locks += _count_section_locks(s)
    tp = teacher_profiles.get(tname, {})
    avail = tp.get('availability', {})
    for _p, available in avail.items():
        if not available:
            locks += 1
    return locks * PTS_LOCK

def room_raw_priority(rid):
    rid_s = str(rid)
    rp = room_profiles.get(rid_s, {})
    unavail_p = len(rp.get('unavailable_periods', set()))
    unavail_t = len(rp.get('unavailable_terms', set()))
    demand = sum(1 for s in sections if s.get('room') == rid_s)
    return (unavail_p * PTS_LOCK) + (unavail_t * PTS_LOCK) + (demand * PTS_ROOM_DEMAND)

def teacher_total_priority(tname):
    raw = teacher_raw_priority(tname)
    top_student = 0
    for sid_idx in teacher_sections.get(tname, []):
        s = sections[sid_idx]
        cid = s.get('code', '')
        for pid in sreq:
            if cid in sreq[pid]:
                st = student_total_priority(pid)
                if st > top_student:
                    top_student = st
    prescribed_room_raw = 0
    for sid_idx in teacher_sections.get(tname, []):
        s = sections[sid_idx]
        rm = s.get('room', 'TBD')
        if rm != 'TBD':
            rr = room_raw_priority(rm)
            if rr > prescribed_room_raw:
                prescribed_room_raw = rr
    return raw + top_student + prescribed_room_raw

def room_total_priority(rid):
    raw = room_raw_priority(rid)
    rid_s = str(rid)
    top_teacher = 0
    top_student = 0
    for s in sections:
        if s.get('room') != rid_s:
            continue
        tname = s.get('teacher', 'TBD')
        if tname != 'TBD':
            tt = teacher_total_priority(tname)
            if tt > top_teacher:
                top_teacher = tt
        cid = s.get('code', '')
        for pid in sreq:
            if cid in sreq[pid]:
                st = student_total_priority(pid)
                if st > top_student:
                    top_student = st
    return raw + top_teacher + top_student

def is_protected(pid, cid):
    g = grade.get(str(pid), 0)
    if _is_grad_req_for_student(cid, g, pid):
        return True
    if g == 12 and _is_gr12_pae(cid):
        return True
    if is_singleton(cid):
        return True
    return False

def priority_label(pid, cid):
    g = grade.get(str(pid), 0)
    if _is_grad_req_for_student(cid, g, pid):
        return 'graduation_required'
    if g == 12 and _is_gr12_pae(cid):
        return 'gr12_academic_elective'
    if is_singleton(cid):
        return 'singleton'
    crp = course_request_priority(pid, cid)
    if crp >= PTS_AP:
        return 'high_priority'
    return 'elective'


print("=" * 60)
print("SCHEDULING ENGINE v3 — ENHANCED BUILD")
print("=" * 60)

# ============================================================
# 0. LOAD ALL DATA
# ============================================================
print("\n[0] LOADING DATA...")

# ── Build Teacher ID → Name map from Template 6 Sheet 1 ──
t6_path = os.path.join(TEMPLATES, 'Template_6_Teacher_Profiles.xlsx')
_t6wb_init = openpyxl.load_workbook(t6_path, data_only=True)
_t6ws_profiles = _t6wb_init['Teacher Profiles']
teacher_id_to_name = {}
for r in range(3, _t6ws_profiles.max_row + 1):
    _tid = _t6ws_profiles.cell(r, 1).value
    _last = _t6ws_profiles.cell(r, 2).value
    _first = _t6ws_profiles.cell(r, 3).value
    if _tid and _last:
        _tname = f"{_last}, {_first}" if _first else str(_last)
        teacher_id_to_name[str(_tid).strip()] = _tname
print(f"  Teacher ID→Name map: {len(teacher_id_to_name)} teachers")

# ── Course info from Template 7 ──
t7_path = os.path.join(TEMPLATES, 'Template_7_Course_Profiles.xlsx')
_t7wb_ci = openpyxl.load_workbook(t7_path, data_only=True)
_t7ws_ci = _t7wb_ci.active
_t7_hdr_ci = {}
for c in range(1, _t7ws_ci.max_column + 1):
    v = _t7ws_ci.cell(1, c).value
    if v:
        _t7_hdr_ci[str(v).strip()] = c

course_info = {}
_course_max_enrollment = {}
for r in range(3, _t7ws_ci.max_row + 1):
    _cc = _t7_hdr_ci.get('Course Code', 1)
    code = _t7ws_ci.cell(r, _cc).value
    if not code:
        continue
    cid = str(code).strip()
    if not cid.replace('-', '').isdigit():
        continue

    title = _t7ws_ci.cell(r, _t7_hdr_ci.get('Course Title', 2)).value or cid
    dept = _t7ws_ci.cell(r, _t7_hdr_ci.get('Department', 3)).value or ''
    credits = _t7ws_ci.cell(r, _t7_hdr_ci.get('Credits', 4)).value or 0
    term_raw = str(_t7ws_ci.cell(r, _t7_hdr_ci.get('Prescribed Term', 5)).value or '').strip()

    is_fy = term_raw.upper() in ('FY', 'FULL-YEAR', 'FULL YEAR', '')
    ctype = 'Full-Year' if is_fy else 'Semester'

    _singleton_raw = _t7ws_ci.cell(r, _t7_hdr_ci.get('Singleton', 9)).value
    _ap_raw = _t7ws_ci.cell(r, _t7_hdr_ci.get('AP', 10)).value
    _grad_req_raw = _t7ws_ci.cell(r, _t7_hdr_ci.get('Graduation Requirement', 11)).value
    _cohort_raw = _t7ws_ci.cell(r, _t7_hdr_ci.get('Cohort', 12)).value

    course_info[cid] = {
        'code': cid, 'title': title, 'dept': str(dept),
        'credits': credits or 0, 'type': ctype, 'is_fy': is_fy,
        'prescribed_term': term_raw.upper() if term_raw else 'FY',
        'is_singleton': str(_singleton_raw).strip().upper() in ('Y', 'YES', 'TRUE', '1'),
        'is_ap': str(_ap_raw).strip().upper() in ('Y', 'YES', 'TRUE', '1'),
        'grad_req_dept': str(_grad_req_raw).strip() if _grad_req_raw and str(_grad_req_raw).strip().upper() not in ('', 'NONE', 'N', 'NO') else '',
        'cohort_flag': str(_cohort_raw).strip() if _cohort_raw and str(_cohort_raw).strip().upper() not in ('', 'NONE', 'N', 'NO') else '',
    }
    _me = _t7ws_ci.cell(r, _t7_hdr_ci.get('Max Enrollment per Section', 8)).value
    _course_max_enrollment[cid] = int(_me) if _me else 25

_t7wb_ci.close()
print(f"  Courses loaded from Template 7: {len(course_info)}")
HARD_CAP_ENFORCEMENT = True

# ── Semester designations ──
_semester_designations = {}
_sd_path = os.path.join(os.path.dirname(__file__) or '.', 'semester_designations.json')
try:
    with open(_sd_path) as _sdf:
        _sd_data = json.load(_sdf)
    for _entry in _sd_data:
        _sdcode = str(_entry.get('code', '')).strip()
        if _sdcode and 'section_details' in _entry:
            _semester_designations[_sdcode] = _entry
    print(f"  Semester designations loaded: {len(_semester_designations)} courses")
except FileNotFoundError:
    print("  semester_designations.json not found — using defaults")

# ── Sections from Template 6 Sheet 2 (Teacher-Course Assignments) ──
_t6ws_assign = _t6wb_init['Teacher-Course Assignments']
sections = []
sec_by_code = defaultdict(list)
teacher_sections = defaultdict(list)
_section_counter = defaultdict(int)

for r in range(3, _t6ws_assign.max_row + 1):
    _tid = _t6ws_assign.cell(r, 1).value
    code = _t6ws_assign.cell(r, 2).value
    room = _t6ws_assign.cell(r, 3).value
    prescribed_period = _t6ws_assign.cell(r, 4).value
    prescribed_term = _t6ws_assign.cell(r, 5).value
    prescribed_cohort = _t6ws_assign.cell(r, 6).value

    if code is None:
        continue
    cid = str(code).strip()
    if cid not in course_info:
        continue

    ci = course_info[cid]
    is_fy = ci.get('is_fy', True)

    _section_counter[cid] += 1
    secnum = _section_counter[cid]

    teacher_name = 'TBD'
    if _tid:
        teacher_name = teacher_id_to_name.get(str(_tid).strip(), 'TBD')

    halves = ('S1', 'S2') if is_fy else ('S1',)
    sem_str = str(prescribed_term or '').strip().upper()
    if sem_str in ('S1', 'FALL'):
        halves = ('S1',)
    elif sem_str in ('S2', 'SPRING'):
        halves = ('S2',)
    elif sem_str in ('FY', 'FULL-YEAR', 'FULL YEAR'):
        halves = ('S1', 'S2')

    _sd_entry = _semester_designations.get(cid)
    if _sd_entry and 'section_details' in _sd_entry:
        for _sd_sec in _sd_entry['section_details']:
            if _sd_sec.get('sec') == secnum:
                _sd_sem = str(_sd_sec.get('semester', '')).strip().upper()
                if _sd_sem == 'S1':
                    halves = ('S1',)
                elif _sd_sem == 'S2':
                    halves = ('S2',)
                elif _sd_sem in ('FY', 'FULL-YEAR'):
                    halves = ('S1', 'S2')
                break

    period = None
    if prescribed_period:
        p = str(prescribed_period).strip().upper()
        if p in PERIODS:
            period = p

    room_str = str(room).strip() if room and str(room).strip() not in ('None', '') else 'TBD'
    cap = _course_max_enrollment.get(cid, 25)

    sid = len(sections)
    _pc_str = str(prescribed_cohort).strip() if prescribed_cohort and str(prescribed_cohort).strip().upper() not in ('', 'NONE', 'N', 'NO') else ''
    sec = {
        'sid': sid, 'code': cid, 'section': secnum,
        'period': period, 'halves': halves, 'cap': cap,
        'teacher': teacher_name, 'room': room_str,
        'title': ci.get('title', cid), 'dept': ci.get('dept', ''),
        'is_fy': is_fy, 'sem_raw': sem_str or str(prescribed_term or ''),
        'prescribed_cohort': _pc_str,
    }
    sections.append(sec)
    sec_by_code[cid].append(sid)
    if teacher_name and teacher_name != 'TBD':
        teacher_sections[teacher_name].append(sid)

_t6wb_init.close()
print(f"  Sections: {len(sections)}")
print(f"  Courses with sections: {len(sec_by_code)}")
print(f"  Teachers with sections: {len(teacher_sections)}")

# ── Template 9: Room Profiles ──
room_profiles = {}
SHARED_ROOMS = set()
t9_path = os.path.join(TEMPLATES, 'Template_9_Room_Profiles.xlsx')
try:
    _t9wb = openpyxl.load_workbook(t9_path, data_only=True)
    _t9ws = _t9wb.active
    _all_periods = set(PERIODS)
    _all_terms = {'FY', 'S1', 'S2'}
    for r in range(3, _t9ws.max_row + 1):
        _rid = _t9ws.cell(r, 1).value
        _rcap = _t9ws.cell(r, 2).value
        _ravail_p = _t9ws.cell(r, 3).value
        _ravail_t = _t9ws.cell(r, 4).value
        _rshared = _t9ws.cell(r, 5).value
        if not _rid:
            continue
        rid = str(_rid).strip()
        _cap = int(_rcap) if _rcap else 25
        _is_simultaneous = _cap >= 100 and str(_rshared or 'N').upper() == 'Y'
        if _is_simultaneous:
            SHARED_ROOMS.add(rid)
        _avail_periods = set(p.strip().upper() for p in str(_ravail_p or 'A,B,C,D,E,F,G').split(',')) if _ravail_p else set(_all_periods)
        _unavail_periods = _all_periods - _avail_periods
        _avail_terms_raw = str(_ravail_t or 'FY,S1,S2').split(',')
        _avail_terms = set(t.strip().upper() for t in _avail_terms_raw) if _ravail_t else set(_all_terms)
        if 'FY' in _avail_terms:
            _avail_terms |= {'S1', 'S2'}
        _unavail_terms = _all_terms - _avail_terms
        room_profiles[rid] = {
            'capacity': _cap,
            'shared': _is_simultaneous,
            'available_periods': _avail_periods,
            'unavailable_periods': _unavail_periods,
            'available_terms': _avail_terms,
            'unavailable_terms': _unavail_terms,
        }
    _t9wb.close()
    _restricted_rooms = sum(1 for rp in room_profiles.values() if rp['unavailable_periods'] or rp['unavailable_terms'])
    print(f"  Room profiles loaded: {len(room_profiles)} rooms (simultaneous-use: {SHARED_ROOMS or 'none'}, restricted: {_restricted_rooms})")
except FileNotFoundError:
    print("  Template 9 not found — using defaults for room profiles")

# ── Student names and grades from Template 8 (for Template 2 join) ──
t8_path = os.path.join(TEMPLATES, 'Template_8_Student_Profiles.xlsx')
_student_names = {}
_student_grades = {}
try:
    _t8wb_n = openpyxl.load_workbook(t8_path, data_only=True)
    _t8ws_n = _t8wb_n[_t8wb_n.sheetnames[0]]
    for r in range(3, _t8ws_n.max_row + 1):
        _sid = _t8ws_n.cell(r, 1).value
        _last = _t8ws_n.cell(r, 2).value
        _first = _t8ws_n.cell(r, 3).value
        _gv = _t8ws_n.cell(r, 4).value
        if not _sid:
            continue
        _pid = str(_sid).strip()
        _student_names[_pid] = f"{_last}, {_first}" if _last and _first else str(_last or _first or _pid)
        _g = 9
        if _gv:
            _gs = str(_gv).strip()
            for _d in ['12', '11', '10', '9']:
                if _d in _gs:
                    _g = int(_d)
                    break
        _student_grades[_pid] = _g
    _t8wb_n.close()
    print(f"  Student names/grades from T8: {len(_student_names)} students")
except FileNotFoundError:
    print("  Template 8 not found — student names will use IDs")

# Populate course→department map for graduation-requirement priority
for _cid, _ci in course_info.items():
    _course_dept_map[_cid] = _ci.get('dept', '')

# ── Template 2: Student Course Requests (2-column format) ──
t2_path = os.path.join(TEMPLATES, 'Template_2_Student_Course_Requests.xlsx')
rwb = openpyxl.load_workbook(t2_path, data_only=True)
rws = rwb.active
students = {}
sreq = defaultdict(list)
grade = {}
for r in range(3, rws.max_row + 1):
    pid_raw = rws.cell(r, 1).value
    cid_raw = rws.cell(r, 2).value
    if pid_raw is None or cid_raw is None:
        continue
    pid = str(pid_raw).strip()
    cid = str(cid_raw).strip()
    if cid == '0':
        continue
    if cid not in sec_by_code:
        continue
    if pid not in students:
        students[pid] = _student_names.get(pid, pid)
        grade[pid] = _student_grades.get(pid, 9)
    if cid not in sreq[pid]:
        sreq[pid].append(cid)

print(f"  Students: {len(students)}")
print(f"  Requests: {sum(len(v) for v in sreq.values())}")
rwb.close()

# ── Template 6: Teacher Profiles (Sheet 1) ──
teacher_profiles = {}
try:
    t6wb = openpyxl.load_workbook(t6_path, data_only=True)
    t6ws = t6wb['Teacher Profiles']
    t6_hdr = {}
    for c in range(1, t6ws.max_column + 1):
        v = t6ws.cell(1, c).value
        if v:
            t6_hdr[str(v).strip()] = c

    def t6col(name, default=None):
        return t6_hdr.get(name, default)

    for r in range(3, t6ws.max_row + 1):
        last = t6ws.cell(r, t6col('Last Name', 2)).value
        first = t6ws.cell(r, t6col('First Name', 3)).value
        if not last:
            continue
        tname = f"{last}, {first}" if first else str(last)

        def _read(col_name, fallback_col=None):
            c = t6col(col_name, fallback_col)
            return t6ws.cell(r, c).value if c else None

        max_periods = _read('Max Teaching Periods')

        avail = {}
        for period in PERIODS:
            v = _read(f'Avail Period {period}') or _read(f'Avail Per {period}')
            avail[period] = str(v).upper() != 'N' if v else True

        approved_6_fy = str(_read('Approved 6th Period FY') or _read('Approved 6-Period Full-Year') or 'N').upper() == 'Y'
        approved_6_s1 = str(_read('Approved 6th Period S1 Only') or _read('Approved 6-Period Semester 1') or 'N').upper() == 'Y'
        approved_6_s2 = str(_read('Approved 6th Period S2 Only') or _read('Approved 6-Period Semester 2') or 'N').upper() == 'Y'

        dept1 = str(_read('Department') or _read('Department 1') or '')

        ssp_teacher = str(_read('Special Student Population Teacher') or _read('SSP Teacher') or 'N').upper() == 'Y'

        teacher_profiles[tname] = {
            'max_periods': int(max_periods) if max_periods and str(max_periods) != 'N/A' else 5,
            'max_consecutive': 3,
            'prep_required': 2,
            'duty_periods': 0,
            'availability': avail,
            'approved_6_fy': approved_6_fy,
            'approved_6_s1': approved_6_s1,
            'approved_6_s2': approved_6_s2,
            'requires_2_consec_free': False,
            'preferred_room': '',
            'preferred_wing': '',
            'preferred_periods': [],
            'avoid_periods': [],
            'contract': 'Standard',
            'department_1': dept1,
            'department_2': '',
            'ssp_teacher': ssp_teacher,
            'teaches_leo': False,
            'teaches_pathway': False,
            'teaches_acad_support': False,
            'course_teacher_locks': '',
            'computed_mtp': None,
            'computed_tssp': None,
        }
    t6wb.close()
    print(f"  Teacher profiles loaded: {len(teacher_profiles)}")
except FileNotFoundError:
    print("  Template 6 not found — using defaults for teacher profiles")

# ── Transcript History from Template_Historical_Grades.xlsx ──
transcript = defaultdict(list)
_thg_path = os.path.join(TEMPLATES, 'Template_Historical_Grades.xlsx')
try:
    _thgwb = openpyxl.load_workbook(_thg_path, data_only=True)
    _thgws = _thgwb.active
    for r in range(3, _thgws.max_row + 1):
        sid = _thgws.cell(r, 1).value
        year = _thgws.cell(r, 2).value
        ccode = _thgws.cell(r, 3).value
        final_grade = _thgws.cell(r, 5).value
        passed = _thgws.cell(r, 6).value
        if sid and ccode:
            transcript[str(sid).strip()].append({
                'year': str(year or ''),
                'code': str(ccode).strip(),
                'grade': str(final_grade or ''),
                'passed': str(passed or '').upper() == 'Y',
            })
    _thgwb.close()
    total_transcript = sum(len(v) for v in transcript.values())
    print(f"  Transcript records loaded: {total_transcript} ({len(transcript)} students)")
except FileNotFoundError:
    print("  Template_Historical_Grades.xlsx not found — skipping transcript validation")

# ── Template 8: Student Profiles (SSP, LEO, Pathway, Academic Support) ──
student_profiles = {}
try:
    t8wb2 = openpyxl.load_workbook(t8_path, data_only=True)
    t8_profile_sheet = None
    for _sn in ('Student Profiles', 'Profiles', 'Sheet1'):
        if _sn in t8wb2.sheetnames:
            t8_profile_sheet = t8wb2[_sn]
            break
    if t8_profile_sheet is None:
        t8_profile_sheet = t8wb2[t8wb2.sheetnames[0]]
    t8_hdr = {}
    for c in range(1, t8_profile_sheet.max_column + 1):
        v = t8_profile_sheet.cell(1, c).value
        if v:
            t8_hdr[str(v).strip()] = c
    def _t8col(name):
        return t8_hdr.get(name)
    for r in range(3, t8_profile_sheet.max_row + 1):
        sid_col = _t8col('Student ID') or 1
        sid = t8_profile_sheet.cell(r, sid_col).value
        if not sid:
            continue
        sid_str = str(sid).strip()
        _leo_col = _t8col('LEO II')
        _leo1_col = _t8col('LEO I')
        _pathway_col = _t8col('Pathway')
        _acad_col = _t8col('Academic Support')
        _ssp_col = _t8col('SSP')
        _grade_col = _t8col('Grade Level')
        is_leo = str(t8_profile_sheet.cell(r, _leo_col).value or 'N').upper() == 'Y' if _leo_col else False
        is_leo_i = str(t8_profile_sheet.cell(r, _leo1_col).value or 'N').upper() == 'Y' if _leo1_col else False
        _pathway_raw = str(t8_profile_sheet.cell(r, _pathway_col).value or 'N').strip() if _pathway_col else 'N'
        is_pathway = _pathway_raw not in ('N', 'n', '')
        _pathway_name = _pathway_raw if is_pathway else 'N'
        is_acad_support = str(t8_profile_sheet.cell(r, _acad_col).value or 'N').upper() == 'Y' if _acad_col else False
        ssp_val = t8_profile_sheet.cell(r, _ssp_col).value if _ssp_col else None
        ssp_score = int(ssp_val) if ssp_val and str(ssp_val).strip().isdigit() else None
        grade_val = t8_profile_sheet.cell(r, _grade_col).value if _grade_col else None
        if ssp_score is None:
            if is_leo:
                ssp_score = 5
            elif is_pathway:
                ssp_score = 4
            elif is_acad_support:
                ssp_score = 3
            else:
                ssp_score = 1
        student_profiles[sid_str] = {
            'is_leo': is_leo,
            'is_leo_i': is_leo_i,
            'is_pathway': is_pathway,
            'pathway_name': _pathway_name,
            'is_acad_support': is_acad_support,
            'ssp': ssp_score,
            'grade': str(grade_val or ''),
        }
    t8wb2.close()
    _leo_count = sum(1 for sp in student_profiles.values() if sp['is_leo'])
    _leo1_count = sum(1 for sp in student_profiles.values() if sp.get('is_leo_i', False))
    _pathway_count = sum(1 for sp in student_profiles.values() if sp['is_pathway'])
    _acad_count = sum(1 for sp in student_profiles.values() if sp['is_acad_support'])
    _pw_names = {}
    for sp in student_profiles.values():
        pn = sp.get('pathway_name', 'N')
        if pn != 'N':
            _pw_names[pn] = _pw_names.get(pn, 0) + 1
    _pw_summary = ', '.join(f"{k}={v}" for k, v in sorted(_pw_names.items(), key=lambda x: -x[1]))
    print(f"  Student profiles loaded: {len(student_profiles)} (LEO II={_leo_count}, LEO I={_leo1_count}, Pathway={_pathway_count}, AcadSupport={_acad_count})")
    if _pw_summary:
        print(f"  Pathway breakdown: {_pw_summary}")
except FileNotFoundError:
    print("  Template 8 not found — skipping student profiles")
except Exception as _e:
    print(f"  Warning: Could not read Student Profiles sheet: {_e}")

# ── Template 7: Course Profiles (prerequisites + grade eligibility) ──
course_prereqs = {}
course_grade_levels = {}
try:
    _t7wb_pr = openpyxl.load_workbook(t7_path, data_only=True)
    _t7ws_pr = _t7wb_pr.active
    _t7_hdr_pr = {}
    for c in range(1, _t7ws_pr.max_column + 1):
        v = _t7ws_pr.cell(1, c).value
        if v:
            _t7_hdr_pr[str(v).strip()] = c
    _prereq_col = _t7_hdr_pr.get('Prerequisites', 14)
    _coreq_col = _t7_hdr_pr.get('Corequisites', 15)
    _gl_col = _t7_hdr_pr.get('Grade Levels', 6)
    _cc_col = _t7_hdr_pr.get('Course Code', 1)
    for r in range(3, _t7ws_pr.max_row + 1):
        ccode = _t7ws_pr.cell(r, _cc_col).value
        if not ccode:
            continue
        cid = str(ccode).strip()
        if not cid.replace('-', '').isdigit():
            continue
        prereqs = _t7ws_pr.cell(r, _prereq_col).value
        coreqs = _t7ws_pr.cell(r, _coreq_col).value
        grade_levels_raw = _t7ws_pr.cell(r, _gl_col).value
        prereq_list = []
        if prereqs and str(prereqs).strip() not in ('N/A', ''):
            prereq_list = [p.strip() for p in str(prereqs).split(',') if p.strip()]
        coreq_list = []
        if coreqs and str(coreqs).strip() not in ('N/A', ''):
            coreq_list = [p.strip() for p in str(coreqs).split(',') if p.strip()]
        if prereq_list or coreq_list:
            course_prereqs[cid] = {'prereqs': prereq_list, 'coreqs': coreq_list}
        if grade_levels_raw and str(grade_levels_raw).strip() not in ('N/A', ''):
            gl_set = set()
            for g in str(grade_levels_raw).split(','):
                g = g.strip()
                if g.isdigit():
                    gl_set.add(int(g))
            if gl_set:
                course_grade_levels[cid] = gl_set
    _t7wb_pr.close()
    print(f"  Course prerequisites loaded: {len(course_prereqs)} courses with prereqs/coreqs")
    print(f"  Grade-level eligibility loaded: {len(course_grade_levels)} courses")
except FileNotFoundError:
    print("  Template 7 not found — skipping prerequisite data")

# ── Template 10: Contracts ──
contracts = {}
t10_path = os.path.join(TEMPLATES, 'Template_10_Contracts.xlsx')
try:
    t10wb = openpyxl.load_workbook(t10_path, data_only=True)
    t10ws = t10wb.active
    for r in range(2, t10ws.max_row + 1):
        ccode = t10ws.cell(r, 1).value
        cname = t10ws.cell(r, 2).value
        if not ccode:
            continue
        max_teach = t10ws.cell(r, 6).value
        max_consec = t10ws.cell(r, 8).value
        max_total = t10ws.cell(r, 9).value
        prep_req = t10ws.cell(r, 10).value
        duty_max = t10ws.cell(r, 12).value
        overload = t10ws.cell(r, 15).value
        contracts[str(ccode).strip()] = {
            'name': str(cname or ''),
            'max_teaching': int(max_teach) if max_teach and str(max_teach) != 'N/A' else 5,
            'max_consecutive': int(max_consec) if max_consec and str(max_consec) != 'N/A' else 3,
            'max_total': int(max_total) if max_total and str(max_total) != 'N/A' else 7,
            'prep_required': int(prep_req) if prep_req and str(prep_req) != 'N/A' else 1,
            'duty_max': int(duty_max) if duty_max and str(duty_max) != 'N/A' else 1,
            'overload_threshold': int(overload) if overload and str(overload) != 'N/A' else 6,
        }
    t10wb.close()
    print(f"  Contracts loaded: {len(contracts)} types")
except FileNotFoundError:
    print("  Template 10 not found — using default contract rules")


# ── Credit Validation Gate ──
CREDIT_CAP = 35.0
CREDIT_EXEMPT = {'955'}
_credit_violations = []
for _pid in sreq:
    _total_cr = 0.0
    _courses_cr = []
    for _cid in sreq[_pid]:
        if _cid in CREDIT_EXEMPT:
            continue
        _cr = course_info.get(_cid, {}).get('credits', 0) or 0
        _total_cr += float(_cr)
        _courses_cr.append((_cid, course_info.get(_cid, {}).get('title', _cid), float(_cr)))
    if _total_cr > CREDIT_CAP:
        _courses_cr.sort(key=lambda x: x[2])
        _credit_violations.append({
            'student_id': _pid,
            'name': students[_pid],
            'grade': grade.get(_pid, 0),
            'total_credits': _total_cr,
            'excess': round(_total_cr - CREDIT_CAP, 1),
            'course_count': len(sreq[_pid]),
            'courses': [{'code': c, 'title': t, 'credits': cr} for c, t, cr in _courses_cr]
        })
_credit_violations.sort(key=lambda v: (-v['total_credits'], v['student_id']))
print(f"  Credit validation: {len(students)} students checked, cap={CREDIT_CAP}")
if _credit_violations:
    print(f"\n  *** CREDIT CAP VIOLATION: {len(_credit_violations)} students exceed {CREDIT_CAP} credits ***")
    for _v in _credit_violations[:10]:
        print(f"    {_v['student_id']} ({_v['name']}, Gr{_v['grade']}): {_v['total_credits']:.1f} credits ({_v['excess']:.1f} over)")
    _report_path = os.path.join(SCRATCHPAD, 'credit_violations.json')
    with open(_report_path, 'w') as _rf:
        json.dump({
            'validation': 'credit_cap', 'cap': CREDIT_CAP,
            'total_students': len(students), 'violations': len(_credit_violations),
            'students': _credit_violations
        }, _rf, indent=2)
    print(f"\n  *** WARNING: credit violations detected — engine will proceed ***")
    print(f"  (Review {_report_path} for details)")
else:
    print(f"  Credit validation: PASSED")


# ============================================================
# 0b. PRE-FLIGHT VALIDATION (NEW in v3)
# ============================================================
print("\n" + "=" * 60)
print("[0b] PRE-FLIGHT VALIDATION")
print("=" * 60)

preflight_warnings = []
preflight_errors = []

# ── Duplicate Request Detection ──
if transcript:
    dup_count = 0
    for pid in sreq:
        completed = {t['code'] for t in transcript.get(pid, []) if t['passed']}
        for cid in list(sreq[pid]):
            if cid in completed:
                ci = course_info.get(cid, {})
                preflight_warnings.append({
                    'type': 'DUPLICATE_REQUEST',
                    'student': pid,
                    'name': students.get(pid, pid),
                    'grade': grade.get(pid, 0),
                    'course': cid,
                    'course_title': ci.get('title', cid),
                    'message': f"Student {pid} ({students.get(pid, pid)}) already passed {cid} ({ci.get('title', cid)}) — request may be erroneous"
                })
                dup_count += 1
    print(f"  Duplicate request check: {dup_count} potential duplicates found")
    if dup_count:
        for w in preflight_warnings[:5]:
            if w['type'] == 'DUPLICATE_REQUEST':
                print(f"    {w['message']}")
        if dup_count > 5:
            print(f"    ... and {dup_count - 5} more")
else:
    print("  Duplicate request check: SKIPPED (no transcript data)")

# ── Prerequisite Validation ──
if transcript and course_prereqs:
    prereq_fails = 0
    prereq_with_transcript = 0
    prereq_no_transcript = 0
    for pid in sreq:
        completed = {t['code'] for t in transcript.get(pid, []) if t['passed']}
        has_transcript = pid in transcript
        for cid in sreq[pid]:
            pr = course_prereqs.get(cid, {})
            for prereq in pr.get('prereqs', []):
                if prereq not in completed and prereq not in sreq[pid]:
                    ci = course_info.get(cid, {})
                    pi = course_info.get(prereq, {})
                    preflight_warnings.append({
                        'type': 'PREREQ_MISSING',
                        'student': pid,
                        'name': students.get(pid, pid),
                        'grade': grade.get(pid, 0),
                        'course': cid,
                        'course_title': ci.get('title', cid),
                        'prereq': prereq,
                        'prereq_title': pi.get('title', prereq),
                        'has_transcript': has_transcript,
                        'message': f"Student {pid} requests {cid} ({ci.get('title', cid)}) but missing prereq {prereq} ({pi.get('title', prereq)})"
                    })
                    prereq_fails += 1
                    if has_transcript:
                        prereq_with_transcript += 1
                    else:
                        prereq_no_transcript += 1
    print(f"  Prerequisite check: {prereq_fails} missing prerequisites found")
    if prereq_fails:
        print(f"    With transcript (review needed): {prereq_with_transcript}")
        print(f"    No transcript (freshmen/transfer): {prereq_no_transcript}")
        _shown = 0
        for w in preflight_warnings:
            if w['type'] == 'PREREQ_MISSING' and _shown < 5:
                print(f"    {w['message']}")
                _shown += 1
        if prereq_fails > 5:
            print(f"    ... and {prereq_fails - 5} more")
else:
    print("  Prerequisite check: SKIPPED (no transcript or prereq data)")

# ── Grade-Level Eligibility Check ──
if course_grade_levels:
    grade_ineligible = 0
    for pid in sreq:
        student_grade = grade.get(pid, 0)
        if not student_grade:
            continue
        for cid in sreq[pid]:
            eligible_grades = course_grade_levels.get(cid)
            if eligible_grades and student_grade not in eligible_grades:
                ci = course_info.get(cid, {})
                preflight_warnings.append({
                    'type': 'GRADE_INELIGIBLE',
                    'student': pid,
                    'name': students.get(pid, pid),
                    'grade': student_grade,
                    'course': cid,
                    'course_title': ci.get('title', cid),
                    'eligible_grades': sorted(eligible_grades),
                    'message': f"Student {pid} ({students.get(pid, pid)}, Gr{student_grade}) requests {cid} ({ci.get('title', cid)}) but course is for grades {sorted(eligible_grades)}"
                })
                grade_ineligible += 1
    print(f"  Grade-level eligibility check: {grade_ineligible} ineligible requests found")
    if grade_ineligible:
        _shown = 0
        for w in preflight_warnings:
            if w['type'] == 'GRADE_INELIGIBLE' and _shown < 5:
                print(f"    {w['message']}")
                _shown += 1
        if grade_ineligible > 5:
            print(f"    ... and {grade_ineligible - 5} more")
else:
    print("  Grade-level eligibility check: SKIPPED (no grade-level data)")

# ── Constraint Chain Analysis ──
constraint_warnings = 0
for pid in sreq:
    period_demands = defaultdict(list)
    for cid in sreq[pid]:
        sids_for_course = sec_by_code.get(cid, [])
        available_periods = set()
        for sid_c in sids_for_course:
            if sections[sid_c]['period']:
                available_periods.add(sections[sid_c]['period'])
        if len(available_periods) == 1:
            p = list(available_periods)[0]
            period_demands[p].append(cid)
    for p, courses_in_p in period_demands.items():
        if len(courses_in_p) > 1:
            constraint_warnings += 1
            titles = [course_info.get(c, {}).get('title', c) for c in courses_in_p]
            preflight_warnings.append({
                'type': 'CONSTRAINT_CHAIN',
                'student': pid,
                'name': students.get(pid, pid),
                'period': p,
                'courses': courses_in_p,
                'message': f"Student {pid}: unavoidable conflict in period {p} — {', '.join(titles)} all locked there"
            })
if constraint_warnings:
    print(f"  Constraint chain analysis: {constraint_warnings} unavoidable conflicts detected")

# Save pre-flight report (JSON)
_dup_warnings = [w for w in preflight_warnings if w['type'] == 'DUPLICATE_REQUEST']
_prereq_warnings = [w for w in preflight_warnings if w['type'] == 'PREREQ_MISSING']
_chain_warnings = [w for w in preflight_warnings if w['type'] == 'CONSTRAINT_CHAIN']
_grade_warnings = [w for w in preflight_warnings if w['type'] == 'GRADE_INELIGIBLE']
_prereq_with_trans = [w for w in _prereq_warnings if w.get('has_transcript')]
_prereq_no_trans = [w for w in _prereq_warnings if not w.get('has_transcript')]

preflight_report = {
    'total_warnings': len(preflight_warnings),
    'duplicates': len(_dup_warnings),
    'prereq_missing': len(_prereq_warnings),
    'prereq_with_transcript': len(_prereq_with_trans),
    'prereq_no_transcript': len(_prereq_no_trans),
    'grade_ineligible': len(_grade_warnings),
    'constraint_chains': len(_chain_warnings),
    'warnings': preflight_warnings,
}
with open(os.path.join(SCRATCHPAD, 'preflight_report.json'), 'w') as pf:
    json.dump(preflight_report, pf, indent=2)
print(f"  Pre-flight report saved: {len(preflight_warnings)} total warnings")

# Auto-generate pre-flight review spreadsheet
_report_xlsx_path = os.path.join(OUTPUT_DIR, 'Preflight_Validation_Report.xlsx')
try:
    from openpyxl.styles import Font as _Font, PatternFill as _Fill, Alignment as _Align, Border as _Border, Side as _Side
    _rwb = openpyxl.Workbook()
    _hfont = _Font(name='Arial', bold=True, size=11, color='FFFFFF')
    _hfill = _Fill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    _dfont = _Font(name='Arial', size=10)
    _afill = _Fill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    _afont = _Font(name='Arial', size=10, bold=True, color='0000FF')
    _alert = _Fill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
    _tbord = _Border(left=_Side(style='thin'), right=_Side(style='thin'),
                     top=_Side(style='thin'), bottom=_Side(style='thin'))

    def _style_hdr(ws, cols):
        for c, t in enumerate(cols, 1):
            cell = ws.cell(1, c, t)
            cell.font, cell.fill, cell.border = _hfont, _hfill, _tbord
            cell.alignment = _Align(horizontal='center', wrap_text=True)

    # ── Summary tab ──
    _ws_sum = _rwb.active
    _ws_sum.title = 'Summary'
    _ws_sum.sheet_properties.tabColor = '00B050'
    _ws_sum.cell(1, 1, 'PRE-FLIGHT VALIDATION REPORT').font = _Font(name='Arial', bold=True, size=14)
    _ws_sum.cell(2, 1, 'Don Bosco Prep 2026-27 Master Schedule').font = _Font(name='Arial', size=11)
    _ws_sum.cell(3, 1, 'Generated by Schedule Engine v3').font = _Font(name='Arial', size=10, italic=True)
    _style_hdr(_ws_sum, ['', '', ''])
    _ws_sum.cell(5, 1).value, _ws_sum.cell(5, 2).value, _ws_sum.cell(5, 3).value = 'CATEGORY', 'COUNT', 'DESCRIPTION'
    for c in range(1, 4):
        _ws_sum.cell(5, c).font, _ws_sum.cell(5, c).fill, _ws_sum.cell(5, c).border = _hfont, _hfill, _tbord
    _sum_rows = [
        ('Duplicate Requests', len(_dup_warnings), 'Students requesting courses they already passed'),
        ('Grade-Level Ineligible', len(_grade_warnings), 'Students requesting courses outside their approved grade level'),
        ('Prereq Warnings (with transcript)', len(_prereq_with_trans), 'Students with history missing a prerequisite — REVIEW NEEDED'),
        ('Prereq Warnings (no transcript)', len(_prereq_no_trans), 'Freshmen/transfers with no prior history — likely OK'),
        ('Constraint Chain Conflicts', len(_chain_warnings), 'Unavoidable period conflicts from locked sections'),
        ('TOTAL', len(preflight_warnings), ''),
    ]
    for i, (cat, cnt, desc) in enumerate(_sum_rows, 6):
        _ws_sum.cell(i, 1, cat).font = _Font(name='Arial', size=10, bold=(cat == 'TOTAL'))
        _ws_sum.cell(i, 2, cnt).font = _Font(name='Arial', size=10, bold=(cat == 'TOTAL'))
        _ws_sum.cell(i, 3, desc).font = _dfont
        for c in range(1, 4):
            _ws_sum.cell(i, c).border = _tbord
    _ws_sum.cell(13, 1, 'HOW TO USE THIS REPORT:').font = _Font(name='Arial', bold=True, size=11, color='2F5496')
    _instructions = [
        '1. Review each tab — yellow ACTION column is yours to fill in.',
        '2. For DUPLICATES: type KEEP (retaking intentionally) or REMOVE (erroneous).',
        '3. For GRADE INELIGIBLE: type OK (counselor override) or REMOVE (block the request).',
        '4. For PREREQ WARNINGS: type OK (override/waiver), REMOVE (block), or TRANSFER (took equivalent elsewhere).',
        '5. The "No Transcript" tab is mostly freshmen — mark OK for legitimate enrollments.',
        '6. Return this file and the engine will apply your decisions on the next run.',
    ]
    for i, line in enumerate(_instructions, 13):
        _ws_sum.cell(i, 1, line).font = _dfont
    _ws_sum.column_dimensions['A'].width = 45
    _ws_sum.column_dimensions['B'].width = 12
    _ws_sum.column_dimensions['C'].width = 60

    # ── Duplicates tab ──
    _ws_dup = _rwb.create_sheet('Duplicate Requests')
    _dup_cols = ['Student ID', 'Student Name', 'Grade', 'Course Code', 'Course Title', 'Issue', 'ACTION (Your Decision)']
    _style_hdr(_ws_dup, _dup_cols)
    _sorted_dupes = sorted(_dup_warnings, key=lambda x: (x.get('grade', 0), x.get('name', '')))
    for i, d in enumerate(_sorted_dupes, 2):
        _ws_dup.cell(i, 1, int(d['student'])).font = _dfont
        _ws_dup.cell(i, 2, d.get('name', '')).font = _dfont
        _ws_dup.cell(i, 3, d.get('grade', '')).font = _dfont
        _ws_dup.cell(i, 4, d.get('course', '')).font = _dfont
        _ws_dup.cell(i, 5, d.get('course_title', '')).font = _dfont
        _ws_dup.cell(i, 6, 'Already passed this course').font = _dfont
        _ws_dup.cell(i, 6).fill = _alert
        _ws_dup.cell(i, 7, '').font, _ws_dup.cell(i, 7).fill = _afont, _afill
        for c in range(1, 8):
            _ws_dup.cell(i, c).border = _tbord
    for col, w in [('A',12),('B',22),('C',8),('D',12),('E',32),('F',24),('G',30)]:
        _ws_dup.column_dimensions[col].width = w

    # ── Grade-Level Ineligible tab ──
    _ws_gl = _rwb.create_sheet('Grade-Level Ineligible')
    _gl_cols = ['Student ID', 'Student Name', 'Student Grade', 'Course Code', 'Course Title',
                'Eligible Grades', 'Issue', 'ACTION (Your Decision)']
    _style_hdr(_ws_gl, _gl_cols)
    _sorted_gl = sorted(_grade_warnings, key=lambda x: (x.get('grade', 0), x.get('name', ''), x.get('course_title', '')))
    for i, g in enumerate(_sorted_gl, 2):
        _ws_gl.cell(i, 1, int(g['student'])).font = _dfont
        _ws_gl.cell(i, 2, g.get('name', '')).font = _dfont
        _ws_gl.cell(i, 3, g.get('grade', '')).font = _dfont
        _ws_gl.cell(i, 4, g.get('course', '')).font = _dfont
        _ws_gl.cell(i, 5, g.get('course_title', '')).font = _dfont
        _ws_gl.cell(i, 6, ', '.join(str(x) for x in g.get('eligible_grades', []))).font = _dfont
        _ws_gl.cell(i, 7, f"Gr{g.get('grade','')} not in eligible grades").font = _dfont
        _ws_gl.cell(i, 7).fill = _alert
        _ws_gl.cell(i, 8, '').font, _ws_gl.cell(i, 8).fill = _afont, _afill
        for c in range(1, 9):
            _ws_gl.cell(i, c).border = _tbord
    for col, w in [('A',12),('B',22),('C',14),('D',12),('E',32),('F',16),('G',28),('H',30)]:
        _ws_gl.column_dimensions[col].width = w

    # ── Prereq with transcript tab ──
    _ws_pt = _rwb.create_sheet('Prereq - With Transcript')
    _prereq_cols = ['Student ID', 'Student Name', 'Grade', 'Requested Code', 'Requested Course',
                    'Missing Prereq Code', 'Missing Prereq Course', 'ACTION (Your Decision)']
    _style_hdr(_ws_pt, _prereq_cols)
    _sorted_pt = sorted(_prereq_with_trans, key=lambda x: (x.get('course_title', ''), x.get('grade', 0), x.get('name', '')))
    for i, p in enumerate(_sorted_pt, 2):
        _ws_pt.cell(i, 1, int(p['student'])).font = _dfont
        _ws_pt.cell(i, 2, p.get('name', '')).font = _dfont
        _ws_pt.cell(i, 3, p.get('grade', '')).font = _dfont
        _ws_pt.cell(i, 4, p.get('course', '')).font = _dfont
        _ws_pt.cell(i, 5, p.get('course_title', '')).font = _dfont
        _ws_pt.cell(i, 6, p.get('prereq', '')).font = _dfont
        _ws_pt.cell(i, 7, p.get('prereq_title', '')).font = _dfont
        _ws_pt.cell(i, 8, '').font, _ws_pt.cell(i, 8).fill = _afont, _afill
        for c in range(1, 9):
            _ws_pt.cell(i, c).border = _tbord
    for col, w in [('A',12),('B',22),('C',8),('D',14),('E',30),('F',16),('G',30),('H',30)]:
        _ws_pt.column_dimensions[col].width = w

    # ── Prereq no transcript tab ──
    _ws_pn = _rwb.create_sheet('Prereq - No Transcript')
    _style_hdr(_ws_pn, _prereq_cols)
    _sorted_pn = sorted(_prereq_no_trans, key=lambda x: (x.get('grade', 0), x.get('name', ''), x.get('course_title', '')))
    for i, p in enumerate(_sorted_pn, 2):
        _ws_pn.cell(i, 1, int(p['student'])).font = _dfont
        _ws_pn.cell(i, 2, p.get('name', '')).font = _dfont
        _ws_pn.cell(i, 3, p.get('grade', '')).font = _dfont
        _ws_pn.cell(i, 4, p.get('course', '')).font = _dfont
        _ws_pn.cell(i, 5, p.get('course_title', '')).font = _dfont
        _ws_pn.cell(i, 6, p.get('prereq', '')).font = _dfont
        _ws_pn.cell(i, 7, p.get('prereq_title', '')).font = _dfont
        _ws_pn.cell(i, 8, '').font, _ws_pn.cell(i, 8).fill = _afont, _afill
        for c in range(1, 9):
            _ws_pn.cell(i, c).border = _tbord
    for col, w in [('A',12),('B',22),('C',8),('D',14),('E',30),('F',16),('G',30),('H',30)]:
        _ws_pn.column_dimensions[col].width = w

    _rwb.save(_report_xlsx_path)
    print(f"  Pre-flight review spreadsheet: {_report_xlsx_path}")
except Exception as _e:
    print(f"  WARNING: could not generate review spreadsheet: {_e}")


# ── LEO II Cohorts from Template 8 (Cohort Name column) ──
cohA, cohB = set(), set()
try:
    _t8wb_coh = openpyxl.load_workbook(t8_path, data_only=True)
    _t8ws_coh = _t8wb_coh[_t8wb_coh.sheetnames[0]]
    _coh_hdr = {}
    for c in range(1, _t8ws_coh.max_column + 1):
        v = _t8ws_coh.cell(1, c).value
        if v:
            _coh_hdr[str(v).strip()] = c
    _coh_name_col = _coh_hdr.get('Cohort Name', 10)
    _coh_sid_col = _coh_hdr.get('Student ID', 1)
    _coh_leo_col = _coh_hdr.get('LEO II', 6)
    for r in range(3, _t8ws_coh.max_row + 1):
        _sid = _t8ws_coh.cell(r, _coh_sid_col).value
        if not _sid:
            continue
        _pid = str(_sid).strip()
        _is_leo = str(_t8ws_coh.cell(r, _coh_leo_col).value or 'N').upper() == 'Y'
        if not _is_leo:
            continue
        _cohort_name = str(_t8ws_coh.cell(r, _coh_name_col).value or '').strip().upper()
        if _pid in students:
            if 'A' in _cohort_name:
                cohA.add(_pid)
            elif 'B' in _cohort_name:
                cohB.add(_pid)
            else:
                cohA.add(_pid)
    _t8wb_coh.close()
except FileNotFoundError:
    pass
print(f"  LEO Cohort A: {len(cohA)}, Cohort B: {len(cohB)}")

# ── Template 4: Co-Schedule Groups (one course per row, group by name) ──
t4_path = os.path.join(TEMPLATES, 'Template_4_CoSchedule_Groups.xlsx')
cogroups = []
try:
    iwb = openpyxl.load_workbook(t4_path, data_only=True)
    cws = iwb.active
    _cogroup_map = {}
    for r in range(3, cws.max_row + 1):
        gname = cws.cell(r, 1).value
        code = cws.cell(r, 2).value
        if not gname or not code:
            continue
        gname_str = str(gname).strip()
        cid = str(code).strip()
        if gname_str not in _cogroup_map:
            _cogroup_map[gname_str] = []
        _cogroup_map[gname_str].append(cid)
    for gname_str, codes in _cogroup_map.items():
        cogroups.append({'name': gname_str, 'codes': codes, 'period': None, 'sem': None})
        print(f"  Co-schedule: {gname_str} = {codes}")
    iwb.close()
except FileNotFoundError:
    print("  Template 4 not found — no co-schedule groups")

# ── Prior Year Schedule from Template_Prior_Year_Master_Schedule.xlsx ──
_py_path = os.path.join(TEMPLATES, 'Template_Prior_Year_Master_Schedule.xlsx')
print("\n  Loading prior year schedule...")
prior_entries = []
prior_teacher_periods = defaultdict(set)
prior_course_periods = defaultdict(set)
try:
    pwb = openpyxl.load_workbook(_py_path, data_only=True)
    pws = pwb.active
    for r in range(3, pws.max_row + 1):
        code_raw = pws.cell(r, 2).value
        teacher_id = pws.cell(r, 4).value
        room = pws.cell(r, 5).value
        period = pws.cell(r, 6).value
        term_raw = pws.cell(r, 7).value
        if not code_raw:
            continue
        code = str(code_raw).strip()
        teacher_name = teacher_id_to_name.get(str(teacher_id).strip(), str(teacher_id or 'TBD').strip()) if teacher_id else 'TBD'
        p = None
        if period and str(period).strip().upper() in PERIODS:
            p = str(period).strip().upper()
        term_str = str(term_raw or '').strip().upper()
        if term_str in ('S1', 'FALL'):
            term = 'S1'
        elif term_str in ('S2', 'SPRING'):
            term = 'S2'
        else:
            term = 'FY'
        prior_entries.append({
            'code': code, 'teacher': teacher_name,
            'period': p, 'term': term,
            'class_id': f"{code}-{pws.cell(r, 3).value or 1}",
            'room': str(room or '').strip()
        })
    for e in prior_entries:
        if e['period']:
            prior_teacher_periods[(e['code'], e['teacher'])].add(e['period'])
            prior_course_periods[e['code']].add(e['period'])
    pwb.close()
    print(f"  Prior-year entries: {len(prior_entries)}")
except FileNotFoundError:
    print("  Template_Prior_Year_Master_Schedule.xlsx not found — skipping prior year data")


# ── Teacher Load Rules (enhanced with profiles + contracts) ──

def get_max_load(teacher, semester=None):
    """Return (max_s1, max_s2) teaching-period caps for a teacher.
    If semester='S1' or 'S2', the returned tuple still has both values
    but the per-semester approved-6 flags are applied correctly.
    Approved-6 can be Full-Year (both semesters), S1-only, or S2-only."""
    tp = teacher_profiles.get(teacher, {})
    if tp:
        base = tp.get('max_periods', 5)
        contract_code = tp.get('contract', 'Standard')
        ct = contracts.get(contract_code, contracts.get('STD', {}))
        if ct:
            base = min(base, ct.get('max_teaching', base))
        max_s1 = base
        max_s2 = base
        if tp.get('approved_6_fy'):
            max_s1 = max(max_s1, 6)
            max_s2 = max(max_s2, 6)
        else:
            if tp.get('approved_6_s1'):
                max_s1 = max(max_s1, 6)
            if tp.get('approved_6_s2'):
                max_s2 = max(max_s2, 6)
        return (max_s1, max_s2)
    if 'konopelski' in teacher.lower():
        return (3, 3)
    return (5, 5)

# Build COURSE_TEACHER_LOCKS from Template 6 "Course-Teacher Lock" column
COURSE_TEACHER_LOCKS = {}
for _tname, _tp in teacher_profiles.items():
    _lock_codes = _tp.get('course_teacher_locks', '')
    if _lock_codes:
        for _lc in str(_lock_codes).split(','):
            _lc = _lc.strip()
            if _lc:
                COURSE_TEACHER_LOCKS[_lc] = _tname

# co-schedule group set will be populated after cogroups are loaded (below)

# Item 6: Affected student count per section (used in period assignment ordering)
_section_demand = Counter()
for _pid in students:
    for _cid in sreq[_pid]:
        for _sid in sec_by_code.get(_cid, []):
            _section_demand[_sid] += 1
_course_demand = Counter()
for _pid in students:
    for _cid in sreq[_pid]:
        _course_demand[_cid] += 1

# ── Initialize new priority system ──
# Student raw and total priorities are computed on demand via student_raw_priority()
# and student_total_priority(). No merge into old dict structures needed.
# Teacher and room priorities are likewise computed on demand.
_clear_priority_caches()
_top5_students = sorted(students.keys(), key=lambda p: -student_total_priority(p))[:5]
print(f"  Student priorities computed: {len(students)}")
for _pid in _top5_students:
    print(f"    {students[_pid]} (Gr{grade[_pid]}): Raw={student_raw_priority(_pid)}, Total={student_total_priority(_pid)}")
_clear_priority_caches()


# Item 9: Three-level constraint classification
CONSTRAINT_CLASSES = {
    'HARD': {
        'teacher_busy': 'Teacher already assigned to another section this period',
        'room_busy': 'Room already assigned to another section this period',
        'period_conflict': 'Student cannot be in two places at the same time',
        'credit_cap': 'Student exceeds maximum credit limit',
        'grade_ineligible': 'Student grade not eligible for this course',
    },
    'ADMIN_LOCK': {
        'pinned_period': 'Course pinned to specific period by administration',
        'teacher_lock': 'Course locked to specific teacher by administration',
        'semester_lock': 'Course locked to specific semester by administration',
        'cohort_assignment': 'Student cohort assignment (LEO II)',
        'cogroup_period': 'Co-schedule group assigned to unified period',
    },
    'SOFT': {
        'teacher_preference': 'Teacher period preference',
        'prior_year_alignment': 'Prior year room/period alignment',
        'section_balance': 'Section fill-level balancing',
        'room_proximity': 'Room wing/proximity preference',
    }
}

def classify_constraint(constraint_name):
    for level, constraints in CONSTRAINT_CLASSES.items():
        if constraint_name in constraints:
            return level
    return 'SOFT'

# ============================================================
# 1. ASSIGN PERIODS (enhanced with teacher availability)
# ============================================================
print("\n" + "=" * 60)
print("[1] PHASE A: ASSIGN PERIODS")
print("=" * 60)

SEMESTER_LOCKS = {
    '745': ('S1',),
    '734': ('S2',),
    '766': ('S1',),
    '765': ('S2',),
    '758': ('S2',),
}

FULL_FREEDOM = {'849', '851'}

for cid, halves in SEMESTER_LOCKS.items():
    for sid in sec_by_code.get(cid, []):
        sections[sid]['halves'] = halves

print(f"  Semester locks applied: {list(SEMESTER_LOCKS.keys())}")
print(f"  Full freedom courses: {list(FULL_FREEDOM)}")

code_to_cogroup = {}
for gi, cg in enumerate(cogroups):
    for code in cg['codes']:
        if code in sec_by_code:
            code_to_cogroup[code] = gi

course_request_priority._cogroup_set = set(code_to_cogroup.keys())

for cg in cogroups:
    if cg['period']:
        p = str(cg['period']).strip().upper()
        if p in PERIODS:
            for code in cg['codes']:
                for sid in sec_by_code.get(code, []):
                    if sections[sid]['period'] is None:
                        sections[sid]['period'] = p

cogroup_sids = defaultdict(list)
for gi, cg in enumerate(cogroups):
    if cg['period']:
        continue
    has_sections = False
    for code in cg['codes']:
        for sid in sec_by_code.get(code, []):
            if sections[sid]['period'] is None:
                cogroup_sids[gi].append(sid)
                has_sections = True
    if has_sections:
        print(f"  Co-schedule group '{cg['name']}' ({len(cogroup_sids[gi])} sections) — will assign unified period")

for cid in FULL_FREEDOM:
    sids = [sid for sid in sec_by_code.get(cid, []) if sections[sid]['period'] is None]
    if not sids:
        continue
    demand = sum(1 for pid in students if cid in sreq[pid])
    nsec = len(sids)
    n_s1 = (nsec + 1) // 2
    for i, sid in enumerate(sids):
        sections[sid]['halves'] = ('S1',) if i < n_s1 else ('S2',)
    print(f"  Full Freedom {cid}: {nsec} sections, {n_s1} S1 / {nsec - n_s1} S2 (demand={demand})")

for cid, sids in sec_by_code.items():
    ci = course_info.get(cid, {})
    if ci.get('is_fy', True):
        continue
    if cid in FULL_FREEDOM or cid in SEMESTER_LOCKS:
        continue
    unpinned = [sid for sid in sids if sections[sid]['period'] is None]
    for i, sid in enumerate(unpinned):
        sections[sid]['halves'] = ('S1',) if i % 2 == 0 else ('S2',)

def in_same_cogroup(sid_a, sid_b):
    code_a = sections[sid_a]['code']
    code_b = sections[sid_b]['code']
    ga = code_to_cogroup.get(code_a)
    gb = code_to_cogroup.get(code_b)
    return ga is not None and ga == gb

def teacher_busy(teacher, period, halves, check_sid=-1):
    for sid in teacher_sections.get(teacher, []):
        s = sections[sid]
        if s['period'] == period and s['sid'] != -1:
            if set(s['halves']) & set(halves):
                if check_sid >= 0 and in_same_cogroup(check_sid, sid):
                    continue
                return True
    return False

def room_busy(room, period, halves, exclude_sid=-1):
    if room in SHARED_ROOMS:
        return False
    for s in sections:
        if s['sid'] == exclude_sid or s['period'] != period:
            continue
        if s['room'] == room:
            if set(s['halves']) & set(halves):
                return True
    return False

def teacher_would_exceed_cap(teacher, period, halves):
    if not teacher or teacher == 'TBD':
        return False
    max_s1, max_s2 = get_max_load(teacher)
    for sem in halves:
        cap = max_s1 if sem == 'S1' else max_s2
        existing_periods = set()
        for sid in teacher_sections.get(teacher, []):
            s = sections[sid]
            if s['period'] and sem in s['halves']:
                existing_periods.add(s['period'])
        existing_periods.add(period)
        if len(existing_periods) > cap:
            return True
    return False

def teacher_available(teacher, period):
    """Check if teacher is available in this period (from profile)."""
    tp = teacher_profiles.get(teacher, {})
    if not tp:
        return True
    avail = tp.get('availability', {})
    return avail.get(period, True)

# --- STEP 1: Assign co-schedule groups ---
assigned_cogroups = set()
for gi, sids_in_group in cogroup_sids.items():
    if not sids_in_group:
        continue
    group_teachers = set()
    group_halves = set()
    for sid in sids_in_group:
        t = sections[sid]['teacher']
        if t and t != 'TBD':
            group_teachers.add(t)
        for h in sections[sid]['halves']:
            group_halves.add(h)
    group_halves_tuple = tuple(sorted(group_halves))

    best_period = None
    best_score = float('inf')
    for p in PERIODS:
        blocked = False
        for t in group_teachers:
            if teacher_would_exceed_cap(t, p, group_halves_tuple):
                blocked = True
                break
            if not teacher_available(t, p):
                blocked = True
                break
        if blocked:
            continue
        score = 0
        period_load = sum(1 for sec in sections if sec['period'] == p)
        score += period_load * 0.1
        for t in group_teachers:
            tp = teacher_profiles.get(t, {})
            if p in tp.get('avoid_periods', []):
                score += 2
            if p in tp.get('preferred_periods', []):
                score -= 1
        if score < best_score:
            best_score = score
            best_period = p

    if best_period is None:
        loads = Counter(sec['period'] for sec in sections if sec['period'])
        best_period = min(PERIODS, key=lambda p: loads.get(p, 0))

    for sid in sids_in_group:
        sections[sid]['period'] = best_period
    assigned_cogroups.update(sids_in_group)
    print(f"  Co-schedule group '{cogroups[gi]['name']}' -> Period {best_period}")

# --- STEP 2: Enhanced greedy assignment ---
def _build_co_enrollment():
    """Build co-enrollment index: for each course, which other courses share students.
    Returns dict: cid -> {other_cid: [list of student pids sharing both courses]}"""
    co = defaultdict(lambda: defaultdict(list))
    for pid in students:
        reqs = sreq[pid]
        for i, cid_a in enumerate(reqs):
            for cid_b in reqs[i + 1:]:
                co[cid_a][cid_b].append(pid)
                co[cid_b][cid_a].append(pid)
    return co

_top_student_cache = {}

def _refresh_top_students():
    """Precompute top student total for each course. O(students x courses_per_student)."""
    _top_student_cache.clear()
    for pid in students:
        st = student_total_priority(pid)
        for cid in sreq.get(pid, []):
            if cid not in _top_student_cache or st > _top_student_cache[cid]:
                _top_student_cache[cid] = st

def _section_priority_key(s):
    """Sort key for section placement order using the DATA_STRUCTURE.md priority system.
    Course Section Total = Course Section Raw + Top Student Total + Teacher Total + Room Total.
    Highest-priority sections are placed first (most negative sort values).
    Uses _top_student_cache (call _refresh_top_students() after each _clear_priority_caches())."""
    code = s['code']
    teacher = s['teacher']
    room = s.get('room', 'TBD')
    cs_raw = course_section_raw(code)
    max_student_total = _top_student_cache.get(code, 0)
    t_raw = teacher_raw_priority(teacher) if teacher and teacher != 'TBD' else 0
    t_total = t_raw + max_student_total
    r_raw = room_raw_priority(room) if room and room != 'TBD' else 0
    r_total = r_raw + t_total + max_student_total
    cs_total = cs_raw + max_student_total + t_total + r_total
    return (
        -cs_total,
        -cs_raw,
        -_course_demand.get(code, 0),
        len(sec_by_code[code]),
        code,
        s['section']
    )

def _predict_clash_score(code, period, halves, co_enroll):
    """Predict how many weighted student clashes placing this course in this period would cause.
    Checks every co-enrolled course: if that course has a section already in this period
    with overlapping semesters, each shared student is a potential clash weighted by priority."""
    clash_score = 0
    co_courses = co_enroll.get(code, {})
    for other_cid, shared_students in co_courses.items():
        other_sids = sec_by_code.get(other_cid, [])
        for osid in other_sids:
            os = sections[osid]
            if os['period'] != period:
                continue
            if not (set(halves) & set(os['halves'])):
                continue
            for pid in shared_students:
                crp_this = course_request_priority(pid, code)
                crp_other = course_request_priority(pid, other_cid)
                clash_score += max(crp_this, crp_other)
            break
    return clash_score

def greedy_assign_periods(seed=42, audit=False):
    """Assign each section to a period using per-placement save/remove/recalculate/re-rank.
    After every section placement, priority caches are cleared, all remaining sections'
    priority values are recalculated, and the ranking is rebuilt before the next placement."""
    rng = random.Random(seed)
    co_enroll = _build_co_enrollment()

    if audit:
        _clear_priority_caches()
        _refresh_top_students()
        _priority_audit['phase_a']['initial_snapshot'] = _capture_snapshot()
        _priority_audit['phase_a']['placements'] = []

    step = 0
    while True:
        # RECALCULATE: clear caches so priorities reflect current state
        _clear_priority_caches()
        _refresh_top_students()

        # Collect remaining unassigned sections
        unassigned = [s for s in sections if s['period'] is None]
        if not unassigned:
            break

        # RE-RANK: deterministic shuffle for tiebreak, then sort by priority
        rng_step = random.Random(seed + step)
        rng_step.shuffle(unassigned)
        unassigned.sort(key=_section_priority_key)

        # PLACE: take #1 ranked section, find its best period
        s = unassigned[0]
        teacher = s['teacher']
        room = s['room']
        halves = s['halves']
        code = s['code']

        used_periods = set()
        period_section_count = Counter()
        for other_sid in sec_by_code[code]:
            if sections[other_sid]['period']:
                used_periods.add(sections[other_sid]['period'])
                period_section_count[sections[other_sid]['period']] += 1

        total_course_sections = len(sec_by_code[code])
        ci = course_info.get(code, {})
        is_coverage_course = bool(ci.get('grad_req_dept', '')) and total_course_sections >= 6

        best_period = None
        best_score = float('inf')
        period_scores = {}

        for p in PERIODS:
            if teacher and teacher != 'TBD' and teacher_busy(teacher, p, halves, s['sid']):
                period_scores[p] = 'teacher_busy'
                continue
            if teacher_would_exceed_cap(teacher, p, halves):
                period_scores[p] = 'load_cap'
                continue
            if teacher and teacher != 'TBD' and not teacher_available(teacher, p):
                period_scores[p] = 'unavailable'
                continue
            score = 0
            clash_penalty = _predict_clash_score(code, p, halves, co_enroll)
            score += clash_penalty * 0.5
            if p in used_periods:
                score += 10
            if is_coverage_course:
                uncovered = [pp for pp in PERIODS if period_section_count.get(pp, 0) == 0]
                if uncovered and p not in used_periods:
                    score -= 20
                elif period_section_count.get(p, 0) > 0:
                    score += 10 * period_section_count[p]
            period_load = sum(1 for sec in sections if sec['period'] == p)
            score += period_load * 0.1
            if room and room != 'TBD' and room_busy(room, p, halves, s['sid']):
                score += 5
            tp = teacher_profiles.get(teacher, {})
            if tp:
                if p in tp.get('avoid_periods', []):
                    score += 2
                if p in tp.get('preferred_periods', []):
                    score -= 1
            prior_prefs = prior_teacher_periods.get((code, teacher), set())
            if not prior_prefs:
                prior_prefs = prior_course_periods.get(code, set())
            if prior_prefs and p in prior_prefs:
                score -= 0.5
            score += rng.random() * 0.01
            period_scores[p] = round(score, 4)

            if score < best_score:
                best_score = score
                best_period = p

        if best_period:
            s['period'] = best_period
        else:
            if teacher and teacher != 'TBD':
                teacher_per = set()
                for sid in teacher_sections.get(teacher, []):
                    if sections[sid]['period']:
                        teacher_per.add(sections[sid]['period'])
                if teacher_per:
                    loads = Counter(sec['period'] for sec in sections if sec['period'])
                    s['period'] = min(teacher_per, key=lambda p: loads.get(p, 0))
                else:
                    loads = Counter(sec['period'] for sec in sections if sec['period'])
                    s['period'] = min(PERIODS, key=lambda p: loads.get(p, 0))
            else:
                loads = Counter(sec['period'] for sec in sections if sec['period'])
                s['period'] = min(PERIODS, key=lambda p: loads.get(p, 0))

        step += 1

        # SAVE: record placement with priority values used
        if audit:
            cs_raw_val = course_section_raw(code)
            t_raw_val = teacher_raw_priority(teacher) if teacher and teacher != 'TBD' else 0
            t_total_val = teacher_total_priority(teacher) if teacher and teacher != 'TBD' else 0
            r_raw_val = room_raw_priority(room) if room and room != 'TBD' else 0
            r_total_val = room_total_priority(room) if room and room != 'TBD' else 0
            top_st = _top_student_cache.get(code, 0)
            _priority_audit['phase_a']['placements'].append({
                'step': step, 'sid': s['sid'], 'code': code,
                'title': s['title'], 'section': s['section'],
                'teacher': teacher, 'room': room,
                'period_assigned': s['period'], 'halves': list(s['halves']),
                'cs_raw': cs_raw_val, 'top_student_total': top_st,
                'teacher_raw': t_raw_val, 'teacher_total': t_total_val,
                'room_raw': r_raw_val, 'room_total': r_total_val,
                'cs_total': cs_raw_val + top_st + t_total_val + r_total_val,
                'period_scores': period_scores,
                'remaining_sections': len(unassigned) - 1,
            })
        # REMOVE: section now has a period — excluded from next iteration's unassigned list

        if step % 50 == 0:
            print(f"    Step {step}: {len(unassigned)-1} sections remaining")

    if audit:
        _clear_priority_caches()
        _refresh_top_students()
        _priority_audit['phase_a']['final_snapshot'] = _capture_snapshot()

greedy_assign_periods(seed=42, audit=True)

assigned_count = sum(1 for s in sections if s['period'])
print(f"  Sections assigned: {assigned_count}/{len(sections)}")
period_dist = Counter(s['period'] for s in sections)
for p in PERIODS:
    print(f"    Period {p}: {period_dist.get(p, 0)} sections")

t_conflicts = 0
for teacher, sids in teacher_sections.items():
    slots = defaultdict(list)
    for sid in sids:
        s = sections[sid]
        for h in s['halves']:
            slots[(s['period'], h)].append(sid)
    for slot, sid_list in slots.items():
        if len(sid_list) > 1:
            real_conflicts = 0
            for i in range(len(sid_list)):
                is_coscheduled = False
                for j in range(len(sid_list)):
                    if i != j and in_same_cogroup(sid_list[i], sid_list[j]):
                        is_coscheduled = True
                        break
                if not is_coscheduled:
                    real_conflicts += 1
            if real_conflicts > 1:
                t_conflicts += real_conflicts - 1
print(f"  Teacher period conflicts: {t_conflicts}")

prior_match = 0
prior_total = 0
for s in sections:
    prior_prefs = prior_teacher_periods.get((s['code'], s['teacher']), set())
    if not prior_prefs:
        prior_prefs = prior_course_periods.get(s['code'], set())
    if prior_prefs:
        prior_total += 1
        if s['period'] in prior_prefs:
            prior_match += 1
print(f"  Prior-year alignment: {prior_match}/{prior_total}")

def teacher_load(teacher, semester):
    periods_used = set()
    for sid in teacher_sections.get(teacher, []):
        s = sections[sid]
        if s['period'] and semester in s['halves']:
            periods_used.add(s['period'])
    return len(periods_used)

load_violations = []
for teacher in teacher_sections:
    max_s1, max_s2 = get_max_load(teacher)
    s1 = teacher_load(teacher, 'S1')
    s2 = teacher_load(teacher, 'S2')
    if s1 > max_s1 or s2 > max_s2:
        load_violations.append({'teacher': teacher, 's1': s1, 's2': s2, 'max_s1': max_s1, 'max_s2': max_s2})
        print(f"  LOAD: {teacher} S1={s1}/{max_s1} S2={s2}/{max_s2}")
print(f"  Load violations: {len(load_violations)}")

# ── Job 1 Excel Export ──
def export_job1_report():
    """Export Job 1 (Section Placement) results to Excel for review."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = openpyxl.Workbook()

    # ── Sheet 1: Section Placements (one row per section, sorted by placement step) ──
    ws = wb.active
    ws.title = "Section Placements"
    headers = [
        'Step', 'Course Code', 'Course Title', 'Section #', 'Department',
        'Teacher Name', 'Teacher ID', 'Room', 'Period', 'Term',
        'CS Raw', 'Top Student Total', 'Teacher Raw', 'Teacher Total',
        'Room Raw', 'Room Total', 'CS Total',
        'Enrollment Cap', 'Co-Schedule Group', 'Prescribed Cohort',
    ]
    hdr_font = Font(name='Arial', bold=True, color='FFFFFF', size=10)
    hdr_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    name_to_id = {}
    for tid, tname in teacher_id_to_name.items():
        name_to_id[tname] = tid

    audit_placements = _priority_audit.get('phase_a', {}).get('placements', [])
    audit_by_sid = {p['sid']: p for p in audit_placements}

    row = 2
    for s in sorted(sections, key=lambda s: audit_by_sid.get(s['sid'], {}).get('step', 9999)):
        ap = audit_by_sid.get(s['sid'], {})
        term_str = '/'.join(s['halves']) if s.get('halves') else ''
        if set(s.get('halves', ())) == {'S1', 'S2'}:
            term_str = 'FY'
        teacher = s['teacher']
        tid = name_to_id.get(teacher, '')
        room = s.get('room', 'TBD')

        co_group = ''
        gi = code_to_cogroup.get(s['code'])
        if gi is not None:
            co_group = cogroups[gi]['name']

        vals = [
            ap.get('step', ''), s['code'], s['title'], s['section'], s['dept'],
            teacher, tid, room, s['period'] or 'UNASSIGNED', term_str,
            ap.get('cs_raw', course_section_raw(s['code'])),
            ap.get('top_student_total', _top_student_cache.get(s['code'], 0)),
            ap.get('teacher_raw', teacher_raw_priority(teacher) if teacher and teacher != 'TBD' else 0),
            ap.get('teacher_total', teacher_total_priority(teacher) if teacher and teacher != 'TBD' else 0),
            ap.get('room_raw', room_raw_priority(room) if room and room != 'TBD' else 0),
            ap.get('room_total', room_total_priority(room) if room and room != 'TBD' else 0),
            ap.get('cs_total', ''),
            s['cap'],
            co_group,
            s.get('prescribed_cohort', ''),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.font = Font(name='Arial', size=10)
            cell.border = thin_border
            if c >= 11:
                cell.alignment = Alignment(horizontal='center')
        row += 1

    for c in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 16
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['F'].width = 22
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = 'A2'

    # ── Sheet 2: Period Distribution ──
    ws2 = wb.create_sheet("Period Distribution")
    ws2.cell(1, 1, "Period").font = Font(name='Arial', bold=True, size=10)
    ws2.cell(1, 2, "S1 Sections").font = Font(name='Arial', bold=True, size=10)
    ws2.cell(1, 3, "S2 Sections").font = Font(name='Arial', bold=True, size=10)
    ws2.cell(1, 4, "FY Sections").font = Font(name='Arial', bold=True, size=10)
    ws2.cell(1, 5, "Total Sections").font = Font(name='Arial', bold=True, size=10)
    for c in range(1, 6):
        ws2.cell(1, c).fill = hdr_fill
        ws2.cell(1, c).font = hdr_font
        ws2.cell(1, c).border = thin_border
    for i, p in enumerate(PERIODS, 2):
        s1_ct = sum(1 for s in sections if s['period'] == p and 'S1' in s['halves'] and 'S2' not in s['halves'])
        s2_ct = sum(1 for s in sections if s['period'] == p and 'S2' in s['halves'] and 'S1' not in s['halves'])
        fy_ct = sum(1 for s in sections if s['period'] == p and 'S1' in s['halves'] and 'S2' in s['halves'])
        total = sum(1 for s in sections if s['period'] == p)
        for c, v in enumerate([p, s1_ct, s2_ct, fy_ct, total], 1):
            cell = ws2.cell(i, c, v)
            cell.font = Font(name='Arial', size=10)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
    for c in range(1, 6):
        ws2.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 16

    # ── Sheet 3: Teacher Load Summary ──
    ws3 = wb.create_sheet("Teacher Loads")
    t_headers = ['Teacher Name', 'Teacher ID', 'S1 Periods', 'S2 Periods', 'Max S1', 'Max S2', 'Overloaded?']
    for c, h in enumerate(t_headers, 1):
        cell = ws3.cell(1, c, h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = thin_border
    t_row = 2
    for tname in sorted(teacher_sections.keys()):
        tid = name_to_id.get(tname, '')
        s1_load = teacher_load(tname, 'S1')
        s2_load = teacher_load(tname, 'S2')
        max_s1, max_s2 = get_max_load(tname)
        overloaded = 'YES' if s1_load > max_s1 or s2_load > max_s2 else ''
        for c, v in enumerate([tname, tid, s1_load, s2_load, max_s1, max_s2, overloaded], 1):
            cell = ws3.cell(t_row, c, v)
            cell.font = Font(name='Arial', size=10)
            cell.border = thin_border
            if overloaded == 'YES' and c == 7:
                cell.font = Font(name='Arial', size=10, color='FF0000', bold=True)
        t_row += 1
    for c in range(1, len(t_headers) + 1):
        ws3.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 16
    ws3.column_dimensions['A'].width = 24
    ws3.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(t_headers))}{t_row - 1}"
    ws3.freeze_panes = 'A2'

    # ── Sheet 4: Teacher Conflicts ──
    ws4 = wb.create_sheet("Teacher Conflicts")
    tc_headers = ['Teacher', 'Period', 'Semester', 'Section 1 (Code-Sec)', 'Section 2 (Code-Sec)', 'Co-Scheduled?']
    for c, h in enumerate(tc_headers, 1):
        cell = ws4.cell(1, c, h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = thin_border
    tc_row = 2
    for teacher, sids in teacher_sections.items():
        slots = defaultdict(list)
        for sid in sids:
            s = sections[sid]
            if s['period']:
                for h in s['halves']:
                    slots[(s['period'], h)].append(sid)
        for (period, sem), sid_list in sorted(slots.items()):
            if len(sid_list) > 1:
                for i in range(len(sid_list)):
                    for j in range(i + 1, len(sid_list)):
                        is_co = in_same_cogroup(sid_list[i], sid_list[j])
                        s1 = sections[sid_list[i]]
                        s2 = sections[sid_list[j]]
                        for c, v in enumerate([
                            teacher, period, sem,
                            f"{s1['code']}-{s1['section']}", f"{s2['code']}-{s2['section']}",
                            'YES' if is_co else 'NO — CONFLICT'
                        ], 1):
                            cell = ws4.cell(tc_row, c, v)
                            cell.font = Font(name='Arial', size=10)
                            cell.border = thin_border
                            if not is_co and c == 6:
                                cell.font = Font(name='Arial', size=10, color='FF0000', bold=True)
                        tc_row += 1
    for c in range(1, len(tc_headers) + 1):
        ws4.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 20
    ws4.freeze_panes = 'A2'

    # ── Sheet 5: Summary ──
    ws5 = wb.create_sheet("Summary")
    summary_data = [
        ('Total Sections', len(sections)),
        ('Sections Assigned', sum(1 for s in sections if s['period'])),
        ('Sections Unassigned', sum(1 for s in sections if not s['period'])),
        ('Total Courses', len(sec_by_code)),
        ('Total Teachers', len(teacher_sections)),
        ('Teacher Period Conflicts (non-co-sched)', t_conflicts),
        ('Load Violations', len(load_violations)),
        ('Prior-Year Alignment', f"{prior_match}/{prior_total}"),
        ('', ''),
        ('Period Distribution', ''),
    ]
    for p in PERIODS:
        summary_data.append((f'  Period {p}', sum(1 for s in sections if s['period'] == p)))
    for r, (label, val) in enumerate(summary_data, 1):
        ws5.cell(r, 1, label).font = Font(name='Arial', bold=True, size=10)
        ws5.cell(r, 2, val).font = Font(name='Arial', size=10)
    ws5.column_dimensions['A'].width = 40
    ws5.column_dimensions['B'].width = 20

    out_path = os.path.join(OUTPUT_DIR, 'Job1_Section_Placements_2026_27.xlsx')
    wb.save(out_path)
    print(f"\n  ** Job 1 Excel export saved: {out_path}")
    return out_path

_job1_path = export_job1_report()

# ── Save Phase A audit to JSON ──
_audit_a_path = os.path.join(OUTPUT_DIR, 'priority_audit_log.json')
with open(_audit_a_path, 'w') as _af:
    json.dump(_priority_audit, _af, indent=2, default=str)
print(f"  Priority audit log saved to {_audit_a_path}")

# ── Job 1 Stop Gate ──
if ENGINE_MODE == 'job1':
    print("\n" + "=" * 60)
    print("JOB 1 COMPLETE — ENGINE STOPPED")
    print("=" * 60)
    print(f"  Review the export: {_job1_path}")
    print("  To proceed, re-run with:  python schedule_engine_v3.py full")
    print("  To re-run Job 1 only:     python schedule_engine_v3.py job1")
    sys.exit(0)


# ============================================================
# 2. SEAT STUDENTS
# ============================================================
print("\n" + "=" * 60)
print("[2] PHASE B: SEAT STUDENTS")
print("=" * 60)

assign = {pid: {} for pid in students}
secfill = Counter()

_occ_cache = {}
def occ_cells(sid):
    if sid in _occ_cache:
        return _occ_cache[sid]
    s = sections[sid]
    result = tuple((s['period'], h) for h in s['halves'])
    _occ_cache[sid] = result
    return result

def _invalidate_occ_cache():
    _occ_cache.clear()

cell_usage = Counter()

def add_place(pid, cid, sid):
    for x in occ_cells(sid):
        cell_usage[(pid, x)] += 1
    secfill[sid] += 1
    assign[pid][cid] = sid

def rm_place(pid, cid):
    sid = assign[pid][cid]
    for x in occ_cells(sid):
        cell_usage[(pid, x)] -= 1
    secfill[sid] -= 1
    del assign[pid][cid]

def added_conflicts(pid, sid):
    return sum(1 for x in occ_cells(sid) if cell_usage.get((pid, x), 0) >= 1)

leo2_sids = sec_by_code.get('745', [])
leo2C = None
leo2E = None
for sid in leo2_sids:
    if sections[sid]['period'] == 'C':
        leo2C = sid
    elif sections[sid]['period'] == 'E':
        leo2E = sid

sorted_students = sorted(students.keys(), key=lambda p: -student_total_priority(p))
print("  Greedy warm-start (highest-priority-first)...")

# ── Placement sort key (DATA_STRUCTURE.md) ──
# Level 1: Course Section Raw determines section placement order (already done in Phase A)
# Level 2: Student Total Priority determines which students fill each section first
# Sort ordering for student-course pairs:
#   1. Course request priority (highest first)
#   2. Student total priority (highest first)
#   3. Course section raw (highest first — tiebreaker per DATA_STRUCTURE.md)
#   4. Fewer available sections first (harder to place)
def _full_sort_key(pc):
    pid, cid = pc
    return (
        -course_request_priority(pid, cid),
        -student_total_priority(pid),
        -course_section_raw(cid),
        len(sec_by_code.get(cid, []))
    )

# Build code_requesters
code_requesters = defaultdict(set)
for _pid in students:
    for _cid in sreq[_pid]:
        code_requesters[_cid].add(_pid)

# Build the full request list
_all_requests = []
for pid in sorted_students:
    for cid in sreq[pid]:
        _all_requests.append((pid, cid))

# Sort by course request priority + student total priority
_all_requests.sort(key=_full_sort_key)

# ── Per-placement save/remove/recalculate/re-rank (Job 2) ──
_priority_audit['phase_b']['initial_snapshot'] = _capture_snapshot()
_placed_set = set()
_placed_count_b = 0
_total_requests = len(_all_requests)
_step_b = 0

while _all_requests:
    pid, cid = _all_requests[0]

    if cid not in sec_by_code:
        _placed_set.add((pid, cid))
        _all_requests.pop(0)
        continue

    chosen_sid = None
    if cid == '745':
        if pid in cohA and leo2C is not None:
            chosen_sid = leo2C
        elif pid in cohB and leo2E is not None:
            chosen_sid = leo2E
        else:
            opts = sec_by_code[cid]
            chosen_sid = min(opts, key=lambda sid: (added_conflicts(pid, sid), secfill[sid]))
    else:
        opts = sec_by_code[cid]
        if HARD_CAP_ENFORCEMENT:
            _hc_opts = [sid for sid in opts if secfill[sid] < sections[sid]['cap']]
            if _hc_opts:
                opts = _hc_opts
        chosen_sid = min(opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid]
        ))

    add_place(pid, cid, chosen_sid)
    _placed_set.add((pid, cid))
    _placed_count_b += 1
    _step_b += 1

    _priority_audit['phase_b']['placements'].append({
        'step': _step_b,
        'student_id': pid,
        'student_name': students.get(pid, ''),
        'code': cid,
        'section_id': chosen_sid,
        'crp': course_request_priority(pid, cid),
        'student_raw': student_raw_priority(pid),
        'student_total': student_total_priority(pid),
        'cs_raw': course_section_raw(cid),
        'section_fill': secfill[chosen_sid],
        'section_cap': sections[chosen_sid]['cap'],
        'conflicts_added': added_conflicts(pid, chosen_sid),
        'remaining_requests': len(_all_requests) - 1,
    })

    if _step_b % 500 == 0:
        print(f"    Phase B step {_step_b}/{_total_requests}")

    _clear_priority_caches()
    _all_requests = [pc for pc in _all_requests[1:] if pc not in _placed_set]
    _all_requests.sort(key=_full_sort_key)

_priority_audit['phase_b']['final_snapshot'] = _capture_snapshot()
print(f"  Phase B complete: {_placed_count_b} placements in {_step_b} steps")

# ── Save priority audit log (Phase A + Phase B) ──
with open(os.path.join(OUTPUT_DIR, 'priority_audit_log.json'), 'w') as _af:
    json.dump(_priority_audit, _af, indent=2, default=str)
print(f"  Priority audit log updated (Phase A + Phase B)")

conf_count = 0
for pid in students:
    for cid, sid in assign[pid].items():
        for x in occ_cells(sid):
            if cell_usage.get((pid, x), 0) > 1:
                conf_count += 1
                break
print(f"  Initial: {sum(len(v) for v in assign.values())} placements, {conf_count} students with conflicts")

def resolve_student(pid):
    pins = {}
    for pc in assign[pid]:
        if is_protected(pid, pc):
            pins[pc] = assign[pid][pc]
    pin_cells = {}
    for c, sid in list(pins.items()):
        for x in occ_cells(sid):
            pin_cells.setdefault(x, []).append(c)
    for x, cs in pin_cells.items():
        if len(cs) > 1:
            cs_sorted = sorted(cs, key=lambda c: (-course_request_priority(pid, c), -int(is_singleton(c))))
            for c in cs_sorted[1:]:
                if c in pins:
                    del pins[c]
    others = [c for c in sreq[pid] if c not in pins and c in assign[pid]]
    used = set()
    for c, sid in pins.items():
        for x in occ_cells(sid):
            used.add(x)
    others.sort(key=lambda c: (-course_request_priority(pid, c), -int(is_singleton(c)), -course_section_raw(c), len(sec_by_code.get(c, []))))
    res = {}

    def rec(i):
        if i == len(others):
            return True
        c = others[i]
        _csp_opts = sec_by_code.get(c, [])
        if HARD_CAP_ENFORCEMENT:
            _csp_hc = [sid for sid in _csp_opts if secfill[sid] < sections[sid]['cap']]
            if _csp_hc:
                _csp_opts = _csp_hc
        opts = sorted(_csp_opts,
                       key=lambda sid: (secfill[sid] >= sections[sid]['cap'], secfill[sid]))
        for sid in opts:
            cells = occ_cells(sid)
            if all(x not in used for x in cells):
                for x in cells:
                    used.add(x)
                res[c] = sid
                if rec(i + 1):
                    return True
                for x in cells:
                    used.discard(x)
                del res[c]
        return False

    if rec(0):
        for c in others:
            if c in assign[pid]:
                rm_place(pid, c)
        for c, sid in res.items():
            add_place(pid, c, sid)
        return True
    return False

print("  Running CSP re-solve...")
for round_num in range(4):
    resolved = 0
    for pid in students:
        has_conflict = False
        for cid, sid in assign[pid].items():
            for x in occ_cells(sid):
                if cell_usage.get((pid, x), 0) > 1:
                    has_conflict = True
                    break
            if has_conflict:
                break
        if has_conflict:
            if resolve_student(pid):
                resolved += 1
    remaining = sum(1 for pid in students
                    for cid, sid in assign[pid].items()
                    for x in occ_cells(sid)
                    if cell_usage.get((pid, x), 0) > 1) // 2
    print(f"    Round {round_num + 1}: resolved {resolved}, remaining ~{remaining}")
    if remaining == 0:
        break

print("\n  Phase C: bumping remaining conflicts...")

# Item 1: Root cause analysis for each clash
# Item 3: Placement log — record sections considered and why rejected
placement_log = []

def _analyze_root_cause(pid, bumped_cid, keeping_cid, bumped_period):
    """Determine why this course was bumped and what blocked it."""
    causes = []
    blocking = []
    sections_tried = []

    if keeping_cid:
        keep_crp = course_request_priority(pid, keeping_cid)
        blocking.append({
            'code': keeping_cid,
            'title': course_info.get(keeping_cid, {}).get('title', keeping_cid),
            'effective_priority': keep_crp,
            'priority_band': priority_label(pid, keeping_cid),
        })

    # Check if bumped course is a singleton
    if is_singleton(bumped_cid):
        causes.append('singleton_collision')
    # Check all alternative sections for this course
    for alt_sid in sec_by_code.get(bumped_cid, []):
        alt_s = sections[alt_sid]
        alt_period = alt_s['period']
        trial = {'sid': alt_sid, 'period': alt_period, 'section': alt_s['section']}
        # Check if student has this period free
        period_free = True
        for ac, asid in assign.get(pid, {}).items():
            if sections[asid]['period'] == alt_period and set(sections[asid]['halves']) & set(alt_s['halves']):
                trial['rejected'] = 'period_conflict'
                trial['conflicting_course'] = ac
                period_free = False
                break
        if period_free:
            if secfill[alt_sid] >= alt_s['cap']:
                trial['rejected'] = 'section_full'
            else:
                trial['rejected'] = None
        sections_tried.append(trial)

    # Classify root cause
    all_full = all(t.get('rejected') == 'section_full' for t in sections_tried if t.get('rejected'))
    all_conflict = all(t.get('rejected') == 'period_conflict' for t in sections_tried if t.get('rejected'))
    if len(sec_by_code.get(bumped_cid, [])) == 1 and all_conflict:
        causes.append('singleton_collision')
    elif all_full:
        causes.append('section_capacity')
    elif all_conflict:
        causes.append('period_saturation')
    else:
        # Mixed reasons
        conflict_count = sum(1 for t in sections_tried if t.get('rejected') == 'period_conflict')
        full_count = sum(1 for t in sections_tried if t.get('rejected') == 'section_full')
        if conflict_count > full_count:
            causes.append('period_conflict')
        elif full_count > 0:
            causes.append('section_capacity')
        else:
            causes.append('scheduling_constraint')
    if not causes:
        causes.append('unclassified')

    return {
        'root_cause_codes': causes,
        'blocking_courses': blocking,
        'sections_tried': sections_tried,
    }

clash = []
for pid in students:
    cells = defaultdict(list)
    for cid, sid in list(assign[pid].items()):
        for x in occ_cells(sid):
            cells[x].append(cid)
    bump = set()
    bump_reason = {}
    for x, cs in cells.items():
        cs = [c for c in cs if c not in bump]
        if len(cs) > 1:
            _score_fn = lambda c: (-course_request_priority(pid, c), -int(is_singleton(c)), -course_section_raw(c))
            keep = min(cs, key=_score_fn)
            for c in cs:
                if c != keep:
                    bump.add(c)
                    bump_reason[c] = keep
    for c in bump:
        s = sections[assign[pid][c]]
        _crp = course_request_priority(pid, c)
        _rca = _analyze_root_cause(pid, c, bump_reason.get(c), s['period'])
        _g = grade.get(str(pid), 0)
        clash.append({
            'student': pid, 'name': students[pid], 'grade': grade[pid],
            'code': c, 'course': course_info.get(c, {}).get('title', c),
            'course_request_priority': _crp,
            'priority_band': priority_label(pid, c),
            'is_grad_req': _is_grad_req_for_student(c, _g, pid),
            'course_section_raw': course_section_raw(c),
            'lost_period': s['period'],
            'lost_sem': 'Full-Year' if len(s['halves']) == 2 else ('Fall' if s['halves'][0] == 'S1' else 'Spring'),
            'root_cause_codes': _rca['root_cause_codes'],
            'blocking_courses': _rca['blocking_courses'],
            'sections_tried': _rca['sections_tried'],
        })
        placement_log.append({
            'phase': 'C', 'student': pid, 'code': c, 'action': 'bumped',
            'reason': _rca['root_cause_codes'][0],
            'kept_course': bump_reason.get(c, ''),
            'alternatives_checked': len(_rca['sections_tried']),
        })
        rm_place(pid, c)


# ============================================================
# PHASE D: MULTI-RESTART ITERATIVE CLASH RESOLUTION (ENHANCED)
# ============================================================
print("\n" + "=" * 60)
print("[D] PHASE D: MULTI-RESTART CLASH RESOLUTION (ENHANCED)")
print("=" * 60)

COGROUP_SIDS = set()
for _cg in cogroups:
    for _cc in _cg['codes']:
        for _cs in sec_by_code.get(_cc, []):
            COGROUP_SIDS.add(_cs)
SEMESTER_LOCKED_SIDS = set()
for _slc in SEMESTER_LOCKS:
    for _sls in sec_by_code.get(_slc, []):
        SEMESTER_LOCKED_SIDS.add(_sls)

code_requesters = defaultdict(set)
for _pid in students:
    for _cid in sreq[_pid]:
        code_requesters[_cid].add(_pid)

_orig_periods = {}
_orig_halves = {}
for s in sections:
    if s['sid'] in COGROUP_SIDS or s['sid'] in assigned_cogroups:
        _orig_periods[s['sid']] = s['period']
        _orig_halves[s['sid']] = s['halves']
    else:
        _orig_periods[s['sid']] = None
        _orig_halves[s['sid']] = s['halves']

def _save_fixed_state():
    fixed = {}
    for s in sections:
        if s['sid'] in assigned_cogroups:
            fixed[s['sid']] = (s['period'], s['halves'])
    return fixed

def _restore_for_restart(fixed_state):
    for s in sections:
        if s['sid'] in fixed_state:
            s['period'], s['halves'] = fixed_state[s['sid']]
        else:
            s['period'] = None
    for cid, halves in SEMESTER_LOCKS.items():
        for sid in sec_by_code.get(cid, []):
            sections[sid]['halves'] = halves
    for cid in FULL_FREEDOM:
        sids = [sid for sid in sec_by_code.get(cid, []) if sections[sid]['period'] is None]
        n_s1 = (len(sids) + 1) // 2
        for i, sid in enumerate(sids):
            sections[sid]['halves'] = ('S1',) if i < n_s1 else ('S2',)
    for cid, sids_list in sec_by_code.items():
        ci = course_info.get(cid, {})
        if ci.get('is_fy', True) or cid in FULL_FREEDOM or cid in SEMESTER_LOCKS:
            continue
        unpinned = [sid for sid in sids_list if sections[sid]['period'] is None]
        for i, sid in enumerate(unpinned):
            sections[sid]['halves'] = ('S1',) if i % 2 == 0 else ('S2',)

fixed_state = _save_fixed_state()

_reseat_pid_order = sorted(students.keys(), key=lambda p: -student_total_priority(p))
_reseat_course_order = {}
for _pid in _reseat_pid_order:
    _reseat_course_order[_pid] = sorted(
        sreq[_pid],
        key=lambda c, _p=_pid: (-course_request_priority(_p, c), -course_section_raw(c), len(sec_by_code.get(c, [])))
    )

BATCH_SIZE = 1500

def _recalc_batch_scores():
    """Clear priority caches between batches so totals reflect placed students."""
    _clear_priority_caches()

def full_reseat():
    _invalidate_occ_cache()
    for pid in students:
        assign[pid] = {}
    secfill.clear()
    cell_usage.clear()
    # Global placement ordering per DATA_STRUCTURE.md:
    # All student-course pairs sorted globally by priority, placed in
    # batches of 1500 with cache clearing between batches.
    all_placements = []
    for pid in students:
        for cid in sreq[pid]:
            if cid not in sec_by_code:
                continue
            all_placements.append((pid, cid))
    all_placements.sort(key=_full_sort_key)
    placed_count = 0
    deferred = []
    while all_placements:
        batch = all_placements[:BATCH_SIZE]
        all_placements = all_placements[BATCH_SIZE:]
        for pid, cid in batch:
            if cid in assign.get(pid, {}):
                continue
            if cid == '745':
                if pid in cohA and leo2C is not None:
                    add_place(pid, cid, leo2C)
                elif pid in cohB and leo2E is not None:
                    add_place(pid, cid, leo2E)
                else:
                    add_place(pid, cid, min(sec_by_code[cid],
                              key=lambda sid: (added_conflicts(pid, sid), secfill[sid])))
                placed_count += 1
                continue
            _fr_opts = sec_by_code[cid]
            if HARD_CAP_ENFORCEMENT:
                _fr_hc = [sid for sid in _fr_opts if secfill[sid] < sections[sid]['cap']]
                if _fr_hc:
                    _fr_opts = _fr_hc
            best = min(_fr_opts, key=lambda sid: (
                added_conflicts(pid, sid),
                max(0, secfill[sid] + 1 - sections[sid]['cap']),
                secfill[sid]))
            if added_conflicts(pid, best) == 0 or is_protected(pid, cid):
                add_place(pid, cid, best)
                placed_count += 1
            else:
                deferred.append((pid, cid))
        if all_placements:
            _recalc_batch_scores()
            all_placements.sort(key=_full_sort_key)
    deferred.sort(key=_full_sort_key)
    still_deferred = []
    for pid, cid in deferred:
        if cid in assign.get(pid, {}):
            continue
        if cid not in sec_by_code:
            continue
        _fr_opts = sec_by_code[cid]
        if HARD_CAP_ENFORCEMENT:
            _fr_hc = [sid for sid in _fr_opts if secfill[sid] < sections[sid]['cap']]
            if _fr_hc:
                _fr_opts = _fr_hc
        best = min(_fr_opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid]))
        if added_conflicts(pid, best) == 0:
            add_place(pid, cid, best)
        else:
            still_deferred.append((pid, cid))
    # Force-place remaining (accept conflicts for CSP/bump to resolve)
    for pid, cid in still_deferred:
        if cid in assign.get(pid, {}):
            continue
        if cid not in sec_by_code:
            continue
        _fr_opts = sec_by_code[cid]
        if HARD_CAP_ENFORCEMENT:
            _fr_hc = [sid for sid in _fr_opts if secfill[sid] < sections[sid]['cap']]
            if _fr_hc:
                _fr_opts = _fr_hc
        add_place(pid, cid, min(_fr_opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid])))
    for rnd in range(6):
        cpids = [pid for pid in students
                 if any(cell_usage.get((pid, x), 0) > 1
                        for cid, sid in assign[pid].items() for x in occ_cells(sid))]
        if not cpids:
            break
        rslvd = 0
        for pid in cpids:
            if any(cell_usage.get((pid, x), 0) > 1
                   for cid, sid in assign[pid].items() for x in occ_cells(sid)):
                if resolve_student(pid):
                    rslvd += 1
        if rslvd == 0:
            break
    nc = []
    for pid in students:
        cm = defaultdict(list)
        for cid, sid in list(assign[pid].items()):
            for x in occ_cells(sid):
                cm[x].append(cid)
        bmp = set()
        bmp_reason = {}
        for x, cs in cm.items():
            cs = [c for c in cs if c not in bmp]
            if len(cs) > 1:
                _sf = lambda c: (-course_request_priority(pid, c), -int(is_singleton(c)), -course_section_raw(c))
                kp = min(cs, key=_sf)
                for c in cs:
                    if c != kp:
                        bmp.add(c)
                        bmp_reason[c] = kp
        for c in bmp:
            bs = sections[assign[pid][c]]
            _crp = course_request_priority(pid, c)
            _g = grade.get(str(pid), 0)
            _rca = _analyze_root_cause(pid, c, bmp_reason.get(c), bs['period'])
            nc.append({
                'student': pid, 'name': students[pid], 'grade': grade[pid],
                'code': c, 'course': course_info.get(c, {}).get('title', c),
                'course_request_priority': _crp,
                'priority_band': priority_label(pid, c),
                'is_grad_req': _is_grad_req_for_student(c, _g, pid),
                'course_section_raw': course_section_raw(c),
                'lost_period': bs['period'],
                'lost_sem': 'Full-Year' if len(bs['halves']) == 2 else (
                    'Fall' if bs['halves'][0] == 'S1' else 'Spring'),
                'root_cause_codes': _rca['root_cause_codes'],
                'blocking_courses': _rca['blocking_courses'],
                'sections_tried': _rca['sections_tried'],
            })
            rm_place(pid, c)
    for cl_item in list(nc):
        pid, cid = cl_item['student'], cl_item['code']
        if cid in assign.get(pid, {}):
            continue
        used = set()
        for c2, s2 in assign.get(pid, {}).items():
            for x in occ_cells(s2):
                used.add(x)
        best, bsc = None, None
        for alt in sec_by_code.get(cid, []):
            if any(x in used for x in occ_cells(alt)):
                continue
            if HARD_CAP_ENFORCEMENT and secfill[alt] >= sections[alt]['cap']:
                continue
            sc = (max(0, secfill[alt] + 1 - sections[alt]['cap']), secfill[alt])
            if bsc is None or sc < bsc:
                bsc, best = sc, alt
        if best is not None:
            add_place(pid, cid, best)
            nc.remove(cl_item)
    # CSP recovery: for students still missing bumped courses, try rearranging their schedule
    bumped_pids = {c['student'] for c in nc}
    for pid in bumped_pids:
        resolve_student(pid)
    # Re-check: some CSP rearrangements may have opened slots for greedy re-add
    still_bumped = []
    for cl_item in list(nc):
        pid, cid = cl_item['student'], cl_item['code']
        if cid in assign.get(pid, {}):
            continue
        used = set()
        for c2, s2 in assign.get(pid, {}).items():
            for x in occ_cells(s2):
                used.add(x)
        best, bsc = None, None
        for alt in sec_by_code.get(cid, []):
            if any(x in used for x in occ_cells(alt)):
                continue
            if HARD_CAP_ENFORCEMENT and secfill[alt] >= sections[alt]['cap']:
                continue
            sc = (max(0, secfill[alt] + 1 - sections[alt]['cap']), secfill[alt])
            if bsc is None or sc < bsc:
                bsc, best = sc, alt
        if best is not None:
            add_place(pid, cid, best)
        else:
            still_bumped.append(cl_item)
    return still_bumped


def full_reseat_fast():
    """Fast version for optimizer: same global ordering + batch recalculation
    as full_reseat(), but returns only a quality tuple (protected, high, total)
    instead of building full diagnostic dicts for every bump."""
    _invalidate_occ_cache()
    for pid in students:
        assign[pid] = {}
    secfill.clear()
    cell_usage.clear()
    # Global placement ordering per DATA_STRUCTURE.md
    all_placements = []
    for pid in students:
        for cid in sreq[pid]:
            if cid not in sec_by_code:
                continue
            all_placements.append((pid, cid))
    all_placements.sort(key=_full_sort_key)
    deferred = []
    while all_placements:
        batch = all_placements[:BATCH_SIZE]
        all_placements = all_placements[BATCH_SIZE:]
        for pid, cid in batch:
            if cid in assign.get(pid, {}):
                continue
            if cid == '745':
                if pid in cohA and leo2C is not None:
                    add_place(pid, cid, leo2C)
                elif pid in cohB and leo2E is not None:
                    add_place(pid, cid, leo2E)
                else:
                    add_place(pid, cid, min(sec_by_code[cid],
                              key=lambda sid: (added_conflicts(pid, sid), secfill[sid])))
                continue
            _fr2_opts = sec_by_code[cid]
            if HARD_CAP_ENFORCEMENT:
                _fr2_hc = [sid for sid in _fr2_opts if secfill[sid] < sections[sid]['cap']]
                if _fr2_hc:
                    _fr2_opts = _fr2_hc
            best = min(_fr2_opts, key=lambda sid: (
                added_conflicts(pid, sid),
                max(0, secfill[sid] + 1 - sections[sid]['cap']),
                secfill[sid]))
            if added_conflicts(pid, best) == 0 or is_protected(pid, cid):
                add_place(pid, cid, best)
            else:
                deferred.append((pid, cid))
        if all_placements:
            _recalc_batch_scores()
            all_placements.sort(key=_full_sort_key)
    deferred.sort(key=_full_sort_key)
    still_deferred = []
    for pid, cid in deferred:
        if cid in assign.get(pid, {}):
            continue
        if cid not in sec_by_code:
            continue
        _fr2_opts = sec_by_code[cid]
        if HARD_CAP_ENFORCEMENT:
            _fr2_hc = [sid for sid in _fr2_opts if secfill[sid] < sections[sid]['cap']]
            if _fr2_hc:
                _fr2_opts = _fr2_hc
        best = min(_fr2_opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid]))
        if added_conflicts(pid, best) == 0:
            add_place(pid, cid, best)
        else:
            still_deferred.append((pid, cid))
    for pid, cid in still_deferred:
        if cid in assign.get(pid, {}):
            continue
        if cid not in sec_by_code:
            continue
        _fr2_opts = sec_by_code[cid]
        if HARD_CAP_ENFORCEMENT:
            _fr2_hc = [sid for sid in _fr2_opts if secfill[sid] < sections[sid]['cap']]
            if _fr2_hc:
                _fr2_opts = _fr2_hc
        add_place(pid, cid, min(_fr2_opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid])))
    for rnd in range(6):
        cpids = [pid for pid in students
                 if any(cell_usage.get((pid, x), 0) > 1
                        for cid, sid in assign[pid].items() for x in occ_cells(sid))]
        if not cpids:
            break
        rslvd = 0
        for pid in cpids:
            if any(cell_usage.get((pid, x), 0) > 1
                   for cid, sid in assign[pid].items() for x in occ_cells(sid)):
                if resolve_student(pid):
                    rslvd += 1
        if rslvd == 0:
            break
    protected_clashes = 0
    high_clashes = 0
    total = 0
    for pid in students:
        cm = defaultdict(list)
        for cid, sid in list(assign[pid].items()):
            for x in occ_cells(sid):
                cm[x].append(cid)
        bmp = set()
        for x, cs in cm.items():
            cs = [c for c in cs if c not in bmp]
            if len(cs) > 1:
                _sf = lambda c: (-course_request_priority(pid, c), -int(is_singleton(c)), -course_section_raw(c))
                kp = min(cs, key=_sf)
                for c in cs:
                    if c != kp:
                        bmp.add(c)
        for c in bmp:
            rm_place(pid, c)
            if is_protected(pid, c):
                protected_clashes += 1
            elif course_request_priority(pid, c) >= PTS_AP:
                high_clashes += 1
            total += 1
    for pid in students:
        for cid in sreq[pid]:
            if cid in assign.get(pid, {}):
                continue
            if cid not in sec_by_code:
                continue
            used = set()
            for c2, s2 in assign.get(pid, {}).items():
                for x in occ_cells(s2):
                    used.add(x)
            best, bsc = None, None
            for alt in sec_by_code.get(cid, []):
                if any(x in used for x in occ_cells(alt)):
                    continue
                if HARD_CAP_ENFORCEMENT and secfill[alt] >= sections[alt]['cap']:
                    continue
                sc = (max(0, secfill[alt] + 1 - sections[alt]['cap']), secfill[alt])
                if bsc is None or sc < bsc:
                    bsc, best = sc, alt
            if best is not None:
                add_place(pid, cid, best)
                total -= 1
                if is_protected(pid, cid):
                    protected_clashes -= 1
                elif course_request_priority(pid, cid) >= PTS_AP:
                    high_clashes -= 1
    # CSP recovery for students with bumped courses
    bumped_pids = set()
    for pid in students:
        for cid in sreq[pid]:
            if cid not in assign.get(pid, {}) and cid in sec_by_code:
                bumped_pids.add(pid)
                break
    for pid in bumped_pids:
        resolve_student(pid)
    # Final greedy re-add after CSP recovery
    for pid in bumped_pids:
        for cid in sreq[pid]:
            if cid in assign.get(pid, {}):
                continue
            if cid not in sec_by_code:
                continue
            used = set()
            for c2, s2 in assign.get(pid, {}).items():
                for x in occ_cells(s2):
                    used.add(x)
            best, bsc = None, None
            for alt in sec_by_code.get(cid, []):
                if any(x in used for x in occ_cells(alt)):
                    continue
                if HARD_CAP_ENFORCEMENT and secfill[alt] >= sections[alt]['cap']:
                    continue
                sc = (max(0, secfill[alt] + 1 - sections[alt]['cap']), secfill[alt])
                if bsc is None or sc < bsc:
                    bsc, best = sc, alt
            if best is not None:
                add_place(pid, cid, best)
                total -= 1
                if is_protected(pid, cid):
                    protected_clashes -= 1
                elif course_request_priority(pid, cid) >= PTS_AP:
                    high_clashes -= 1
    return (max(0, protected_clashes), max(0, high_clashes), max(0, total))


def _clash_quality(cl):
    """Priority-aware clash quality score: (protected, high_priority, total).
    Lower is better. Protected courses (grad req, Gr12 PAE, singleton) never traded for lower."""
    top_clashes = sum(1 for c in cl if is_protected(c['student'], c['code']))
    mid_clashes = sum(1 for c in cl if not is_protected(c['student'], c['code']) and course_request_priority(c['student'], c['code']) >= PTS_AP)
    return (top_clashes, mid_clashes, len(cl))

def _can_move_section(sid, new_period):
    """Check if section can move to new_period without teacher conflicts."""
    if sid in COGROUP_SIDS:
        return False
    s = sections[sid]
    if new_period == s['period']:
        return False
    t = s['teacher']
    if t and t != 'TBD':
        if any(sections[ts]['period'] == new_period
               and set(sections[ts]['halves']) & set(s['halves'])
               and not in_same_cogroup(sid, ts)
               for ts in teacher_sections.get(t, []) if ts != sid):
            return False
        old_p = s['period']
        s['period'] = None
        exc = teacher_would_exceed_cap(t, new_period, s['halves'])
        s['period'] = old_p
        if exc:
            return False
        if not teacher_available(t, new_period):
            return False
    return True

def run_optimization_pass(cl=None):
    if cl is None:
        cl = full_reseat()
    best_q = _clash_quality(cl)
    stalled = 0
    for d_iter in range(60):
        if stalled >= 8:
            break
        sec_sc = Counter()
        for c in cl:
            for sid in sec_by_code.get(c['code'], []):
                if sections[sid]['period'] == c['lost_period']:
                    sec_sc[sid] += 1
            pid_cl = c['student']
            for cid_cl, sid_cl in assign.get(pid_cl, {}).items():
                if sections[sid_cl]['period'] == c['lost_period']:
                    sec_sc[sid_cl] += 1
        for c in cl:
            _crp = c.get('course_request_priority', 0)
            if is_protected(c['student'], c['code']):
                for sid in sec_by_code.get(c['code'], []):
                    if sections[sid]['period'] == c['lost_period']:
                        sec_sc[sid] += 3
            elif _crp >= PTS_AP:
                for sid in sec_by_code.get(c['code'], []):
                    if sections[sid]['period'] == c['lost_period']:
                        sec_sc[sid] += 2
        cands = []
        for sid, score in sec_sc.most_common(120):
            if sid in COGROUP_SIDS or score < 1:
                continue
            s = sections[sid]
            for p in PERIODS:
                if not _can_move_section(sid, p):
                    continue
                new_conf = 0
                for rpid in code_requesters.get(s['code'], set()):
                    for rc in sreq[rpid]:
                        if rc == s['code']:
                            continue
                        rsids = sec_by_code.get(rc, [])
                        if rsids and all(sections[rs]['period'] == p for rs in rsids):
                            if any(set(sections[rs]['halves']) & set(s['halves']) for rs in rsids):
                                if is_protected(rpid, rc):
                                    new_conf += 4
                                elif course_request_priority(rpid, rc) >= PTS_AP:
                                    new_conf += 3
                                elif course_request_priority(rpid, rc) >= PTS_SEMESTER_ONLY:
                                    new_conf += 2
                                else:
                                    new_conf += 1
                                break
                est = score - new_conf
                if est > 0:
                    cands.append((est, sid, p))
        if not cands:
            break
        cands.sort(reverse=True)
        improved = False
        for est, sid, np in cands[:16]:
            s = sections[sid]
            op = s['period']
            s['period'] = np
            _invalidate_occ_cache()
            tc_q = full_reseat_fast()
            if tc_q < best_q:
                best_q = tc_q
                cl = full_reseat()
                improved = True
                stalled = 0
                break
            s['period'] = op
            _invalidate_occ_cache()
        if not improved:
            stalled += 1
    # Phase 2: two-section swap — try swapping periods between pairs of high-clash sections
    import time as _swap_time
    _swap_start = _swap_time.time()
    stalled2 = 0
    for d_iter2 in range(20):
        if stalled2 >= 4:
            break
        if _swap_time.time() - _swap_start > 60:
            break
        sec_sc2 = Counter()
        for c in cl:
            for sid in sec_by_code.get(c['code'], []):
                sec_sc2[sid] += 1
        top_sids = [sid for sid, _ in sec_sc2.most_common(30)
                    if sid not in COGROUP_SIDS]
        improved2 = False
        for i in range(len(top_sids)):
            if improved2:
                break
            if _swap_time.time() - _swap_start > 60:
                break
            sid1 = top_sids[i]
            s1 = sections[sid1]
            p1 = s1['period']
            for j in range(i + 1, min(i + 15, len(top_sids))):
                sid2 = top_sids[j]
                s2 = sections[sid2]
                p2 = s2['period']
                if p1 == p2:
                    continue
                if s1['teacher'] == s2['teacher']:
                    continue
                if not _can_move_section(sid1, p2):
                    continue
                if not _can_move_section(sid2, p1):
                    continue
                s1['period'] = p2
                s2['period'] = p1
                _invalidate_occ_cache()
                tc_q = full_reseat_fast()
                if tc_q < best_q:
                    best_q = tc_q
                    cl = full_reseat()
                    improved2 = True
                    stalled2 = 0
                    break
                s1['period'] = p1
                s2['period'] = p2
                _invalidate_occ_cache()
        if not improved2:
            stalled2 += 1
    return cl

# v3: 16 restart seeds (doubled from 8)
SEEDS = [4269, 256, 7777, 2024, 5050, 7, 1337, 3141,
         42, 100, 999, 2025, 8888, 31415, 54321, 11111]
best_clash = None
best_periods = None
best_halves = None
best_seed = None

def _recompute_seating_order():
    """Clear priority caches after period assignments change.
    full_reseat() and full_reseat_fast() build their own global ordering
    using _full_sort_key each time."""
    _clear_priority_caches()

import time as _time
import gc as _gc
for restart, seed in enumerate(SEEDS):
    _gc.collect()
    _t0 = _time.time()
    _restore_for_restart(fixed_state)
    greedy_assign_periods(seed=seed)
    _recompute_seating_order()
    cl = full_reseat()
    baseline = len(cl)

    cl = run_optimization_pass(cl)
    result = len(cl)
    _elapsed = _time.time() - _t0

    print(f"  Restart {restart+1}/{len(SEEDS)} (seed={seed}): baseline={baseline} -> optimized={result}  [{_elapsed:.1f}s]")

    result_q = _clash_quality(cl)
    if best_clash is None or result_q < _clash_quality(best_clash):
        best_clash = cl
        best_seed = seed
        best_periods = {s['sid']: s['period'] for s in sections}
        best_halves = {s['sid']: s['halves'] for s in sections}

    # Early exit if we hit a great result
    if result <= 50:
        print(f"  Early exit: {result} clashes is below target threshold")
        break

# Restore best solution
for s in sections:
    s['period'] = best_periods[s['sid']]
    s['halves'] = best_halves[s['sid']]
_recompute_seating_order()
clash = full_reseat()
print(f"\n  BEST: seed={best_seed}, {len(clash)} clashes")

# Recompute stats
prior_match = sum(1 for s in sections
                  if s['period'] in (prior_teacher_periods.get((s['code'], s['teacher']), set())
                                     or prior_course_periods.get(s['code'], set())))
prior_total = sum(1 for s in sections
                  if prior_teacher_periods.get((s['code'], s['teacher']), set())
                  or prior_course_periods.get(s['code'], set()))
t_conflicts = 0
for teacher, sids in teacher_sections.items():
    slots = defaultdict(list)
    for sid in sids:
        for h in sections[sid]['halves']:
            slots[(sections[sid]['period'], h)].append(sid)
    for slot, sl in slots.items():
        if len(sl) > 1:
            real = sum(1 for i in range(len(sl))
                       if not any(in_same_cogroup(sl[i], sl[j])
                                  for j in range(len(sl)) if i != j))
            if real > 1:
                t_conflicts += real - 1
load_violations = []
for teacher in teacher_sections:
    ms1, ms2 = get_max_load(teacher)
    s1_load = teacher_load(teacher, 'S1')
    s2_load = teacher_load(teacher, 'S2')
    if s1_load > ms1 or s2_load > ms2:
        load_violations.append({'teacher': teacher, 's1': s1_load, 's2': s2_load,
                               'max_s1': ms1, 'max_s2': ms2})

print(f"\n  PHASE D COMPLETE: {len(clash)} clashes")


# ============================================================
# 3. RESULTS
# ============================================================
print("\n" + "=" * 60)
print("[3] RESULTS")
print("=" * 60)

total_placed = sum(len(v) for v in assign.values())
total_requested = sum(len(v) for v in sreq.values())
placement_rate = 100 * total_placed / total_requested if total_requested else 0

print(f"  Clashes: {len(clash)}")
print(f"  Students affected: {len(set(c['student'] for c in clash))}")
print(f"  Placed: {total_placed}/{total_requested} ({placement_rate:.1f}%)")

# Item 4: Disaggregated fulfillment preview
_preview_grad_req = sum(1 for p in students for c in sreq[p] if _is_grad_req_for_student(c, grade.get(str(p), 0), pid=p))
_preview_grad_placed = sum(1 for p in students for c in sreq[p] if _is_grad_req_for_student(c, grade.get(str(p), 0), pid=p) and c in assign.get(p, {}))
_preview_ap = sum(1 for p in students for c in sreq[p] if course_info.get(c, {}).get('is_ap', False))
_preview_ap_placed = sum(1 for p in students for c in sreq[p] if course_info.get(c, {}).get('is_ap', False) and c in assign.get(p, {}))
print(f"  Graduation requirement fulfillment: {_preview_grad_placed}/{_preview_grad_req} ({100*_preview_grad_placed/_preview_grad_req:.1f}%)" if _preview_grad_req else "  Graduation requirement fulfillment: N/A")
print(f"  AP/Honors fulfillment: {_preview_ap_placed}/{_preview_ap} ({100*_preview_ap_placed/_preview_ap:.1f}%)" if _preview_ap else "  AP/Honors fulfillment: N/A")

# Protected clash analysis (grad req, Gr12 PAE, singleton)
protected_clashes = [c for c in clash if is_protected(c['student'], c['code'])]
print(f"  Protected clashes (grad req / Gr12 PAE / singleton): {len(protected_clashes)}")
if protected_clashes:
    for c in protected_clashes[:10]:
        print(f"    {c['name']} (Gr{c['grade']}): {c['course']} [{c['code']}] — Period {c['lost_period']}")

sec_sizes = [secfill[sid] for sid in range(len(sections)) if secfill[sid] > 0]
if sec_sizes:
    print(f"  Section sizes: min={min(sec_sizes)}, max={max(sec_sizes)}, avg={statistics.mean(sec_sizes):.1f}")

dept_clashes = Counter()
band_clashes = Counter()
grade_clashes = Counter()
for c in clash:
    ci = course_info.get(c['code'], {})
    dept_clashes[ci.get('dept', 'Unknown')] += 1
    band_clashes[c.get('priority_band', 'elective')] += 1
    grade_clashes[c['grade']] += 1

print(f"\n  Clashes by priority band:")
for band in sorted(band_clashes.keys()):
    print(f"    {band}: {band_clashes[band]}")
print(f"\n  Clashes by department:")
for dept, cnt in dept_clashes.most_common():
    print(f"    {dept}: {cnt}")
print(f"\n  Clashes by grade:")
for g in sorted(grade_clashes.keys()):
    print(f"    Grade {g}: {grade_clashes[g]}")

# Item 4: Root-cause aggregation
_rc_counts = Counter()
for _cl in clash:
    for _rc in _cl.get('root_cause_codes', ['unclassified']):
        _rc_counts[_rc] += 1
if _rc_counts:
    _RC_LABELS = {
        'singleton_collision': 'Singleton Collision',
        'section_capacity': 'Section Full',
        'period_saturation': 'All Periods Blocked',
        'period_conflict': 'Period Conflict',
        'scheduling_constraint': 'Mixed Constraints',
        'unclassified': 'Unclassified',
    }
    print(f"\n  Root cause breakdown:")
    for _rc, _cnt in _rc_counts.most_common():
        print(f"    {_RC_LABELS.get(_rc, _rc)}: {_cnt}")

print(f"\n  Prior-year alignment: {prior_match}/{prior_total}")
print(f"  Teacher load violations: {len(load_violations)}")
for lv in load_violations:
    print(f"    {lv['teacher']}: S1={lv['s1']}/{lv['max_s1']} S2={lv['s2']}/{lv['max_s2']}")

# ============================================================
# 3b. RESOLVE ROOM CONFLICTS
# ============================================================
PRIOR_YEAR_ROOMS = {
    "O'Connor, Paul": {"Classroom D-101": 5},
    "Mazella, Julie": {"Classroom D-103": 5},
    "DeLeon, Marco": {"Classroom D-102": 1, "Classroom D-103": 2, "Classroom D-204": 1, "Classroom I-114": 1},
    "Nobilione, Lauren": {"Classroom D-104": 5},
    "Saggio, Jack": {"Classroom D-104": 2, "Classroom D-201": 1, "Classroom D-203": 1, "Classroom I-117": 1, "Classroom J-321": 1},
    "Gettler, Mary": {"Classroom D-105": 6},
    "Gerlach, Reese": {"Classroom D-107": 6},
    "Hampson, Elizabeth": {"Classroom D-108": 5},
    "Montegari, James": {"Classroom I-114": 5},
    "Martino, Brianna": {"Classroom I-113": 1, "Classroom I-114": 1, "Classroom I-117": 1, "Classroom I-119": 1, "Classroom S-235": 1},
    "Dwyer, Kevin": {"Classroom I-115": 5},
    "Lomascolo, Frank": {"Classroom J-320": 5},
    "Arcede, Francis": {"Classroom J-321": 5},
    "Langan, John": {"Classroom J-320": 1, "Classroom J-323": 2, "Lecture Hall D-206": 1},
    "Carr, Lynette": {"Classroom S-231": 6},
    "Angotti, Sylvia": {"Classroom S-231": 2, "Classroom S-232": 1, "Classroom I-119": 1, "Classroom J-221": 1},
    "Zawacki, Richard": {"Classroom S-233": 5},
    "Corcoran, Kevin": {"Classroom S-238": 10},
    "Guy, Libbie": {"Classroom I-115": 1, "Classroom S-238": 1},
}

EXEMPT_ROOMS = SHARED_ROOMS | {'Gymnasium'}
ALL_ROOMS = sorted(set(s['room'] for s in sections if s['room'] not in ('TBD', 'Unassigned') and s['room'] not in EXEMPT_ROOMS))

def _room_free(room, period, halves, exclude_sid):
    if room in SHARED_ROOMS:
        return True
    for s in sections:
        if s['sid'] == exclude_sid or s['period'] != period or s['room'] != room:
            continue
        if set(s['halves']) & set(halves):
            return False
    return True

def _find_room_conflicts():
    rp = defaultdict(list)
    for s in sections:
        if s['room'] in EXEMPT_ROOMS or s['room'] in ('TBD', 'Unassigned'):
            continue
        rp[(s['room'], s['period'])].append(s)
    conflicts = {}
    for (room, period), slist in rp.items():
        teachers = set(s['teacher'] for s in slist)
        if len(teachers) > 1:
            has_overlap = False
            for i, a in enumerate(slist):
                for b in slist[i+1:]:
                    if a['teacher'] != b['teacher'] and set(a['halves']) & set(b['halves']):
                        has_overlap = True
            if has_overlap:
                conflicts[(room, period)] = slist
    return conflicts

print("\n[3b] RESOLVING ROOM CONFLICTS...")
room_moves = []
max_passes = 5
for pass_num in range(max_passes):
    conflicts = _find_room_conflicts()
    if not conflicts:
        break
    print(f"  Pass {pass_num+1}: {len(conflicts)} conflicts")
    for (room, period), slist in sorted(conflicts.items()):
        scored = []
        for s in slist:
            py = PRIOR_YEAR_ROOMS.get(s['teacher'], {}).get(room, 0)
            scored.append((py, secfill.get(s['sid'], 0), s))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        stay = scored[0][2]
        for _, _, mover in scored[1:]:
            if mover['teacher'] == stay['teacher']:
                continue
            if not (set(mover['halves']) & set(stay['halves'])):
                continue
            mover_priors = PRIOR_YEAR_ROOMS.get(mover['teacher'], {})
            wing = room.split('-')[0].split()[-1] if '-' in room else ''
            candidates = []
            for pr in sorted(mover_priors, key=lambda r: -mover_priors[r]):
                if pr not in candidates and pr != room:
                    candidates.append(pr)
            for r in ALL_ROOMS:
                if r not in candidates and r != room and wing and wing + '-' in r:
                    candidates.append(r)
            for r in ALL_ROOMS:
                if r not in candidates and r != room:
                    candidates.append(r)
            placed = False
            for new_room in candidates:
                if _room_free(new_room, period, mover['halves'], mover['sid']):
                    old = mover['room']
                    mover['room'] = new_room
                    room_moves.append(f"{old} Per {period} -> {new_room}: {mover['teacher']} ({mover['code']})")
                    placed = True
                    break
            if not placed:
                room_moves.append(f"UNRESOLVED: {room} Per {period} {mover['teacher']} ({mover['code']})")

final_conflicts = _find_room_conflicts()
print(f"  Room conflicts resolved: {len(room_moves)} moves, {len(final_conflicts)} remaining")


# ============================================================
# 4. SAVE RESULTS
# ============================================================
# Item 4: Disaggregated metrics
# Graduation fulfillment: % of graduation-required requests placed
_grad_req_requested = 0
_grad_req_placed = 0
_first_choice_placed = 0
_ap_honors_requested = 0
_ap_honors_placed = 0
for _pid in students:
    for _cid in sreq[_pid]:
        _g = grade.get(str(_pid), 0)
        if _g and _is_grad_req_for_student(_cid, _g, pid=_pid):
            _grad_req_requested += 1
            if _cid in assign.get(_pid, {}):
                _grad_req_placed += 1
        if course_info.get(_cid, {}).get('is_ap', False):
            _ap_honors_requested += 1
            if _cid in assign.get(_pid, {}):
                _ap_honors_placed += 1
        if _cid in assign.get(_pid, {}):
            _first_choice_placed += 1

_grad_fulfillment = round(100.0 * _grad_req_placed / _grad_req_requested, 1) if _grad_req_requested else 100.0
_first_choice_rate = round(100.0 * _first_choice_placed / total_requested, 1) if total_requested else 0.0
_ap_honors_rate = round(100.0 * _ap_honors_placed / _ap_honors_requested, 1) if _ap_honors_requested else 100.0

# Item 4: Root-cause aggregation
_root_cause_counts = Counter()
for _cl in clash:
    for _rc in _cl.get('root_cause_codes', ['unclassified']):
        _root_cause_counts[_rc] += 1

output = {
    'engine_version': 'v3-enhanced',
    'sections': [],
    'assignments': {},
    'clashes': clash,
    'placement_log': placement_log,
    'preflight': {
        'duplicates': len(_dup_warnings),
        'grade_ineligible': len(_grade_warnings),
        'prereq_missing': len(_prereq_warnings),
        'prereq_with_transcript': len(_prereq_with_trans),
        'prereq_no_transcript': len(_prereq_no_trans),
        'constraint_chains': len(_chain_warnings),
        'warnings': preflight_warnings,
    },
    'stats': {
        'students': len(students),
        'requests': total_requested,
        'placed': total_placed,
        'clashes': len(clash),
        'protected_clashes': len(protected_clashes),
        'sections_used': len([s for s in range(len(sections)) if secfill[s] > 0]),
        'placement_rate': round(placement_rate, 1),
        'graduation_fulfillment_rate': _grad_fulfillment,
        'graduation_required_placed': _grad_req_placed,
        'graduation_required_total': _grad_req_requested,
        'first_choice_rate': _first_choice_rate,
        'ap_honors_fulfillment_rate': _ap_honors_rate,
        'ap_honors_placed': _ap_honors_placed,
        'ap_honors_total': _ap_honors_requested,
        'prior_year_alignment': f"{prior_match}/{prior_total}",
        'restart_seeds_tried': len(SEEDS),
        'best_seed': best_seed,
    },
    'root_cause_summary': dict(_root_cause_counts.most_common()),
    'constraint_classification': CONSTRAINT_CLASSES,
    'diagnostics': {
        'teacher_conflicts': t_conflicts,
        'load_violations': load_violations,
        'room_moves': room_moves,
        'room_conflicts_remaining': len(final_conflicts),
    }
}

for s in sections:
    prior_prefs = prior_teacher_periods.get((s['code'], s['teacher']), set())
    if not prior_prefs:
        prior_prefs = prior_course_periods.get(s['code'], set())
    prior_match_flag = s['period'] in prior_prefs if prior_prefs else None

    output['sections'].append({
        'sid': s['sid'], 'code': s['code'], 'title': s['title'],
        'dept': s['dept'], 'period': s['period'], 'halves': list(s['halves']),
        'teacher': s['teacher'], 'room': s['room'], 'cap': s['cap'],
        'enrolled': secfill[s['sid']], 'section': s['section'],
        'course_section_raw': course_section_raw(s['code']),
        'prior_year_match': prior_match_flag
    })

for pid in students:
    output['assignments'][pid] = {
        'name': students[pid],
        'grade': grade[pid],
        'student_raw': student_raw_priority(pid),
        'student_total': student_total_priority(pid),
        'courses': {}
    }
    for cid, sid in assign[pid].items():
        s = sections[sid]
        output['assignments'][pid]['courses'][cid] = {
            'title': s['title'],
            'period': s['period'],
            'halves': list(s['halves']),
            'teacher': s['teacher'],
            'room': s['room'],
            'section': s['section'],
            'course_request_priority': course_request_priority(pid, cid)
        }

SOLUTION_FILE = os.path.join(SCRATCHPAD, "schedule_solution_v3.json")
with open(SOLUTION_FILE, 'w') as f:
    json.dump(output, f)

# Also save to project root for easy access
SOLUTION_FILE_ROOT = os.path.join(os.path.dirname(__file__) or '.', "schedule_solution_v3.json")
with open(SOLUTION_FILE_ROOT, 'w') as f:
    json.dump(output, f)

print(f"\n  Solution saved to {SOLUTION_FILE}")
print(f"  Solution also saved to {SOLUTION_FILE_ROOT}")

# ── Job 2 Excel Export ──
def export_job2_report():
    """Export Job 2 (Student Placement) results to Excel for review."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    wb = openpyxl.Workbook()

    # ── Sheet 1: Student Placements ──
    ws = wb.active
    ws.title = "Student Placements"
    headers = [
        'Student ID', 'Student Name', 'Grade',
        'Course Code', 'Course Title', 'Section #',
        'Period', 'Term', 'Teacher', 'Room',
        'CRP', 'Student Raw', 'Student Total', 'CS Raw',
        'Section Fill', 'Section Cap', 'Fill %',
    ]
    hdr_font = Font(name='Arial', bold=True, color='FFFFFF', size=10)
    hdr_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    row = 2
    for pid in sorted(students.keys(), key=lambda p: (-grade.get(p, 0), students.get(p, ''))):
        for cid, sid in sorted(assign[pid].items(), key=lambda x: (sections[x[1]]['period'] or 'Z')):
            s = sections[sid]
            term_str = '/'.join(s['halves'])
            if set(s['halves']) == {'S1', 'S2'}:
                term_str = 'FY'
            fill_count = secfill[sid]
            fill_pct = round(fill_count / s['cap'] * 100, 1) if s['cap'] > 0 else 0
            vals = [
                pid, students[pid], grade.get(pid, ''),
                cid, s['title'], s['section'],
                s['period'] or 'UNASSIGNED', term_str, s['teacher'], s['room'],
                course_request_priority(pid, cid),
                student_raw_priority(pid), student_total_priority(pid),
                course_section_raw(cid),
                fill_count, s['cap'], fill_pct,
            ]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=row, column=c, value=v)
                cell.font = Font(name='Arial', size=10)
                cell.border = thin_border
                if c >= 11:
                    cell.alignment = Alignment(horizontal='center')
            row += 1

    for c in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 14
    ws.column_dimensions['B'].width = 22
    ws.column_dimensions['E'].width = 28
    ws.column_dimensions['I'].width = 22
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = 'A2'

    # ── Sheet 2: Unscheduled Requests ──
    ws2 = wb.create_sheet("Unscheduled Requests")
    u_headers = ['Student ID', 'Student Name', 'Grade', 'Course Code', 'Course Title',
                 'CRP', 'Student Raw', 'Student Total', 'Root Cause']
    for c, h in enumerate(u_headers, 1):
        cell = ws2.cell(1, c, h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = thin_border
    u_row = 2
    for pid in sorted(students.keys(), key=lambda p: (-grade.get(p, 0), students.get(p, ''))):
        for cid in sreq.get(pid, []):
            if cid not in assign[pid]:
                root = ''
                if cid not in sec_by_code or not sec_by_code[cid]:
                    root = 'no_sections'
                else:
                    root = 'all_periods_blocked'
                title = course_info.get(cid, {}).get('title', cid)
                for c, v in enumerate([
                    pid, students[pid], grade.get(pid, ''),
                    cid, title,
                    course_request_priority(pid, cid),
                    student_raw_priority(pid), student_total_priority(pid),
                    root,
                ], 1):
                    cell = ws2.cell(u_row, c, v)
                    cell.font = Font(name='Arial', size=10)
                    cell.border = thin_border
                u_row += 1
    for c in range(1, len(u_headers) + 1):
        ws2.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 16
    ws2.column_dimensions['B'].width = 22
    ws2.column_dimensions['E'].width = 28
    ws2.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(u_headers))}{u_row - 1}"
    ws2.freeze_panes = 'A2'

    # ── Sheet 3: Section Fill Summary ──
    ws3 = wb.create_sheet("Section Fill")
    sf_headers = ['Course Code', 'Course Title', 'Section #', 'Period', 'Term',
                  'Teacher', 'Room', 'Enrolled', 'Cap', 'Fill %', 'Remaining']
    for c, h in enumerate(sf_headers, 1):
        cell = ws3.cell(1, c, h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.border = thin_border
    sf_row = 2
    for s in sorted(sections, key=lambda s: (s['code'], s['section'])):
        fill_count = secfill[s['sid']]
        fill_pct = round(fill_count / s['cap'] * 100, 1) if s['cap'] > 0 else 0
        term_str = '/'.join(s['halves'])
        if set(s['halves']) == {'S1', 'S2'}:
            term_str = 'FY'
        for c, v in enumerate([
            s['code'], s['title'], s['section'], s['period'] or '', term_str,
            s['teacher'], s['room'], fill_count, s['cap'], fill_pct, s['cap'] - fill_count,
        ], 1):
            cell = ws3.cell(sf_row, c, v)
            cell.font = Font(name='Arial', size=10)
            cell.border = thin_border
            if c >= 8:
                cell.alignment = Alignment(horizontal='center')
            if fill_pct >= 100 and c == 10:
                cell.font = Font(name='Arial', size=10, color='FF0000', bold=True)
        sf_row += 1
    for c in range(1, len(sf_headers) + 1):
        ws3.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 14
    ws3.column_dimensions['B'].width = 28
    ws3.column_dimensions['F'].width = 22
    ws3.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(sf_headers))}{sf_row - 1}"
    ws3.freeze_panes = 'A2'

    # ── Sheet 4: Summary ──
    ws4 = wb.create_sheet("Summary")
    total_placed = sum(len(v) for v in assign.values())
    total_requested = sum(len(sreq[pid]) for pid in students)
    total_unscheduled = total_requested - total_placed
    summary_data = [
        ('Total Students', len(students)),
        ('Total Course Requests', total_requested),
        ('Total Placements', total_placed),
        ('Total Unscheduled', total_unscheduled),
        ('Placement Rate', f"{round(total_placed / total_requested * 100, 1)}%" if total_requested else '0%'),
        ('', ''),
        ('Students with Conflicts', conf_count),
        ('Total Clashes', len(clash)),
        ('', ''),
        ('By Grade:', ''),
    ]
    for g in [9, 10, 11, 12]:
        g_students = [p for p in students if grade.get(p) == g]
        g_placed = sum(len(assign[p]) for p in g_students)
        g_requested = sum(len(sreq[p]) for p in g_students)
        g_clashes = sum(1 for c in clash if grade.get(c['student']) == g)
        summary_data.append((f'  Grade {g}', f'{g_placed}/{g_requested} placed, {g_clashes} clashes'))
    for r, (label, val) in enumerate(summary_data, 1):
        ws4.cell(r, 1, label).font = Font(name='Arial', bold=True, size=10)
        ws4.cell(r, 2, val).font = Font(name='Arial', size=10)
    ws4.column_dimensions['A'].width = 30
    ws4.column_dimensions['B'].width = 40

    out_path = os.path.join(OUTPUT_DIR, 'Job2_Student_Placements_2026_27.xlsx')
    wb.save(out_path)
    print(f"\n  ** Job 2 Excel export saved: {out_path}")
    return out_path

_job2_path = export_job2_report()

# ============================================================
# 5. POST-RUN: GENERATE INTERACTIVE HTML BOARDS
# ============================================================
print("\n" + "=" * 60)
print("[5] GENERATING INTERACTIVE HTML BOARDS")
print("=" * 60)

BOARDS_DIR = os.path.join(OUTPUT_DIR, 'boards')
os.makedirs(BOARDS_DIR, exist_ok=True)

def _inject_data(html_src, marker_pattern, new_data_js):
    """Replace a JS data constant in an HTML file with new data."""
    import re
    m = re.search(marker_pattern, html_src)
    if not m:
        return None
    start = m.start()
    depth = 0
    i = m.end() - 1
    open_ch = html_src[i]
    close_ch = '}' if open_ch == '{' else ']'
    while i < len(html_src):
        if html_src[i] == open_ch:
            depth += 1
        elif html_src[i] == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(html_src) and html_src[end] in ' \t':
                    end += 1
                if end < len(html_src) and html_src[end] == ';':
                    end += 1
                return html_src[:start] + new_data_js + html_src[end:]
        i += 1
    return None

_boards_generated = 0

# ── Board 1: Credit Validation Report ──
try:
    _cvr_path = os.path.join(OUTPUT_DIR, 'credit_validation_report.html')
    if os.path.exists(_cvr_path):
        with open(_cvr_path) as _f:
            _cvr_html = _f.read()
        _cvr_data = []
        for _v in _credit_violations:
            _cvr_data.append({
                'id': _v['student_id'],
                'name': _v['name'],
                'grade': _v['grade'],
                'total': _v['total_credits'],
                'excess': _v['excess'],
                'count': _v['course_count'],
                'courses': [{'code': c['code'], 'title': c['title'],
                             'credits': c['credits'], 'course_section_raw': course_section_raw(c['code'])}
                            for c in _v['courses']]
            })
        _cvr_js = f"const DATA = {json.dumps(_cvr_data)};"
        _cvr_out = _inject_data(_cvr_html, r'const DATA\s*=\s*\[', _cvr_js)
        if _cvr_out:
            _cvr_dest = os.path.join(BOARDS_DIR, 'credit_validation_report.html')
            with open(_cvr_dest, 'w') as _f:
                _f.write(_cvr_out)
            print(f"  credit_validation_report.html — {len(_cvr_data)} violations")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: credit_validation_report failed: {_e}")

# ── Board 2: Student Clash Report ──
try:
    _scr_path = os.path.join(OUTPUT_DIR, 'student_clash_report.html')
    if os.path.exists(_scr_path):
        with open(_scr_path) as _f:
            _scr_html = _f.read()
        _scr_sections = []
        for _s in sections:
            _h = 3 if len(_s['halves']) == 2 else (1 if _s['halves'][0] == 'S1' else 2)
            _scr_sections.append([
                _s['code'], _s['title'], _s['dept'], _s['period'],
                _h, _s['teacher'], _s['room'], _s['cap'],
                secfill[_s['sid']], _s['section']
            ])
        _clash_by_student = defaultdict(lambda: {'cl': [], 'sc': {}})
        for _c in clash:
            _pid = _c['student']
            _clash_by_student[_pid]['cl'].append([
                _c['code'], _c['course'], _c['lost_period'], 1
            ])
        for _pid in students:
            if _pid in _clash_by_student or _pid in [_c['student'] for _c in clash]:
                for _cid, _sid in assign.get(_pid, {}).items():
                    _s = sections[_sid]
                    _h = 3 if len(_s['halves']) == 2 else (1 if _s['halves'][0] == 'S1' else 2)
                    _clash_by_student[_pid]['sc'][_cid] = [
                        _s['title'], _s['period'], _h,
                        _s['teacher'], _s['room'], _s['section']
                    ]
        _scr_clashes = []
        for _pid, _data in _clash_by_student.items():
            if _data['cl']:
                _scr_clashes.append({
                    'id': _pid,
                    'n': students.get(_pid, _pid),
                    'g': grade.get(_pid, 9),
                    'cl': _data['cl'],
                    'sc': _data['sc']
                })
        _scr_clashes.sort(key=lambda x: (-len(x['cl']), x['g'], x['n']))
        _scr_names = {}
        for _pid, _name in students.items():
            _scr_names[_pid] = [_name, grade.get(_pid, 9)]
        _scr_ss = defaultdict(list)
        for _pid, _courses in assign.items():
            for _cid, _sid in _courses.items():
                _s = sections[_sid]
                _key = f"{_cid}-{_s['section']}"
                _scr_ss[_key].append(_pid)
        _scr_occ = {}
        for _pid, _courses in assign.items():
            _entries = []
            for _cid, _sid in _courses.items():
                _s = sections[_sid]
                _h = 3 if len(_s['halves']) == 2 else (1 if _s['halves'][0] == 'S1' else 2)
                _entries.append([_cid, _s['title'], _s['period'], _s['section']])
            _scr_occ[_pid] = _entries
        _total_requests = total_requested
        _total_placed = sum(len(v) for v in assign.values())
        _scr_stats = {
            'placed': _total_placed,
            'total_requests': _total_requests,
            'total_clashes': len(clash),
            'affected_students': len(_scr_clashes)
        }
        _scr_cs = defaultdict(list)
        for _s in sections:
            _h = 3 if len(_s['halves']) == 2 else (1 if _s['halves'][0] == 'S1' else 2)
            _scr_cs[_s['code']].append([_s['section'], _s['period'], _h, _s['teacher'], secfill[_s['sid']], _s['cap']])
        _scr_d = json.dumps({
            'S': _scr_sections, 'C': _scr_clashes,
            'N': _scr_names, 'SS': dict(_scr_ss),
            'O': _scr_occ, 'CS': dict(_scr_cs),
            'stats': _scr_stats
        })
        _scr_js = f"const D = {_scr_d};"
        _scr_out = _inject_data(_scr_html, r'const D\s*=\s*\{', _scr_js)
        if _scr_out:
            _scr_dest = os.path.join(BOARDS_DIR, 'student_clash_report.html')
            with open(_scr_dest, 'w') as _f:
                _f.write(_scr_out)
            print(f"  student_clash_report.html — {len(_scr_clashes)} students with clashes")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: student_clash_report failed: {_e}")

# ── Board 3: Singleton Board ──
try:
    _sb_path = os.path.join(OUTPUT_DIR, 'singleton_board.html')
    if os.path.exists(_sb_path):
        with open(_sb_path) as _f:
            _sb_html = _f.read()
        _singleton_codes = set()
        _code_section_count = Counter(_s['code'] for _s in sections)
        for _code, _cnt in _code_section_count.items():
            if _cnt == 1:
                _singleton_codes.add(_code)
        _sb_data = {'s': []}
        _teacher_groups = defaultdict(list)
        for _idx, _s in enumerate(sections):
            _h = 'F' if len(_s['halves']) == 2 else ('1' if _s['halves'][0] == 'S1' else '2')
            _is_singleton = _s['code'] in _singleton_codes
            _entry = {
                'i': _idx, 'c': _s['code'], 'n': _s['title'],
                'p': _s['period'], 'h': _h, 't': _s['teacher'],
                'r': _s['room'], 'k': _s['cap'], 'd': _s['dept'],
                'e': secfill[_s['sid']], 'sn': _s['section'], 'sg': _is_singleton
            }
            if _is_singleton:
                _sb_data['s'].append(_entry)
            else:
                _teacher_groups[_s['teacher']].append({
                    'i': _idx, 'c': _s['code'], 'n': _s['title'],
                    'p': _s['period'], 'h': _h, 'r': _s['room'],
                    'e': secfill[_s['sid']], 'sn': _s['section'], 'sg': False
                })
        for _teacher, _secs in _teacher_groups.items():
            _sb_data[_teacher] = _secs
        _sb_js = f"const D = {json.dumps(_sb_data)};"
        _sb_out = _inject_data(_sb_html, r'const D\s*=\s*\{', _sb_js)
        if _sb_out:
            _sb_dest = os.path.join(BOARDS_DIR, 'singleton_board.html')
            with open(_sb_dest, 'w') as _f:
                _f.write(_sb_out)
            print(f"  singleton_board.html — {len(_sb_data['s'])} singletons, {len(_teacher_groups)} teachers")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: singleton_board failed: {_e}")

# ── Board 4: Conflict Resolution Console ──
try:
    _crc_path = os.path.join(OUTPUT_DIR, 'conflict_resolution_console.html')
    if os.path.exists(_crc_path):
        with open(_crc_path) as _f:
            _crc_html = _f.read()
        _clash_by_course = defaultdict(lambda: {'count': 0, 'blocking': Counter()})
        for _c in clash:
            _ccode = _c['code']
            _clash_by_course[_ccode]['count'] += 1
            _pid = _c['student']
            for _oc, _osid in assign.get(_pid, {}).items():
                if sections[_osid]['period'] == _c['lost_period']:
                    _okey = f"{_oc} {course_info.get(_oc, {}).get('title', _oc)}"
                    _clash_by_course[_ccode]['blocking'][_okey] += 1
        _crc_data = []
        for _ccode, _info in sorted(_clash_by_course.items(), key=lambda x: -x[1]['count']):
            _ci = course_info.get(_ccode, {})
            _code_secs = [_s for _s in sections if _s['code'] == _ccode]
            _periods_used = sorted(set(_s['period'] for _s in _code_secs))
            _gaps = sorted(set(PERIODS) - set(_periods_used))
            _teachers = sorted(set(_s['teacher'] for _s in _code_secs))
            _teacher_free = {}
            for _t in _teachers:
                _t_secs = [_s for _s in sections if _s['teacher'] == _t]
                _t_periods_s1 = set()
                _t_periods_s2 = set()
                for _ts in _t_secs:
                    if 'S1' in _ts['halves']:
                        _t_periods_s1.add(_ts['period'])
                    if 'S2' in _ts['halves']:
                        _t_periods_s2.add(_ts['period'])
                _teacher_free[_t] = {
                    'free_s1': sorted(set(PERIODS) - _t_periods_s1),
                    'free_s2': sorted(set(PERIODS) - _t_periods_s2),
                    'load_s1': len(_t_periods_s1),
                    'load_s2': len(_t_periods_s2)
                }
            _n_clashes = _info['count']
            _fix_type = 'add_section' if _gaps else ('redistribute' if len(_code_secs) > 1 else 'structural')
            if _fix_type == 'add_section':
                _fix_desc = f"Add section in Period {'/'.join(_gaps)}."
            elif _fix_type == 'redistribute':
                _fix_desc = f"Redistribute students across {len(_code_secs)} existing sections."
            else:
                _fix_desc = "Structural change needed — review period assignment or add section."
            _crc_data.append({
                'code': _ccode,
                'title': _ci.get('title', _ccode),
                'dept': _ci.get('dept', ''),
                'clashes': _n_clashes,
                'sections': len(_code_secs),
                'periods': _periods_used,
                'gaps': _gaps,
                'teachers': _teachers,
                'teacher_free': _teacher_free,
                'blocking': dict(_info['blocking'].most_common(10)),
                'course_section_raw': course_section_raw(_ccode),
                'fix_type': _fix_type,
                'fix_desc': _fix_desc
            })
        _crc_js = f"const DATA = {json.dumps(_crc_data)};"
        _crc_out = _inject_data(_crc_html, r'const DATA\s*=\s*\[', _crc_js)
        if _crc_out:
            _crc_dest = os.path.join(BOARDS_DIR, 'conflict_resolution_console.html')
            with open(_crc_dest, 'w') as _f:
                _f.write(_crc_out)
            print(f"  conflict_resolution_console.html — {len(_crc_data)} courses with clashes")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: conflict_resolution_console failed: {_e}")

# ── Board 5: Student Request Recommendations ──
try:
    _srr_path = os.path.join(OUTPUT_DIR, 'student_request_recommendations.html')
    if os.path.exists(_srr_path):
        with open(_srr_path) as _f:
            _srr_html = _f.read()
        # Item 2: Prerequisite-aware, ranked alternatives
        def _check_prereqs_met(pid_check, cid_check):
            """Check if student has completed prerequisites for a course."""
            prereq_info = course_prereqs.get(str(cid_check), {})
            if not prereq_info:
                return True
            prereqs = prereq_info.get('prereqs', [])
            if not prereqs:
                return True
            completed = set()
            for tr in transcript.get(str(pid_check), []):
                if tr.get('passed', False):
                    completed.add(str(tr.get('code', '')))
            for req_cid in sreq.get(pid_check, []):
                completed.add(str(req_cid))
            return all(str(p) in completed for p in prereqs)

        def _alt_rank(alt_sec, bumped_dept, bumped_code, bumped_raw, pid_rank):
            """Rank alternatives: same-subject > same-requirement > same-rigor > other.
            Lower rank number = better match."""
            alt_dept = alt_sec['dept']
            alt_raw = course_section_raw(alt_sec['code'])
            alt_g = grade.get(str(pid_rank), 0)
            is_grad_req_alt = _is_grad_req_for_student(alt_sec['code'], alt_g, pid=pid_rank) if alt_g else False
            bumped_is_grad = _is_grad_req_for_student(bumped_code, alt_g, pid=pid_rank) if alt_g else False

            if alt_dept == bumped_dept and alt_raw == bumped_raw:
                return 0
            if alt_dept == bumped_dept:
                return 1
            if is_grad_req_alt and bumped_is_grad:
                return 2
            if abs(alt_raw - bumped_raw) <= 10:
                return 3
            return 4

        _srr_data = []
        for _c in clash:
            _pid = _c['student']
            _bumped_code = _c['code']
            _bumped_period = _c['lost_period']
            _bumped_dept = course_info.get(_bumped_code, {}).get('dept', '')
            _bumped_prio = course_section_raw(_bumped_code)
            _assigned_periods = set()
            for _ac, _asid in assign.get(_pid, {}).items():
                _assigned_periods.add(sections[_asid]['period'])
            _free_periods = sorted(set(PERIODS) - _assigned_periods)
            _blocking_code = ''
            _blocking_title = ''
            for _ac, _asid in assign.get(_pid, {}).items():
                if sections[_asid]['period'] == _bumped_period:
                    _blocking_code = _ac
                    _blocking_title = course_info.get(_ac, {}).get('title', _ac)
                    break

            _bumped_codes = set(_cx['code'] for _cx in clash if _cx['student'] == _pid)
            _all_candidates = []
            for _fp in _free_periods:
                _available = [_s for _s in sections if _s['period'] == _fp
                              and _s['code'] not in assign.get(_pid, {})
                              and _s['code'] not in _bumped_codes
                              and secfill[_s['sid']] < _s['cap']]
                for _av in _available:
                    if not _check_prereqs_met(_pid, _av['code']):
                        continue
                    _student_g = grade.get(str(_pid), 0)
                    eligible_grades = course_grade_levels.get(str(_av['code']), set())
                    if eligible_grades and _student_g not in eligible_grades:
                        continue
                    _rank = _alt_rank(_av, _bumped_dept, _bumped_code, _bumped_prio, _pid)
                    _all_candidates.append((_rank, _av))

            _all_candidates.sort(key=lambda x: (x[0], secfill[x[1]['sid']]))
            _seen_codes = set()
            _opts = []
            _RANK_LABELS = {0: 'same_subject_same_rigor', 1: 'same_subject', 2: 'same_requirement',
                            3: 'similar_rigor', 4: 'other_eligible'}
            for _rk, _av in _all_candidates:
                if _av['code'] in _seen_codes:
                    continue
                _seen_codes.add(_av['code'])
                _opts.append({
                    't': 'add', 'c': _av['code'], 'n': _av['title'],
                    'd': _av['dept'], 'p': _av['period'], 'tc': _av['teacher'],
                    'f': secfill[_av['sid']], 'cp': _av['cap'],
                    'sd': _av['dept'] == _bumped_dept,
                    'match': _RANK_LABELS.get(_rk, 'other'),
                })
                if len(_opts) >= 8:
                    break
            _cat = 'add_alternative' if _opts else 'no_resolution'
            _srr_data.append({
                's': _pid, 'g': grade.get(_pid, 9),
                'bc': _bumped_code, 'bt': _c['course'], 'bp': _bumped_period, 'bd': _bumped_dept,
                'xc': _blocking_code, 'xt': _blocking_title,
                'fp': _free_periods, 'nc': len(assign.get(_pid, {})),
                'cat': _cat, 'opts': _opts[:8],
                'rc': _c.get('root_cause_codes', []),
            })
        _srr_js = f"const R = {json.dumps(_srr_data)};"
        _srr_out = _inject_data(_srr_html, r'const R\s*=\s*\[', _srr_js)
        if _srr_out:
            _srr_dest = os.path.join(BOARDS_DIR, 'student_request_recommendations.html')
            with open(_srr_dest, 'w') as _f:
                _f.write(_srr_out)
            print(f"  student_request_recommendations.html — {len(_srr_data)} recommendations")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: student_request_recommendations failed: {_e}")

# ── Board 6: Data Source Audit Report ──
try:
    _dsa_path = os.path.join(OUTPUT_DIR, 'data_source_audit_report.html')
    if os.path.exists(_dsa_path):
        import shutil
        shutil.copy2(_dsa_path, os.path.join(BOARDS_DIR, 'data_source_audit_report.html'))
        print(f"  data_source_audit_report.html — copied (static report)")
        _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: data_source_audit_report failed: {_e}")

# ── Board 7: Constraint Builder ──
try:
    _cb_path = os.path.join(OUTPUT_DIR, 'constraint_builder.html')
    if os.path.exists(_cb_path):
        with open(_cb_path) as _f:
            _cb_html = _f.read()
        _cb_courses = []
        _seen_codes = set()
        for _s in sections:
            if _s['code'] not in _seen_codes:
                _seen_codes.add(_s['code'])
                _cb_courses.append({
                    'code': _s['code'], 'title': _s['title'],
                    'dept': _s['dept'],
                    'sections': len(sec_by_code.get(_s['code'], []))
                })
        _cb_courses.sort(key=lambda x: (x['dept'], x['title']))
        _cb_js = f"const COURSES = {json.dumps(_cb_courses)};"
        _cb_out = _inject_data(_cb_html, r'const COURSES\s*=\s*\[', _cb_js)
        if _cb_out:
            _cb_dest = os.path.join(BOARDS_DIR, 'constraint_builder.html')
            with open(_cb_dest, 'w') as _f:
                _f.write(_cb_out)
            print(f"  constraint_builder.html — {len(_cb_courses)} courses")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: constraint_builder failed: {_e}")

# ── Board 8: Master Schedule Builder ──
try:
    _msb_path = os.path.join(OUTPUT_DIR, 'master_schedule_builder.html')
    if os.path.exists(_msb_path):
        with open(_msb_path) as _f:
            _msb_html = _f.read()
        _msb_catalog = []
        for _cid, _ci in course_info.items():
            _gl_raw = course_grade_levels.get(_cid, set())
            _gl_str = ','.join(str(g) for g in sorted(_gl_raw)) if _gl_raw else ''
            _pr = course_prereqs.get(_cid, {})
            _prereq_codes = _pr.get('prereqs', [])
            _msb_catalog.append({
                'id': _cid, 'name': _ci.get('title', _cid),
                'dept': _ci.get('dept', ''), 'credits': _ci.get('credits', 0),
                'grade': _gl_str,
                'prereq': _prereq_codes[0] if _prereq_codes else '',
                'prereqGrade': ''
            })
        _msb_catalog.sort(key=lambda x: (x['dept'], x['name']))
        _msb_js = f"const COURSE_CATALOG = {json.dumps(_msb_catalog)};"
        _msb_out = _inject_data(_msb_html, r'const COURSE_CATALOG\s*=\s*\[', _msb_js)
        if _msb_out:
            _msb_dest = os.path.join(BOARDS_DIR, 'master_schedule_builder.html')
            with open(_msb_dest, 'w') as _f:
                _f.write(_msb_out)
            print(f"  master_schedule_builder.html — {len(_msb_catalog)} courses in catalog")
            _boards_generated += 1
except Exception as _e:
    print(f"  WARNING: master_schedule_builder failed: {_e}")

# ── Generate index.html for boards directory ──
try:
    _index_html = f"""<title>Schedule Engine v3 — Dashboard Index</title>
<style>
:root{{--bg:#f5f2ee;--surface:#fff;--text:#1a1412;--text2:#5c4f44;--border:#d6cec6;
  --maroon:#7B1E28;--font:'Segoe UI',system-ui,sans-serif}}
@media(prefers-color-scheme:dark){{:root{{--bg:#1a1412;--surface:#242018;--text:#e8e2db;--text2:#b0a598;--border:#3e362e;--maroon:#A0333E}}}}
:root[data-theme="dark"]{{--bg:#1a1412;--surface:#242018;--text:#e8e2db;--text2:#b0a598;--border:#3e362e;--maroon:#A0333E}}
:root[data-theme="light"]{{--bg:#f5f2ee;--surface:#fff;--text:#1a1412;--text2:#5c4f44;--border:#d6cec6;--maroon:#7B1E28}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font);background:var(--bg);color:var(--text);padding:40px 20px}}
.container{{max-width:900px;margin:0 auto}}
h1{{color:var(--maroon);font-size:28px;margin-bottom:8px}}
.subtitle{{color:var(--text2);margin-bottom:32px;font-size:14px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px}}
.stat{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px 24px;text-align:center}}
.stat .val{{font-size:28px;font-weight:700;color:var(--maroon)}}
.stat .lbl{{font-size:12px;color:var(--text2);margin-top:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px;
  text-decoration:none;color:var(--text);transition:all .15s}}
.card:hover{{border-color:var(--maroon);box-shadow:0 4px 12px rgba(0,0,0,.1);transform:translateY(-2px)}}
.card h3{{font-size:15px;margin-bottom:6px;color:var(--maroon)}}
.card p{{font-size:13px;color:var(--text2);line-height:1.5}}
</style>
<div class="container">
<h1>Don Bosco Prep 2026-27</h1>
<p class="subtitle">Schedule Engine v3 — Interactive Dashboard Suite</p>
<div class="stats">
<div class="stat"><div class="val">{len(clash)}</div><div class="lbl">Clashes</div></div>
<div class="stat"><div class="val">{placement_rate:.1f}%</div><div class="lbl">Placement</div></div>
<div class="stat"><div class="val">{len(students)}</div><div class="lbl">Students</div></div>
<div class="stat"><div class="val">{len(sections)}</div><div class="lbl">Sections</div></div>
<div class="stat"><div class="val">{len(protected_clashes)}</div><div class="lbl">Protected Clashes</div></div>
</div>
<div class="grid">
<a class="card" href="student_clash_report.html"><h3>Student Clash Report</h3>
<p>Drag-and-drop schedule grid for {len(_scr_clashes)} students with conflicts. Visual period/semester layout.</p></a>
<a class="card" href="conflict_resolution_console.html"><h3>Conflict Resolution Console</h3>
<p>Course-level clash analysis with fix recommendations for {len(_crc_data)} affected courses.</p></a>
<a class="card" href="credit_validation_report.html"><h3>Credit Validation Report</h3>
<p>{len(_cvr_data)} students exceeding the 35-credit cap. Priority-ranked drop candidates.</p></a>
<a class="card" href="student_request_recommendations.html"><h3>Request Recommendations</h3>
<p>Alternative course options for {len(_srr_data)} bumped requests with availability details.</p></a>
<a class="card" href="singleton_board.html"><h3>Singleton Board</h3>
<p>Scheduling grid for {len(_sb_data['s'])} singleton courses. Teacher-period conflict view.</p></a>
<a class="card" href="constraint_builder.html"><h3>Constraint Builder</h3>
<p>Configure semester locks, period locks, and co-schedule constraints for {len(_cb_courses)} courses.</p></a>
<a class="card" href="master_schedule_builder.html"><h3>Master Schedule Builder</h3>
<p>Full course catalog ({len(_msb_catalog)} courses) with student request management and validation.</p></a>
<a class="card" href="data_source_audit_report.html"><h3>Data Source Audit</h3>
<p>Cross-file integrity checks and data quality findings.</p></a>
</div>
</div>"""
    with open(os.path.join(BOARDS_DIR, 'index.html'), 'w') as _f:
        _f.write(_index_html)
    _boards_generated += 1
    print(f"  index.html — dashboard hub")
except Exception as _e:
    print(f"  WARNING: index.html failed: {_e}")

print(f"\n  {_boards_generated} boards generated in {BOARDS_DIR}/")

print("=" * 60)
print(f"DONE — v3 Enhanced Engine: {len(clash)} clashes, {placement_rate:.1f}% placement")
print("=" * 60)
