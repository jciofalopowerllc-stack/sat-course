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
  1. Pre-flight validation: duplicate detection + prerequisite + grade eligibility
     - Transcript-based duplicate detection (students re-requesting passed courses)
     - Prerequisite chain validation with has_transcript flag
     - Grade-level eligibility check (student grade vs. course approved grades)
     - Auto-generates Preflight_Validation_Report.xlsx for review
  2. Contract cascade: load limits from contract types
  3. Teacher profile constraints: period availability, preferences
  4. Room profile awareness: type matching, capacity enforcement
  5. Improved Phase D: 16 restart seeds, deeper search (40 iterations)
  6. Constraint chain analysis: detect unavoidable conflicts early
  7. Priority-weighted bump decisions with P4 protection

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

# ============================================================
# LOAD PRIORITY SCALE AND 8-INPUT SCORING
# ============================================================
with open(os.path.join(os.path.dirname(__file__) or '.', 'course_priorities.json')) as _pf:
    _prio_data = json.load(_pf)
COURSE_PRIORITY = {}
for _plevel, _pinfo in _prio_data['scale'].items():
    for _pc in _pinfo.get('courses', []):
        COURSE_PRIORITY[str(_pc)] = int(_plevel)
SINGLETON_COURSES = set(str(c) for c in _prio_data.get('singleton_courses', []))

# ── Graduation-Requirement Subject Mapping ──
# Required departments by grade level (from DON_BOSCO_PREP_REQUIRED_SUBJECTS_AND_CREDITS.xlsx)
# Priority is DYNAMIC per student: a course's effective priority depends on whether
# it fulfills a REQUIRED SUBJECT for that student's grade level.
# Courses in required departments get a graduation-requirement bonus.
# All other courses are electives regardless of AP/Honors status.
_grad_req = _prio_data.get('graduation_requirements', {})
GRAD_REQ_DEPTS = {
    9:  set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])),
    10: set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])),
    11: set(_grad_req.get('grades_9_10_11', {}).get('required_departments', [])),
    12: set(_grad_req.get('grade_12', {}).get('required_departments', []))
         | set(_grad_req.get('grade_12', {}).get('required_either', [])),
}
# ── Priority Band System ──
# Band 1 (GRAD_REQ_BAND): courses required for the student's grade-level graduation.
# Band 2 (ELECTIVE_BAND): all other courses (electives), regardless of AP/Honors/restrictions.
# Band 1 courses are ALWAYS ranked higher than Band 2 courses for the same student.
# Within each band, the static course tier (P0-P5) determines relative order.
# The band offset guarantees separation: the lowest Band 1 score (100 + P0 = 100)
# always exceeds the highest Band 2 score (0 + P5 = 5).
GRAD_REQ_BAND = 100
ELECTIVE_BAND = 0

def prio(c):
    """Static course priority (grade-agnostic). Use student_prio() for bump decisions."""
    return COURSE_PRIORITY.get(str(c), 1)

def is_singleton(c):
    return str(c) in SINGLETON_COURSES

# _course_dept_map populated after course_info is loaded (Template 1)
_course_dept_map = {}

def _is_grad_req_dept(cid, student_grade):
    """Check if a course belongs to a department required for the student's grade level."""
    dept = _course_dept_map.get(str(cid), '')
    return dept in GRAD_REQ_DEPTS.get(student_grade, set())

def student_prio(pid, cid):
    """Dynamic per-student priority using the two-band system.
    Band 1 (100+): graduation-required courses — never bumped in favor of an elective.
    Band 2 (0-5): electives — scored by course tier within the band.
    The lowest possible Band 1 score (100) always exceeds the highest Band 2 score (5)."""
    base = prio(cid)
    g = grade.get(str(pid), 0)
    if g and _is_grad_req_dept(cid, g):
        return GRAD_REQ_BAND + base
    return ELECTIVE_BAND + base

with open(os.path.join(os.path.dirname(__file__) or '.', 'priority_assignments.json')) as _paf:
    PRIO_ASSIGN = json.load(_paf)

