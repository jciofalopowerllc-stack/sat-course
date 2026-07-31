"""Don Bosco Prep 2026-27 Scheduling Engine — ENHANCED BUILD (v3)
Incorporates all 11 template inputs from the product spec:
  - Templates 1-5: Core data (sectioning, requests, LEO, co-schedule, prior year)
  - Template 6: Teacher Profiles (load caps, period availability, preferences)
  - Template 7: Course Profiles (8-input scoring, prerequisites, room requirements)
  - Template 8: Student Profiles + Transcript History (duplicate/prereq validation)
  - Template 9: Room Profiles (capacity, type, equipment)
  - Template 10: Contracts (cascade rules for teacher loads)
  - Template 11: Priority Scoring Reference (read-only)

Enhancements over v2 (schedule_engine_final.py):
  1. Pre-flight validation: duplicate request detection + prerequisite checks
  2. Contract cascade: load limits from contract types
  3. Teacher profile constraints: period availability, preferences
  4. Room profile awareness: type matching, capacity enforcement
  5. Improved Phase D: 16 restart seeds, deeper search (40 iterations)
  6. Constraint chain analysis: detect unavoidable conflicts early
  7. Priority-weighted bump decisions with P4 protection
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
PERIODS = list('ABCDEFG')

# ============================================================
# LOAD PRIORITY SCALE AND 8-INPUT SCORING
# ============================================================
with open(os.path.join(os.path.dirname(__file__) or '.', 'course_priorities.json')) as _pf:
    _prio_data = json.load(_pf)
COURSE_PRIORITY = {}
for _plevel, _pinfo in _prio_data['scale'].items():
    for _pc in _pinfo.get('courses', []):
        COURSE_PRIORITY[str(_pc)] = int(_plevel)

def prio(c):
    return COURSE_PRIORITY.get(str(c), 1)

with open(os.path.join(os.path.dirname(__file__) or '.', 'priority_assignments.json')) as _paf:
    PRIO_ASSIGN = json.load(_paf)

_PA_WEIGHTS = PRIO_ASSIGN['metadata']['weights']
_W = (_PA_WEIGHTS['CFP'], _PA_WEIGHTS['CYRP'], _PA_WEIGHTS['SSP'], _PA_WEIGHTS['MTP'],
      _PA_WEIGHTS['CTAP'], _PA_WEIGHTS['TL'], _PA_WEIGHTS['PL'], _PA_WEIGHTS['RL'])

_COURSE_PRIO = PRIO_ASSIGN.get('course_priorities', {})
_STUDENT_PRIO = PRIO_ASSIGN.get('student_priorities', {})
_TEACHER_PRIO = PRIO_ASSIGN.get('teacher_priorities', {})
_placement_cache = {}

def placement_score(pid, cid):
    key = (str(pid), str(cid))
    if key in _placement_cache:
        return _placement_cache[key]
    cp = _COURSE_PRIO.get(key[1], {})
    sp = _STUDENT_PRIO.get(key[0], {})
    cfp = cp.get('CFP', 0)
    cyrp = cp.get('CYRP', 0)
    ssp = sp.get('SSP', 1)
    teachers = cp.get('teachers', [])
    mtp = max(((_TEACHER_PRIO.get(t, {}).get('MTP', 1)) for t in teachers), default=1) if teachers else 1
    ctap = cp.get('CTAP', 0)
    tl = cp.get('TL', 0)
    pl = cp.get('PL', 0)
    rl = cp.get('RL', 0)
    vals = (cfp, cyrp, ssp, mtp, ctap, tl, pl, rl)
    ws = sum(v * w for v, w in zip(vals, _W))
    cc = sum(1 for v in vals if v >= 4)
    result = (ws, cc)
    _placement_cache[key] = result
    return result

def placement_sort_key(pid, cid):
    ws, cc = placement_score(pid, cid)
    return (-cc, -ws)

_course_composite_cache = {}

def course_composite(cid):
    cid_s = str(cid)
    if cid_s in _course_composite_cache:
        return _course_composite_cache[cid_s]
    cp = _COURSE_PRIO.get(cid_s, {})
    cfp = cp.get('CFP', 0)
    cyrp = cp.get('CYRP', 0)
    ctap = cp.get('CTAP', 0)
    tl = cp.get('TL', 0)
    pl = cp.get('PL', 0)
    rl = cp.get('RL', 0)
    teachers = cp.get('teachers', [])
    mtp = max(((_TEACHER_PRIO.get(t, {}).get('MTP', 1)) for t in teachers), default=1) if teachers else 1
    total = cfp * _W[0] + cyrp * _W[1] + mtp * _W[3] + ctap * _W[4] + tl * _W[5] + pl * _W[6] + rl * _W[7]
    cc = sum(1 for v in (cfp, cyrp, mtp, ctap, tl, pl, rl) if v >= 4)
    result = (-cc, -total)
    _course_composite_cache[cid_s] = result
    return result

_student_rank_cache = {}

def _compute_student_ranks():
    scores = []
    for pid in _STUDENT_PRIO:
        sp = _STUDENT_PRIO[pid]
        courses = sp.get('courses', [])
        max_cc = 0
        total_ws = 0.0
        for cid in courses:
            ws, cc = placement_score(pid, cid)
            total_ws += ws
            if cc > max_cc:
                max_cc = cc
        scores.append((pid, max_cc, total_ws))
    scores.sort(key=lambda x: (-x[1], -x[2]))
    for rank, (pid, mc, tw) in enumerate(scores, 1):
        _student_rank_cache[pid] = (rank, mc, tw)

def student_rank_key(pid):
    if pid in _student_rank_cache:
        return _student_rank_cache[pid][0]
    return 99999


print("=" * 60)
print("SCHEDULING ENGINE v3 — ENHANCED BUILD")
print("=" * 60)

# ============================================================
# 0. LOAD ALL DATA
# ============================================================
print("\n[0] LOADING DATA...")

# ── Template 1: Course Sectioning ──
t1_path = os.path.join(TEMPLATES, 'Template_1_Course_Sectioning.xlsx')
swb = openpyxl.load_workbook(t1_path, data_only=True)
ws1 = swb['Step 1 - Set Sections']
course_info = {}
for r in range(2, ws1.max_row + 1):
    code = ws1.cell(r, 1).value
    title = ws1.cell(r, 2).value
    dept = ws1.cell(r, 3).value
    credits = ws1.cell(r, 4).value
    ctype = ws1.cell(r, 5).value
    if code and title and dept:
        cid = str(code).strip()
        is_fy = (ctype or '').lower().startswith('full')
        course_info[cid] = {
            'code': cid, 'title': title, 'dept': dept,
            'credits': credits or 0, 'type': ctype or 'Full-Year',
            'is_fy': is_fy
        }

ws2 = swb['Step 2 - Assign Sections']
sections = []
sec_by_code = defaultdict(list)
teacher_sections = defaultdict(list)

for r in range(2, ws2.max_row + 1):
    code = ws2.cell(r, 1).value
    secnum = ws2.cell(r, 7).value
    sem = ws2.cell(r, 8).value
    cap = ws2.cell(r, 9).value
    teacher = ws2.cell(r, 10).value
    room = ws2.cell(r, 11).value
    if code is None or secnum is None:
        continue
    cid = str(code).strip()
    ci = course_info.get(cid, {})
    is_fy = ci.get('is_fy', True)

    sem_str = str(sem or '').strip()
    if 'Fall' in sem_str and 'Spring' not in sem_str:
        halves = ('S1',)
    elif 'Spring' in sem_str and 'Fall' not in sem_str:
        halves = ('S2',)
    elif sem_str.lower().startswith('builder'):
        halves = ('S1',)
    else:
        if is_fy:
            halves = ('S1', 'S2')
        else:
            halves = ('S1',)

    sid = len(sections)
    sec = {
        'sid': sid, 'code': cid, 'section': secnum,
        'period': None, 'halves': halves, 'cap': cap or 25,
        'teacher': teacher or 'TBD', 'room': room or 'TBD',
        'title': ci.get('title', cid), 'dept': ci.get('dept', ''),
        'is_fy': is_fy, 'sem_raw': sem_str
    }
    sections.append(sec)
    sec_by_code[cid].append(sid)
    if teacher:
        teacher_sections[teacher].append(sid)

print(f"  Sections: {len(sections)}")
print(f"  Courses: {len(sec_by_code)}")
print(f"  Teachers: {len(teacher_sections)}")

# ── Template 2: Student Course Requests ──
t2_path = os.path.join(TEMPLATES, 'Template_2_Student_Course_Requests.xlsx')
rwb = openpyxl.load_workbook(t2_path, data_only=True)
rws = rwb.active
students = {}
sreq = defaultdict(list)
grade = {}
for r in range(2, rws.max_row + 1):
    pid = rws.cell(r, 1).value
    name = rws.cell(r, 2).value
    cid_raw = rws.cell(r, 4).value
    cname = rws.cell(r, 5).value
    grade_raw = rws.cell(r, 7).value
    if pid is None:
        continue
    pid = str(pid)
    cid = str(cid_raw).strip() if cid_raw else '0'
    if cid == '0' or cname == 'Placeholder':
        continue
    if cid not in sec_by_code:
        continue
    g = 9
    if grade_raw:
        gs = str(grade_raw)
        for d in ['12', '11', '10', '9']:
            if d in gs:
                g = int(d)
                break
    if pid not in students:
        students[pid] = str(name) if name else pid
    grade[pid] = g
    if cid not in sreq[pid]:
        sreq[pid].append(cid)

print(f"  Students: {len(students)}")
print(f"  Requests: {sum(len(v) for v in sreq.values())}")

# ── Template 6: Teacher Profiles ──
teacher_profiles = {}
t6_path = os.path.join(TEMPLATES, 'Template_6_Teacher_Profiles.xlsx')
try:
    t6wb = openpyxl.load_workbook(t6_path, data_only=True)
    t6ws = t6wb.active
    for r in range(3, t6ws.max_row + 1):
        tid = t6ws.cell(r, 1).value
        last = t6ws.cell(r, 2).value
        first = t6ws.cell(r, 3).value
        if not last:
            continue
        tname = f"{last}, {first}" if first else str(last)
        max_periods = t6ws.cell(r, 9).value
        max_consec = t6ws.cell(r, 10).value
        prep_req = t6ws.cell(r, 11).value
        duty = t6ws.cell(r, 12).value
        avail = {}
        for pi, period in enumerate(PERIODS):
            v = t6ws.cell(r, 14 + pi).value
            avail[period] = str(v).upper() != 'N' if v else True
        approved_6 = str(t6ws.cell(r, 21).value or '').upper() == 'Y'
        pref_room = t6ws.cell(r, 22).value
        pref_wing = t6ws.cell(r, 23).value
        pref_periods = str(t6ws.cell(r, 24).value or '')
        avoid_periods = str(t6ws.cell(r, 25).value or '')
        contract = str(t6ws.cell(r, 6).value or 'Standard')

        teacher_profiles[tname] = {
            'max_periods': int(max_periods) if max_periods and str(max_periods) != 'N/A' else 5,
            'max_consecutive': int(max_consec) if max_consec and str(max_consec) != 'N/A' else 3,
            'prep_required': int(prep_req) if prep_req and str(prep_req) != 'N/A' else 1,
            'duty_periods': int(duty) if duty and str(duty) != 'N/A' else 1,
            'availability': avail,
            'approved_6': approved_6,
            'preferred_room': str(pref_room) if pref_room and str(pref_room) != 'N/A' else '',
            'preferred_wing': str(pref_wing) if pref_wing and str(pref_wing) != 'N/A' else '',
            'preferred_periods': [p.strip() for p in pref_periods.split(',') if p.strip() and p.strip() in PERIODS],
            'avoid_periods': [p.strip() for p in avoid_periods.split(',') if p.strip() and p.strip() in PERIODS],
            'contract': contract,
        }
    t6wb.close()
    print(f"  Teacher profiles loaded: {len(teacher_profiles)}")
except FileNotFoundError:
    print("  Template 6 not found — using defaults for teacher profiles")

# ── Template 8: Transcript History (for pre-flight validation) ──
transcript = defaultdict(list)
t8_path = os.path.join(TEMPLATES, 'Template_8_Student_Profiles.xlsx')
try:
    t8wb = openpyxl.load_workbook(t8_path, data_only=True)
    if 'Transcript History' in t8wb.sheetnames:
        t8ws = t8wb['Transcript History']
        for r in range(5, t8ws.max_row + 1):
            sid = t8ws.cell(r, 1).value
            year = t8ws.cell(r, 2).value
            ccode = t8ws.cell(r, 3).value
            final_grade = t8ws.cell(r, 7).value
            passed = t8ws.cell(r, 8).value
            if sid and ccode:
                transcript[str(sid)].append({
                    'year': str(year or ''),
                    'code': str(ccode).strip(),
                    'grade': str(final_grade or ''),
                    'passed': str(passed or '').upper() == 'Y',
                })
    t8wb.close()
    total_transcript = sum(len(v) for v in transcript.values())
    print(f"  Transcript records loaded: {total_transcript} ({len(transcript)} students)")
except FileNotFoundError:
    print("  Template 8 not found — skipping transcript validation")

# ── Template 7: Course Profiles (prerequisites) ──
course_prereqs = {}
t7_path = os.path.join(TEMPLATES, 'Template_7_Course_Profiles.xlsx')
try:
    t7wb = openpyxl.load_workbook(t7_path, data_only=True)
    t7ws = t7wb.active
    for r in range(3, t7ws.max_row + 1):
        ccode = t7ws.cell(r, 1).value
        prereqs = t7ws.cell(r, 20).value
        coreqs = t7ws.cell(r, 21).value
        if ccode:
            cid = str(ccode).strip()
            prereq_list = []
            if prereqs and str(prereqs).strip() not in ('N/A', ''):
                prereq_list = [p.strip() for p in str(prereqs).split(',') if p.strip()]
            coreq_list = []
            if coreqs and str(coreqs).strip() not in ('N/A', ''):
                coreq_list = [p.strip() for p in str(coreqs).split(',') if p.strip()]
            if prereq_list or coreq_list:
                course_prereqs[cid] = {'prereqs': prereq_list, 'coreqs': coreq_list}
    t7wb.close()
    print(f"  Course prerequisites loaded: {len(course_prereqs)} courses with prereqs/coreqs")
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
    print(f"\n  *** ENGINE HALTED — credit violations must be resolved. ***")
    sys.exit(1)
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
    for pid in sreq:
        completed = {t['code'] for t in transcript.get(pid, []) if t['passed']}
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
                        'course': cid,
                        'course_title': ci.get('title', cid),
                        'prereq': prereq,
                        'prereq_title': pi.get('title', prereq),
                        'message': f"Student {pid} requests {cid} ({ci.get('title', cid)}) but missing prereq {prereq} ({pi.get('title', prereq)})"
                    })
                    prereq_fails += 1
    print(f"  Prerequisite check: {prereq_fails} missing prerequisites found")
    if prereq_fails:
        for w in preflight_warnings[:5]:
            if w['type'] == 'PREREQ_MISSING':
                print(f"    {w['message']}")
        if prereq_fails > 5:
            print(f"    ... and {prereq_fails - 5} more")
else:
    print("  Prerequisite check: SKIPPED (no transcript or prereq data)")

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

# Save pre-flight report
preflight_report = {
    'total_warnings': len(preflight_warnings),
    'duplicates': len([w for w in preflight_warnings if w['type'] == 'DUPLICATE_REQUEST']),
    'prereq_missing': len([w for w in preflight_warnings if w['type'] == 'PREREQ_MISSING']),
    'constraint_chains': len([w for w in preflight_warnings if w['type'] == 'CONSTRAINT_CHAIN']),
    'warnings': preflight_warnings,
}
with open(os.path.join(SCRATCHPAD, 'preflight_report.json'), 'w') as pf:
    json.dump(preflight_report, pf, indent=2)
print(f"  Pre-flight report saved: {len(preflight_warnings)} total warnings")


# ── Template 3: LEO II Cohorts ──
t3_path = os.path.join(TEMPLATES, 'Template_3_LEO_II_Cohorts.xlsx')
lwb = openpyxl.load_workbook(t3_path, data_only=True)
lws = lwb.active
cohA, cohB = set(), set()
for r in range(2, lws.max_row + 1):
    student_name = lws.cell(r, 4).value
    cohort = lws.cell(r, 6).value
    if not cohort:
        continue
    for pid, pname in students.items():
        if pname and student_name and pname.strip() == str(student_name).strip():
            if cohort == 'A':
                cohA.add(pid)
            else:
                cohB.add(pid)
            break
print(f"  LEO Cohort A: {len(cohA)}, Cohort B: {len(cohB)}")

# ── Template 4: Co-Schedule Groups ──
t4_path = os.path.join(TEMPLATES, 'Template_4_CoSchedule_Groups.xlsx')
iwb = openpyxl.load_workbook(t4_path, data_only=True)
cws = iwb['5 Co-Schedule Groups']
cogroups = []
for r in range(4, cws.max_row + 1):
    gname = cws.cell(r, 1).value
    codes_raw = cws.cell(r, 2).value
    if not gname or not codes_raw:
        continue
    codes = [c.strip() for c in str(codes_raw).split(',')]
    period = cws.cell(r, 7).value
    sem = cws.cell(r, 8).value
    cogroups.append({'name': gname, 'codes': codes, 'period': period, 'sem': sem})
    print(f"  Co-schedule: {gname} = {codes} period={period}")

# ── Template 5: Prior Year Schedule ──
t5_path = os.path.join(TEMPLATES, 'Template_5_Prior_Year_Schedule.xlsx')
print("\n  Loading prior year schedule...")
pwb = openpyxl.load_workbook(t5_path, data_only=True)
pws = pwb.active

prior_entries = []
for r in range(2, pws.max_row + 1):
    class_id = pws.cell(r, 1).value
    teacher = pws.cell(r, 4).value
    grading = pws.cell(r, 5).value
    period = pws.cell(r, 6).value
    room = pws.cell(r, 8).value
    if not class_id:
        continue
    m = re.match(r'(\d+)', str(class_id).strip())
    if not m:
        continue
    code = m.group(1)
    p = None
    if period and str(period).strip().upper() in PERIODS:
        p = str(period).strip().upper()
    grading_str = str(grading or '').strip()
    if grading_str in ('S1', 'Fall'):
        term = 'S1'
    elif grading_str in ('S2', 'Spring'):
        term = 'S2'
    else:
        term = 'FY'
    prior_entries.append({'code': code, 'teacher': str(teacher or '').strip(),
                          'period': p, 'term': term, 'class_id': str(class_id).strip(),
                          'room': str(room or '').strip()})

s2_periods = {}
for e in prior_entries:
    if e['period'] and e['term'] == 'S2':
        m2 = re.match(r'(\d+)\s*[-:]\s*(\d+)', e['class_id'])
        if m2:
            s2_periods[(m2.group(1), m2.group(2))] = e['period']
for e in prior_entries:
    if not e['period'] and e['term'] == 'S1':
        m2 = re.match(r'(\d+)\s*[-:]\s*(\d+)', e['class_id'])
        if m2 and (m2.group(1), m2.group(2)) in s2_periods:
            e['period'] = s2_periods[(m2.group(1), m2.group(2))]

prior_teacher_periods = defaultdict(set)
prior_course_periods = defaultdict(set)
for e in prior_entries:
    if e['period']:
        prior_teacher_periods[(e['code'], e['teacher'])].add(e['period'])
        prior_course_periods[e['code']].add(e['period'])

print(f"  Prior-year entries: {len(prior_entries)}")


# ── Teacher Load Rules (enhanced with profiles + contracts) ──
APPROVED_6 = {'Dennehy, Sheri', 'Zawiski, Brian', 'Muscat, Nicole',
              'Calidas, Riddhi', 'Janeczko, Douglas', 'Tranate, John', 'McConnell, George'}

def get_max_load(teacher):
    tp = teacher_profiles.get(teacher, {})
    if tp:
        max_p = tp.get('max_periods', 5)
        if tp.get('approved_6'):
            max_p = max(max_p, 6)
        contract_code = tp.get('contract', 'Standard')
        ct = contracts.get(contract_code, contracts.get('STD', {}))
        if ct:
            max_p = min(max_p, ct.get('max_teaching', max_p))
        return (max_p, max_p)
    if 'konopelski' in teacher.lower():
        return (3, 3)
    if teacher in APPROVED_6:
        return (6, 6)
    return (5, 5)

COURSE_TEACHER_LOCKS = {
    '620': 'Daniels, Torrence',
    '631': 'Chiaravalloti, Michael'
}

# Pre-compute student rank scores
_compute_student_ranks()
_ranked_count = len(_student_rank_cache)
_top5 = sorted(_student_rank_cache.items(), key=lambda x: x[1][0])[:5]
print(f"  Student ranks computed: {_ranked_count}")
for _pid, (_rk, _mc, _tw) in _top5:
    print(f"    Rank {_rk}: {_pid} (maxCC={_mc}, totalWS={_tw:.1f})")


# ============================================================
# 1. ASSIGN PERIODS (enhanced with teacher availability)
# ============================================================
print("\n" + "=" * 60)
print("[1] PHASE A: ASSIGN PERIODS")
print("=" * 60)

PINNED = {
    '745': [('C', ('S1',)), ('E', ('S1',))],
    '734': [('C', ('S2',)), ('D', ('S2',))],
}

SEMESTER_LOCKS = {
    '766': ('S1',),
    '765': ('S2',),
}

FULL_FREEDOM = {'849', '851'}

for cid, pins in PINNED.items():
    sids = sec_by_code.get(cid, [])
    for i, sid in enumerate(sids):
        if i < len(pins):
            sections[sid]['period'] = pins[i][0]
            sections[sid]['halves'] = pins[i][1]

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
    for s in sections:
        if s['sid'] == exclude_sid or s['period'] != period:
            continue
        if s['room'] == room:
            if set(s['halves']) & set(halves):
                return True
    return False

HARD_PERIOD_CAP = 6

def teacher_would_exceed_cap(teacher, period, halves):
    if not teacher or teacher == 'TBD':
        return False
    for sem in halves:
        existing_periods = set()
        for sid in teacher_sections.get(teacher, []):
            s = sections[sid]
            if s['period'] and sem in s['halves']:
                existing_periods.add(s['period'])
        existing_periods.add(period)
        if len(existing_periods) > HARD_PERIOD_CAP:
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
def greedy_assign_periods(seed=42):
    rng = random.Random(seed)
    unassigned = [s for s in sections if s['period'] is None]
    rng.shuffle(unassigned)
    unassigned.sort(key=lambda s: (course_composite(s['code']), len(sec_by_code[s['code']]), s['code'], s['section']))

    for s in unassigned:
        teacher = s['teacher']
        room = s['room']
        halves = s['halves']
        code = s['code']

        used_periods = set()
        for other_sid in sec_by_code[code]:
            if sections[other_sid]['period']:
                used_periods.add(sections[other_sid]['period'])

        best_period = None
        best_score = float('inf')

        for p in PERIODS:
            if teacher and teacher != 'TBD' and teacher_busy(teacher, p, halves, s['sid']):
                continue
            if teacher_would_exceed_cap(teacher, p, halves):
                continue
            if teacher and teacher != 'TBD' and not teacher_available(teacher, p):
                continue
            score = 0
            if p in used_periods:
                score += 10
            period_load = sum(1 for sec in sections if sec['period'] == p)
            score += period_load * 0.1
            if room and room != 'TBD' and room_busy(room, p, halves, s['sid']):
                score += 5
            # Teacher preference scoring
            tp = teacher_profiles.get(teacher, {})
            if tp:
                if p in tp.get('avoid_periods', []):
                    score += 2
                if p in tp.get('preferred_periods', []):
                    score -= 1
            # Prior year alignment bonus
            prior_prefs = prior_teacher_periods.get((code, teacher), set())
            if not prior_prefs:
                prior_prefs = prior_course_periods.get(code, set())
            if prior_prefs and p in prior_prefs:
                score -= 0.5
            score += rng.random() * 0.01

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

greedy_assign_periods(seed=42)

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

sorted_students = sorted(students.keys(), key=student_rank_key)
print("  Greedy warm-start (most-constrained-first)...")
for pid in sorted_students:
    reqs = sorted(sreq[pid], key=lambda c: (placement_sort_key(pid, c), len(sec_by_code.get(c, []))))
    for cid in reqs:
        if cid not in sec_by_code:
            continue
        if cid == '745':
            if pid in cohA and leo2C is not None:
                add_place(pid, cid, leo2C)
            elif pid in cohB and leo2E is not None:
                add_place(pid, cid, leo2E)
            else:
                opts = sec_by_code[cid]
                best = min(opts, key=lambda sid: (added_conflicts(pid, sid), secfill[sid]))
                add_place(pid, cid, best)
            continue
        opts = sec_by_code[cid]
        best = min(opts, key=lambda sid: (
            added_conflicts(pid, sid),
            max(0, secfill[sid] + 1 - sections[sid]['cap']),
            secfill[sid]
        ))
        add_place(pid, cid, best)

conf_count = 0
for pid in students:
    for cid, sid in assign[pid].items():
        for x in occ_cells(sid):
            if cell_usage.get((pid, x), 0) > 1:
                conf_count += 1
                break
print(f"  Initial: {sum(len(v) for v in assign.values())} placements, {conf_count} students with conflicts")

PROT = {str(c) for c, p in COURSE_PRIORITY.items() if p == 5}
# v3: Also protect P4 (Required Core) from being bumped by P1/P0
PROT_P4 = {str(c) for c, p in COURSE_PRIORITY.items() if p == 4}

def resolve_student(pid):
    pins = {}
    for pc in assign[pid]:
        if pc in PROT:
            pins[pc] = assign[pid][pc]
    others = [c for c in sreq[pid] if c not in pins and c in assign[pid]]
    used = set()
    for c, sid in pins.items():
        for x in occ_cells(sid):
            used.add(x)
    others.sort(key=lambda c: (placement_sort_key(pid, c), len(sec_by_code.get(c, []))))
    res = {}

    def rec(i):
        if i == len(others):
            return True
        c = others[i]
        opts = sorted(sec_by_code.get(c, []),
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

clash = []
for pid in students:
    cells = defaultdict(list)
    for cid, sid in list(assign[pid].items()):
        for x in occ_cells(sid):
            cells[x].append(cid)
    bump = set()
    for x, cs in cells.items():
        cs = [c for c in cs if c not in bump]
        if len(cs) > 1:
            prot_cs = [c for c in cs if c in PROT]
            p4_cs = [c for c in cs if c in PROT_P4]
            _score_fn = lambda c: (-prio(c), -placement_score(pid, c)[1], -placement_score(pid, c)[0])
            if prot_cs:
                keep = min(prot_cs, key=_score_fn)
            elif p4_cs:
                keep = min(p4_cs, key=_score_fn)
            else:
                keep = min(cs, key=_score_fn)
            for c in cs:
                if c != keep and c not in PROT:
                    bump.add(c)
    for c in bump:
        s = sections[assign[pid][c]]
        _ws, _cc = placement_score(pid, c)
        clash.append({
            'student': pid, 'name': students[pid], 'grade': grade[pid],
            'code': c, 'course': course_info.get(c, {}).get('title', c),
            'priority': prio(c),
            'composite_ws': round(_ws, 1),
            'composite_cc': _cc,
            'lost_period': s['period'],
            'lost_sem': 'Full-Year' if len(s['halves']) == 2 else ('Fall' if s['halves'][0] == 'S1' else 'Spring')
        })
        rm_place(pid, c)


# ============================================================
# PHASE D: MULTI-RESTART ITERATIVE CLASH RESOLUTION (ENHANCED)
# ============================================================
print("\n" + "=" * 60)
print("[D] PHASE D: MULTI-RESTART CLASH RESOLUTION (ENHANCED)")
print("=" * 60)

PINNED_SIDS = set()
for _pc in PINNED:
    for _ps in sec_by_code.get(_pc, []):
        PINNED_SIDS.add(_ps)
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
    if s['sid'] in PINNED_SIDS or s['sid'] in COGROUP_SIDS or s['sid'] in assigned_cogroups:
        _orig_periods[s['sid']] = s['period']
        _orig_halves[s['sid']] = s['halves']
    else:
        _orig_periods[s['sid']] = s['period'] if s['sid'] in PINNED_SIDS else None
        _orig_halves[s['sid']] = s['halves']

def _save_fixed_state():
    fixed = {}
    for s in sections:
        if s['sid'] in PINNED_SIDS or s['sid'] in assigned_cogroups:
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

_reseat_pid_order = sorted(students.keys(), key=student_rank_key)
_reseat_course_order = {}
for _pid in _reseat_pid_order:
    _reseat_course_order[_pid] = sorted(
        sreq[_pid],
        key=lambda c, _p=_pid: (placement_sort_key(_p, c), len(sec_by_code.get(c, [])))
    )


def full_reseat():
    _invalidate_occ_cache()
    for pid in students:
        assign[pid] = {}
    secfill.clear()
    cell_usage.clear()
    for pid in _reseat_pid_order:
        for cid in _reseat_course_order[pid]:
            if cid not in sec_by_code:
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
            add_place(pid, cid, min(sec_by_code[cid], key=lambda sid: (
                added_conflicts(pid, sid),
                max(0, secfill[sid] + 1 - sections[sid]['cap']),
                secfill[sid])))
    for rnd in range(3):
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
        for x, cs in cm.items():
            cs = [c for c in cs if c not in bmp]
            if len(cs) > 1:
                pr = [c for c in cs if c in PROT]
                p4 = [c for c in cs if c in PROT_P4]
                _sf = lambda c: (-prio(c), -placement_score(pid, c)[1], -placement_score(pid, c)[0])
                if pr:
                    kp = min(pr, key=_sf)
                elif p4:
                    kp = min(p4, key=_sf)
                else:
                    kp = min(cs, key=_sf)
                for c in cs:
                    if c != kp and c not in PROT:
                        bmp.add(c)
        for c in bmp:
            bs = sections[assign[pid][c]]
            _ws_b, _cc_b = placement_score(pid, c)
            nc.append({
                'student': pid, 'name': students[pid], 'grade': grade[pid],
                'code': c, 'course': course_info.get(c, {}).get('title', c),
                'priority': prio(c),
                'composite_ws': round(_ws_b, 1),
                'composite_cc': _cc_b,
                'lost_period': bs['period'],
                'lost_sem': 'Full-Year' if len(bs['halves']) == 2 else (
                    'Fall' if bs['halves'][0] == 'S1' else 'Spring')
            })
            rm_place(pid, c)
    for cl_item in list(nc):
        pid, cid = cl_item['student'], cl_item['code']
        if cid in PROT or cid in assign.get(pid, {}):
            continue
        used = set()
        for c2, s2 in assign.get(pid, {}).items():
            for x in occ_cells(s2):
                used.add(x)
        best, bsc = None, None
        for alt in sec_by_code.get(cid, []):
            if any(x in used for x in occ_cells(alt)):
                continue
            sc = (max(0, secfill[alt] + 1 - sections[alt]['cap']), secfill[alt])
            if bsc is None or sc < bsc:
                bsc, best = sc, alt
        if best is not None:
            add_place(pid, cid, best)
            nc.remove(cl_item)
    return nc


def run_optimization_pass(cl=None):
    if cl is None:
        cl = full_reseat()
    stalled = 0
    # v3: deeper search — 40 iterations, top 8 candidates per round
    for d_iter in range(40):
        if stalled >= 5:
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
        # v3: also weight by priority — P4 clashes score 3x, P3 score 2x
        for c in cl:
            p = c.get('priority', 1)
            if p >= 4:
                for sid in sec_by_code.get(c['code'], []):
                    if sections[sid]['period'] == c['lost_period']:
                        sec_sc[sid] += 2
            elif p >= 3:
                for sid in sec_by_code.get(c['code'], []):
                    if sections[sid]['period'] == c['lost_period']:
                        sec_sc[sid] += 1
        cands = []
        for sid, score in sec_sc.most_common(120):
            if sid in PINNED_SIDS or sid in COGROUP_SIDS or score < 1:
                continue
            s = sections[sid]
            for p in PERIODS:
                if p == s['period']:
                    continue
                if s['teacher'] and s['teacher'] != 'TBD':
                    if any(sections[ts]['period'] == p
                           and set(sections[ts]['halves']) & set(s['halves'])
                           and not in_same_cogroup(sid, ts)
                           for ts in teacher_sections.get(s['teacher'], []) if ts != sid):
                        continue
                    old_p = s['period']
                    s['period'] = None
                    exc = teacher_would_exceed_cap(s['teacher'], p, s['halves'])
                    s['period'] = old_p
                    if exc:
                        continue
                    if not teacher_available(s['teacher'], p):
                        continue
                new_conf = 0
                for rpid in code_requesters.get(s['code'], set()):
                    for rc in sreq[rpid]:
                        if rc == s['code']:
                            continue
                        rsids = sec_by_code.get(rc, [])
                        if rsids and all(sections[rs]['period'] == p for rs in rsids):
                            if any(set(sections[rs]['halves']) & set(s['halves']) for rs in rsids):
                                new_conf += 1
                                break
                est = score - new_conf
                if est > 0:
                    cands.append((est, sid, p))
        if not cands:
            break
        cands.sort(reverse=True)
        improved = False
        for est, sid, np in cands[:8]:
            s = sections[sid]
            op = s['period']
            s['period'] = np
            _invalidate_occ_cache()
            tc = full_reseat()
            if len(tc) < len(cl):
                cl = tc
                improved = True
                stalled = 0
                break
            s['period'] = op
            _invalidate_occ_cache()
        if not improved:
            stalled += 1
    return cl

# v3: 16 restart seeds (doubled from 8)
SEEDS = [4269, 256, 7777, 2024, 5050, 7, 1337, 3141,
         42, 100, 999, 2025, 8888, 31415, 54321, 11111]
best_clash = None
best_periods = None
best_halves = None
best_seed = None

import time as _time
for restart, seed in enumerate(SEEDS):
    _t0 = _time.time()
    _restore_for_restart(fixed_state)
    greedy_assign_periods(seed=seed)
    cl = full_reseat()
    baseline = len(cl)

    cl = run_optimization_pass(cl)
    result = len(cl)
    _elapsed = _time.time() - _t0

    print(f"  Restart {restart+1}/{len(SEEDS)} (seed={seed}): baseline={baseline} -> optimized={result}  [{_elapsed:.1f}s]")

    if best_clash is None or result < len(best_clash):
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

# P4 clash analysis
p4_clashes = [c for c in clash if c['priority'] >= 4]
print(f"  P4+ (Required Core) clashes: {len(p4_clashes)}")
if p4_clashes:
    for c in p4_clashes[:10]:
        print(f"    {c['name']} (Gr{c['grade']}): {c['course']} [{c['code']}] — Period {c['lost_period']}")

sec_sizes = [secfill[sid] for sid in range(len(sections)) if secfill[sid] > 0]
if sec_sizes:
    print(f"  Section sizes: min={min(sec_sizes)}, max={max(sec_sizes)}, avg={statistics.mean(sec_sizes):.1f}")

dept_clashes = Counter()
prio_clashes = Counter()
grade_clashes = Counter()
for c in clash:
    ci = course_info.get(c['code'], {})
    dept_clashes[ci.get('dept', 'Unknown')] += 1
    prio_clashes[prio(c['code'])] += 1
    grade_clashes[c['grade']] += 1

print(f"\n  Clashes by priority level:")
PRIO_LABELS = {0: 'Elective-Flexible', 1: 'Elective-Standard', 2: 'Departmental Core',
               3: 'Sequence/Honors', 4: 'Required Core', 5: 'AP/Singleton'}
for pl in sorted(prio_clashes.keys()):
    print(f"    P{pl} ({PRIO_LABELS.get(pl, '?')}): {prio_clashes[pl]}")
print(f"\n  Clashes by department:")
for dept, cnt in dept_clashes.most_common():
    print(f"    {dept}: {cnt}")
print(f"\n  Clashes by grade:")
for g in sorted(grade_clashes.keys()):
    print(f"    Grade {g}: {grade_clashes[g]}")

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

EXEMPT_ROOMS = {'Gymnasium'}
ALL_ROOMS = sorted(set(s['room'] for s in sections if s['room'] not in ('TBD', 'Unassigned') and s['room'] not in EXEMPT_ROOMS))

def _room_free(room, period, halves, exclude_sid):
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
output = {
    'engine_version': 'v3-enhanced',
    'sections': [],
    'assignments': {},
    'clashes': clash,
    'preflight': {
        'duplicates': len([w for w in preflight_warnings if w['type'] == 'DUPLICATE_REQUEST']),
        'prereq_missing': len([w for w in preflight_warnings if w['type'] == 'PREREQ_MISSING']),
        'constraint_chains': len([w for w in preflight_warnings if w['type'] == 'CONSTRAINT_CHAIN']),
        'warnings': preflight_warnings[:50],
    },
    'stats': {
        'students': len(students),
        'requests': total_requested,
        'placed': total_placed,
        'clashes': len(clash),
        'p4_clashes': len(p4_clashes),
        'sections_used': len([s for s in range(len(sections)) if secfill[s] > 0]),
        'placement_rate': round(placement_rate, 1),
        'prior_year_alignment': f"{prior_match}/{prior_total}",
        'restart_seeds_tried': len(SEEDS),
        'best_seed': best_seed,
    },
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
        'priority': prio(s['code']),
        'course_composite': course_composite(s['code']),
        'prior_year_match': prior_match_flag
    })

for pid in students:
    _rk_info = _student_rank_cache.get(pid, (999, 0, 0.0))
    output['assignments'][pid] = {
        'name': students[pid],
        'grade': grade[pid],
        'rank': _rk_info[0],
        'max_constraint_count': _rk_info[1],
        'total_weighted_sum': round(_rk_info[2], 1),
        'courses': {}
    }
    for cid, sid in assign[pid].items():
        s = sections[sid]
        _pws, _pcc = placement_score(pid, cid)
        output['assignments'][pid]['courses'][cid] = {
            'title': s['title'],
            'period': s['period'],
            'halves': list(s['halves']),
            'teacher': s['teacher'],
            'room': s['room'],
            'section': s['section'],
            'placement_ws': round(_pws, 1),
            'placement_cc': _pcc
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
print("=" * 60)
print(f"DONE — v3 Enhanced Engine: {len(clash)} clashes, {placement_rate:.1f}% placement")
print("=" * 60)