_PA_WEIGHTS = PRIO_ASSIGN['metadata']['weights']
_W = (_PA_WEIGHTS['CFP'], _PA_WEIGHTS['CYRP'], _PA_WEIGHTS['SSP'], _PA_WEIGHTS['MTP'],
      _PA_WEIGHTS['CTAP'], _PA_WEIGHTS['TL'], _PA_WEIGHTS['PL'], _PA_WEIGHTS['RL'],
      _PA_WEIGHTS.get('SC', 1.5), _PA_WEIGHTS.get('CR', 1.5))

_COURSE_PRIO = PRIO_ASSIGN.get('course_priorities', {})
_STUDENT_PRIO = PRIO_ASSIGN.get('student_priorities', {})
_TEACHER_PRIO = PRIO_ASSIGN.get('teacher_priorities', {})
_placement_cache = {}

# Item 5: Scarcity + ConflictRisk (computed after data load, updated dynamically)
_scarcity_scores = {}
_conflict_risk_scores = {}

def _compute_scarcity():
    """Scarcity: fewer sections = higher score. 1 section=5, 2=4, 3=3, 4-5=2, 6+=1, 0=0."""
    _scarcity_scores.clear()
    for cid, sids in sec_by_code.items():
        n = len(sids)
        if n == 0:
            _scarcity_scores[cid] = 0
        elif n == 1:
            _scarcity_scores[cid] = 5
        elif n == 2:
            _scarcity_scores[cid] = 4
        elif n == 3:
            _scarcity_scores[cid] = 3
        elif n <= 5:
            _scarcity_scores[cid] = 2
        else:
            _scarcity_scores[cid] = 1

def _compute_conflict_risk():
    """ConflictRisk per student-course: count how many of the student's OTHER requests
    share sections in the same period as this course's sections. Higher = more risk."""
    _conflict_risk_scores.clear()

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
    sc = _scarcity_scores.get(key[1], 1)
    cr = _conflict_risk_scores.get(key, 0)
    vals = (cfp, cyrp, ssp, mtp, ctap, tl, pl, rl, sc, cr)
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
    sc = _scarcity_scores.get(cid_s, 1)
    total = cfp * _W[0] + cyrp * _W[1] + mtp * _W[3] + ctap * _W[4] + tl * _W[5] + pl * _W[6] + rl * _W[7] + sc * _W[8]
    cc = sum(1 for v in (cfp, cyrp, mtp, ctap, tl, pl, rl, sc) if v >= 4)
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
        # Item 7: flexibility credit — fewer feasible sections = less flexible = higher priority
        min_sections = 99
        for cid in sreq.get(pid, []):
            n_secs = len(sec_by_code.get(cid, []))
            if n_secs < min_sections:
                min_sections = n_secs
        flex_penalty = min_sections if min_sections < 99 else 0
        scores.append((pid, max_cc, total_ws, flex_penalty))
    # Sort: most critical count first, then highest weighted sum, then least flexible
    scores.sort(key=lambda x: (-x[1], -x[2], x[3]))
    for rank, (pid, mc, tw, _fp) in enumerate(scores, 1):
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

# Populate course→department map for graduation-requirement priority
for _cid, _ci in course_info.items():
    _course_dept_map[_cid] = _ci.get('dept', '')

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
        for r in range(2, t8ws.max_row + 1):
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

# ── Template 7: Course Profiles (prerequisites + grade eligibility) ──
course_prereqs = {}
course_grade_levels = {}
t7_path = os.path.join(TEMPLATES, 'Template_7_Course_Profiles.xlsx')
try:
    t7wb = openpyxl.load_workbook(t7_path, data_only=True)
    t7ws = t7wb.active
    for r in range(3, t7ws.max_row + 1):
        ccode = t7ws.cell(r, 1).value
        prereqs = t7ws.cell(r, 20).value
        coreqs = t7ws.cell(r, 21).value
        grade_levels_raw = t7ws.cell(r, 7).value
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
            if grade_levels_raw and str(grade_levels_raw).strip() not in ('N/A', ''):
                gl_set = set()
                for g in str(grade_levels_raw).split(','):
                    g = g.strip()
                    if g.isdigit():
                        gl_set.add(int(g))
                if gl_set:
                    course_grade_levels[cid] = gl_set
    t7wb.close()
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

# Pre-compute scarcity scores (Item 5) and conflict risk (Item 5)
_compute_scarcity()

# Item 5: Compute conflict risk per student-course pair
# ConflictRisk = for each of the student's OTHER course requests, if ALL sections of that
# course overlap in period with ALL sections of this course, that's a guaranteed conflict.
# Score 0-5 based on count of such unavoidable overlaps.
def _compute_conflict_risk():
    _conflict_risk_scores.clear()
    for pid in students:
        reqs = sreq[pid]
        if len(reqs) <= 1:
            continue
        for cid in reqs:
            sids_c = sec_by_code.get(cid, [])
            if not sids_c:
                continue
            c_periods = set()
            for sid in sids_c:
                s = sections[sid]
                if s['period']:
                    c_periods.add(s['period'])
            risk = 0
            for other_cid in reqs:
                if other_cid == cid:
                    continue
                o_sids = sec_by_code.get(other_cid, [])
                if not o_sids:
                    continue
                o_periods = set()
                for osid in o_sids:
                    os = sections[osid]
                    if os['period']:
                        o_periods.add(os['period'])
                if o_periods and c_periods and o_periods == c_periods and len(o_periods) == 1:
                    risk += 1
            _conflict_risk_scores[(str(pid), str(cid))] = min(risk, 5)

_compute_conflict_risk()

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

# Pre-compute student rank scores
_compute_student_ranks()
_ranked_count = len(_student_rank_cache)
_top5 = sorted(_student_rank_cache.items(), key=lambda x: x[1][0])[:5]
print(f"  Student ranks computed: {_ranked_count}")
for _pid, (_rk, _mc, _tw) in _top5:
    print(f"    Rank {_rk}: {_pid} (maxCC={_mc}, totalWS={_tw:.1f})")


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
    # Item 6: sort by composite score, then by demand (more students affected = assign first)
    unassigned.sort(key=lambda s: (course_composite(s['code']), -_course_demand.get(s['code'], 0), len(sec_by_code[s['code']]), s['code'], s['section']))

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

# Item 8: Seat by priority tier with scarcity recalculation between tiers
# Group requests by course priority tier and seat highest tiers first
_tier_groups = defaultdict(list)
for pid in sorted_students:
    for cid in sreq[pid]:
        _tier_groups[prio(cid)].append((pid, cid))
_tiers_desc = sorted(_tier_groups.keys(), reverse=True)

for _tier in _tiers_desc:
    for pid, cid in _tier_groups[_tier]:
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
    # Recalculate scarcity after each tier — sections filling up may create new bottlenecks
    _placement_cache.clear()
    _course_composite_cache.clear()
    _remaining_cap = {}
    for cid_r, sids_r in sec_by_code.items():
        rem = sum(max(0, sections[sid_r]['cap'] - secfill[sid_r]) for sid_r in sids_r)
        demand = _course_demand.get(cid_r, 0)
        placed_count = sum(1 for pid_r in students if cid_r in assign.get(pid_r, {}))
        unplaced = demand - placed_count
        if unplaced > 0 and rem > 0:
            ratio = unplaced / rem
            if ratio >= 2.0:
                _scarcity_scores[cid_r] = 5
            elif ratio >= 1.5:
                _scarcity_scores[cid_r] = max(_scarcity_scores.get(cid_r, 1), 4)
            elif ratio >= 1.0:
                _scarcity_scores[cid_r] = max(_scarcity_scores.get(cid_r, 1), 3)

conf_count = 0
for pid in students:
    for cid, sid in assign[pid].items():
        for x in occ_cells(sid):
            if cell_usage.get((pid, x), 0) > 1:
                conf_count += 1
                break
print(f"  Initial: {sum(len(v) for v in assign.values())} placements, {conf_count} students with conflicts")

# Two-band priority: Band 1 (100+) = graduation required, Band 2 (0-5) = electives.
# Any course in Band 1 is pinned (never bumped in favor of an elective).
PROT_THRESHOLD = GRAD_REQ_BAND  # 100 — all graduation-required courses are protected
# Legacy static sets kept for reference but NOT used in bump decisions
PROT = {str(c) for c, p in COURSE_PRIORITY.items() if p == 5}
PROT_P4 = {str(c) for c, p in COURSE_PRIORITY.items() if p == 4}

def resolve_student(pid):
    pins = {}
    for pc in assign[pid]:
        if student_prio(pid, pc) >= PROT_THRESHOLD:
            pins[pc] = assign[pid][pc]
    others = [c for c in sreq[pid] if c not in pins and c in assign[pid]]
    used = set()
    for c, sid in pins.items():
        for x in occ_cells(sid):
            used.add(x)
    # Sort by student-specific priority: graduation requirements placed before electives
    others.sort(key=lambda c: (-student_prio(pid, c), -int(is_singleton(c)), placement_sort_key(pid, c), len(sec_by_code.get(c, []))))
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

# Item 1: Root cause analysis for each clash
# Item 3: Placement log — record sections considered and why rejected
placement_log = []

def _analyze_root_cause(pid, bumped_cid, keeping_cid, bumped_period):
    """Determine why this course was bumped and what blocked it."""
    causes = []
    blocking = []
    sections_tried = []

    # What course is blocking this period?
    if keeping_cid:
        keep_prio = student_prio(pid, keeping_cid)
        bump_prio = student_prio(pid, bumped_cid)
        blocking.append({
            'code': keeping_cid,
            'title': course_info.get(keeping_cid, {}).get('title', keeping_cid),
            'effective_priority': keep_prio,
            'priority_band': 'graduation_required' if keep_prio >= GRAD_REQ_BAND else 'elective',
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
            _score_fn = lambda c: (-student_prio(pid, c), -int(is_singleton(c)), -placement_score(pid, c)[1], -placement_score(pid, c)[0])
            keep = min(cs, key=_score_fn)
            for c in cs:
                if c != keep and student_prio(pid, c) < PROT_THRESHOLD:
                    bump.add(c)
                    bump_reason[c] = keep
    for c in bump:
        s = sections[assign[pid][c]]
        _ws, _cc = placement_score(pid, c)
        _eff_prio = student_prio(pid, c)
        _rca = _analyze_root_cause(pid, c, bump_reason.get(c), s['period'])
        clash.append({
            'student': pid, 'name': students[pid], 'grade': grade[pid],
            'code': c, 'course': course_info.get(c, {}).get('title', c),
            'priority': prio(c),
            'effective_priority': _eff_prio,
            'priority_band': 'graduation_required' if _eff_prio >= GRAD_REQ_BAND else 'elective',
            'is_grad_req': _eff_prio >= GRAD_REQ_BAND,
            'composite_ws': round(_ws, 1),
            'composite_cc': _cc,
            'lost_period': s['period'],
            'lost_sem': 'Full-Year' if len(s['halves']) == 2 else ('Fall' if s['halves'][0] == 'S1' else 'Spring'),
            'root_cause_codes': _rca['root_cause_codes'],
            'blocking_courses': _rca['blocking_courses'],
            'sections_tried': _rca['sections_tried'],
        })
        # Item 3: log the placement decision
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
        bmp_reason = {}
        for x, cs in cm.items():
            cs = [c for c in cs if c not in bmp]
            if len(cs) > 1:
                _sf = lambda c: (-student_prio(pid, c), -int(is_singleton(c)), -placement_score(pid, c)[1], -placement_score(pid, c)[0])
                kp = min(cs, key=_sf)
                for c in cs:
                    if c != kp and student_prio(pid, c) < PROT_THRESHOLD:
                        bmp.add(c)
                        bmp_reason[c] = kp
        for c in bmp:
            bs = sections[assign[pid][c]]
            _ws_b, _cc_b = placement_score(pid, c)
            _eff_prio = student_prio(pid, c)
            _rca = _analyze_root_cause(pid, c, bmp_reason.get(c), bs['period'])
            nc.append({
                'student': pid, 'name': students[pid], 'grade': grade[pid],
                'code': c, 'course': course_info.get(c, {}).get('title', c),
                'priority': prio(c),
                'effective_priority': _eff_prio,
                'priority_band': 'graduation_required' if _eff_prio >= GRAD_REQ_BAND else 'elective',
                'is_grad_req': _eff_prio >= GRAD_REQ_BAND,
                'composite_ws': round(_ws_b, 1),
                'composite_cc': _cc_b,
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
        if student_prio(pid, cid) >= PROT_THRESHOLD or cid in assign.get(pid, {}):
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

# Item 4: Disaggregated fulfillment preview
_preview_grad_req = sum(1 for p in students for c in sreq[p] if _is_grad_req_dept(c, grade.get(str(p), 0)))
_preview_grad_placed = sum(1 for p in students for c in sreq[p] if _is_grad_req_dept(c, grade.get(str(p), 0)) and c in assign.get(p, {}))
_preview_ap = sum(1 for p in students for c in sreq[p] if prio(c) >= 4)
_preview_ap_placed = sum(1 for p in students for c in sreq[p] if prio(c) >= 4 and c in assign.get(p, {}))
print(f"  Graduation requirement fulfillment: {_preview_grad_placed}/{_preview_grad_req} ({100*_preview_grad_placed/_preview_grad_req:.1f}%)" if _preview_grad_req else "  Graduation requirement fulfillment: N/A")
print(f"  AP/Honors fulfillment: {_preview_ap_placed}/{_preview_ap} ({100*_preview_ap_placed/_preview_ap:.1f}%)" if _preview_ap else "  AP/Honors fulfillment: N/A")

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
        if _g and _is_grad_req_dept(_cid, _g):
            _grad_req_requested += 1
            if _cid in assign.get(_pid, {}):
                _grad_req_placed += 1
        _cp = prio(_cid)
        if _cp >= 4:
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
        'p4_clashes': len(p4_clashes),
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
                             'credits': c['credits'], 'priority': prio(c['code'])}
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
                'priority': prio(_ccode),
                'avg_composite_ws': round(-course_composite(_ccode)[1], 1),
                'max_composite_cc': -course_composite(_ccode)[0],
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

        def _alt_rank(alt_sec, bumped_dept, bumped_code, bumped_prio, pid_rank):
            """Rank alternatives: same-subject > same-requirement > same-rigor > other.
            Lower rank number = better match."""
            alt_dept = alt_sec['dept']
            alt_prio = prio(alt_sec['code'])
            alt_g = grade.get(str(pid_rank), 0)
            is_grad_req = _is_grad_req_dept(alt_sec['code'], alt_g) if alt_g else False
            bumped_is_grad = _is_grad_req_dept(bumped_code, alt_g) if alt_g else False

            if alt_dept == bumped_dept and alt_prio == bumped_prio:
                return 0  # Same subject, same rigor
            if alt_dept == bumped_dept:
                return 1  # Same subject, different rigor
            if is_grad_req and bumped_is_grad:
                return 2  # Both fulfill graduation requirements
            if abs(alt_prio - bumped_prio) <= 1:
                return 3  # Similar rigor level
            return 4  # Other eligible course

        _srr_data = []
        for _c in clash:
            _pid = _c['student']
            _bumped_code = _c['code']
            _bumped_period = _c['lost_period']
            _bumped_dept = course_info.get(_bumped_code, {}).get('dept', '')
            _bumped_prio = prio(_bumped_code)
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
<div class="stat"><div class="val">{len(p4_clashes)}</div><div class="lbl">P4 Clashes</div></div>
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
