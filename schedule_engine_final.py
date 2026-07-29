"""Don Bosco Prep 2026-27 Scheduling Engine — FINAL BUILD
v1 core algorithm (286-clash baseline) with:
  - Both authoritative sources consumed (Prescribed + Sectioning Template)
  - Prior-year schedule loaded for validation/reporting (not for period assignment)
  - Teacher load violations flagged per Jamie's rules
  - Prior-year alignment stats in output
"""

import openpyxl, json, math, random, collections, statistics, os, re
from collections import defaultdict, Counter

UPLOAD = "/root/.claude/uploads/a04b5f0d-60df-588f-8acb-79549aab48c5"
SCRATCHPAD = "/tmp/claude-0/-home-user-sat-course/a04b5f0d-60df-588f-8acb-79549aab48c5/scratchpad"
PERIODS = list('ABCDEFG')

print("=" * 60)
print("SCHEDULING ENGINE — FINAL BUILD")
print("=" * 60)

# ============================================================
# 0. LOAD ALL DATA
# ============================================================
print("\n[0] LOADING DATA...")

swb = openpyxl.load_workbook(f"{UPLOAD}/1602bb5f-Course_Sectioning_Template_202627_JULY16_V17__FIRST_BUILD__1.xlsx", data_only=True)
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

rwb = openpyxl.load_workbook(f"{UPLOAD}/24aede92-Student_Course_Requests_7336_records_20260728.xlsx", data_only=True)
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

lwb = openpyxl.load_workbook(f"{UPLOAD}/94920245-2627_LEO_II_COHORTS_A__B.xlsx", data_only=True)
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

iwb = openpyxl.load_workbook(f"{UPLOAD}/e669b4e0-Verify_Tenant_Intake_DonBoscoPrep_20260727_2.xlsx", data_only=True)
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

# --- PRIOR-YEAR SCHEDULE (for validation/reporting only) ---
print("\n  Loading 2025-26 master schedule for validation...")
pwb = openpyxl.load_workbook(f"{UPLOAD}/a9be4174-202526_Master_Schedule_for_202627_Reference.xlsx", data_only=True)
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

# Infer S1 periods from S2 counterparts
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
print(f"  Courses with period data: {len(prior_course_periods)}")

# Teacher load rules
APPROVED_6 = {'Dennehy, Sheri', 'Zawiski, Brian', 'Muscat, Nicole',
              'Calidas, Riddhi', 'Janeczko, Douglas', 'Tranate, John', 'McConnell, George'}

def get_max_load(teacher):
    if 'konopelski' in teacher.lower():
        return (3, 3)
    if teacher in APPROVED_6:
        return (6, 6)
    return (5, 5)

# Course-teacher lock constraints: only the specified teacher may teach these courses
COURSE_TEACHER_LOCKS = {
    '620': 'Daniels, Torrence',    # Driver's Ed/PE — only Daniels
    '631': 'Chiaravalloti, Michael' # CPR-AED Training/PE — only Chiaravalloti
}

# ============================================================
# 1. ASSIGN PERIODS (v1 algorithm — exact reproduction)
# ============================================================
print("\n" + "=" * 60)
print("[1] PHASE A: ASSIGN PERIODS")
print("=" * 60)

PINNED = {
    '745': [('C', ('S1',)), ('E', ('S1',))],
    '734': [('C', ('S2',)), ('D', ('S2',))],
    '766': [('G', ('S1',))],
    '765': [('G', ('S2',))],
}

for cid, pins in PINNED.items():
    sids = sec_by_code.get(cid, [])
    for i, sid in enumerate(sids):
        if i < len(pins):
            sections[sid]['period'] = pins[i][0]
            sections[sid]['halves'] = pins[i][1]

# Build co-schedule group membership: code -> group index
code_to_cogroup = {}
for gi, cg in enumerate(cogroups):
    for code in cg['codes']:
        if code in sec_by_code:
            code_to_cogroup[code] = gi

# Apply co-schedule groups WITH a fixed period
for cg in cogroups:
    if cg['period']:
        p = str(cg['period']).strip().upper()
        if p in PERIODS:
            for code in cg['codes']:
                for sid in sec_by_code.get(code, []):
                    if sections[sid]['period'] is None:
                        sections[sid]['period'] = p

# Co-schedule groups WITHOUT a fixed period: mark for unified greedy assignment later
# (all sections in the group will be assigned the same period together)
cogroup_sids = defaultdict(list)  # group_index -> [sids]
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

for cid, sids in sec_by_code.items():
    ci = course_info.get(cid, {})
    if ci.get('is_fy', True):
        continue
    unpinned = [sid for sid in sids if sections[sid]['period'] is None]
    for i, sid in enumerate(unpinned):
        if i % 2 == 0:
            sections[sid]['halves'] = ('S1',)
        else:
            sections[sid]['halves'] = ('S2',)

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
    """Check if assigning this period would give teacher >6 distinct periods in any semester."""
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

# --- STEP 1: Assign co-schedule groups (no fixed period) as unified blocks ---
assigned_cogroups = set()
for gi, sids_in_group in cogroup_sids.items():
    if not sids_in_group:
        continue
    # All sections in group get the same period — pick the best one
    # Collect all teachers in this group to check conflicts
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
        if blocked:
            continue
        score = 0
        period_load = sum(1 for sec in sections if sec['period'] == p)
        score += period_load * 0.1
        if score < best_score:
            best_score = score
            best_period = p

    if best_period is None:
        # Fallback: least loaded
        loads = Counter(sec['period'] for sec in sections if sec['period'])
        best_period = min(PERIODS, key=lambda p: loads.get(p, 0))

    for sid in sids_in_group:
        sections[sid]['period'] = best_period
    assigned_cogroups.update(sids_in_group)
    print(f"  Co-schedule group '{cogroups[gi]['name']}' -> Period {best_period} ({len(sids_in_group)} sections)")

# --- STEP 2: Greedy assignment for remaining sections ---
unassigned = [s for s in sections if s['period'] is None]
unassigned.sort(key=lambda s: (len(sec_by_code[s['code']]), s['code'], s['section']))

rng = random.Random(42)

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
        # HARD CONSTRAINT: no teacher gets more than 6 distinct periods
        if teacher_would_exceed_cap(teacher, p, halves):
            continue
        score = 0
        if p in used_periods:
            score += 10
        period_load = sum(1 for sec in sections if sec['period'] == p)
        score += period_load * 0.1
        if room and room != 'TBD' and room_busy(room, p, halves, s['sid']):
            score += 5

        if score < best_score:
            best_score = score
            best_period = p

    if best_period:
        s['period'] = best_period
    else:
        # Fallback: prefer a period the teacher already uses (merge) over a new one
        if teacher and teacher != 'TBD':
            teacher_periods = set()
            for sid in teacher_sections.get(teacher, []):
                if sections[sid]['period']:
                    teacher_periods.add(sections[sid]['period'])
            if teacher_periods:
                loads = Counter(sec['period'] for sec in sections if sec['period'])
                s['period'] = min(teacher_periods, key=lambda p: loads.get(p, 0))
            else:
                loads = Counter(sec['period'] for sec in sections if sec['period'])
                s['period'] = min(PERIODS, key=lambda p: loads.get(p, 0))
        else:
            loads = Counter(sec['period'] for sec in sections if sec['period'])
            s['period'] = min(PERIODS, key=lambda p: loads.get(p, 0))

assigned_count = sum(1 for s in sections if s['period'])
print(f"  Sections assigned: {assigned_count}/{len(sections)}")
period_dist = Counter(s['period'] for s in sections)
for p in PERIODS:
    print(f"    Period {p}: {period_dist.get(p, 0)} sections")

# Teacher conflict check (exclude co-scheduled sections — they share a period by design)
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

# Prior-year alignment check (validation only)
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
print(f"  Prior-year alignment: {prior_match}/{prior_total} sections match 2025-26 period")

# Teacher load check — count distinct periods per semester (merged sections = 1 period)
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
# 2. SEAT STUDENTS (v1 algorithm — exact reproduction)
# ============================================================
print("\n" + "=" * 60)
print("[2] PHASE B: SEAT STUDENTS")
print("=" * 60)

assign = {pid: {} for pid in students}
secfill = Counter()

def occ_cells(sid):
    s = sections[sid]
    return [(s['period'], h) for h in s['halves']]

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

sorted_students = sorted(students.keys(), key=lambda pid: -len(sreq[pid]))
print("  Greedy warm-start...")
for pid in sorted_students:
    reqs = sorted(sreq[pid], key=lambda c: len(sec_by_code.get(c, [])))
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

PROT = {'745', '734', '766', '765'}

def resolve_student(pid):
    pins = {}
    for pc in ['745', '766', '765']:
        if pc in assign[pid]:
            pins[pc] = assign[pid][pc]
    others = [c for c in sreq[pid] if c not in pins and c in assign[pid]]
    used = set()
    for c, sid in pins.items():
        for x in occ_cells(sid):
            used.add(x)
    others.sort(key=lambda c: len(sec_by_code.get(c, [])))
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

def prio(c):
    ci = course_info.get(c, {})
    dept = ci.get('dept', '')
    if c in PROT:
        return 5
    if dept == 'English':
        return 5
    if dept in ('Mathematics', 'Science', 'Theology'):
        return 4
    if dept in ('Social Studies', 'Language'):
        return 3
    return 1

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
            keep = max(prot_cs, key=lambda c: prio(c)) if prot_cs else max(cs, key=lambda c: prio(c))
            for c in cs:
                if c != keep and c not in PROT:
                    bump.add(c)
    for c in bump:
        s = sections[assign[pid][c]]
        clash.append({
            'student': pid, 'name': students[pid], 'grade': grade[pid],
            'code': c, 'course': course_info.get(c, {}).get('title', c),
            'lost_period': s['period'],
            'lost_sem': 'Full-Year' if len(s['halves']) == 2 else ('Fall' if s['halves'][0] == 'S1' else 'Spring')
        })
        rm_place(pid, c)


# ============================================================
# PHASE D0: FORCED SECTION PERIOD MOVES (decongest Period G)
# ============================================================
print("\n" + "=" * 60)
print("[D0] FORCED SECTION PERIOD MOVES")
print("=" * 60)

FORCED_MOVES = [
    # (code, section#, new_period, reason)
    ('149', 1, 'F', 'AP Eng Lit sec#1 G→F: resolve 9 AP Macro/Micro clashes'),
    ('761', 1, 'A', 'AP Psychology G→A: decongest G, Harris free in A'),
    ('585', 1, 'E', 'Robotics Design G→E: decongest G, McConnell free in E'),
    ('743', 1, 'B', 'AP Euro History D→B: resolve 5 AP Latin clashes, Quast free in B'),
]

for fcode, fsec, fnew_per, freason in FORCED_MOVES:
    moved = False
    for sid in sec_by_code.get(fcode, []):
        s = sections[sid]
        if s['section'] == fsec:
            old_per = s['period']
            s['period'] = fnew_per
            print(f"  FORCED: {fcode} {s['title']} sec#{fsec}: {old_per} → {fnew_per} ({freason})")
            moved = True
            break
    if not moved:
        print(f"  WARNING: Could not find {fcode} sec#{fsec}")

# ============================================================
# PHASE D: ITERATIVE CLASH RESOLUTION
# ============================================================
print("\n" + "=" * 60)
print("[D] PHASE D: CLASH RESOLUTION")
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

code_requesters = defaultdict(set)
for _pid in students:
    for _cid in sreq[_pid]:
        code_requesters[_cid].add(_pid)


def full_reseat():
    """Re-run complete student seating from scratch. Returns new clash list."""
    for pid in students:
        assign[pid] = {}
    secfill.clear()
    cell_usage.clear()
    # Greedy warm-start
    for pid in sorted(students.keys(), key=lambda p: -len(sreq[p])):
        for cid in sorted(sreq[pid], key=lambda c: len(sec_by_code.get(c, []))):
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
    # Enhanced CSP (8 rounds, severity-priority)
    for rnd in range(8):
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
    # Bumping
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
                kp = max(pr, key=prio) if pr else max(cs, key=prio)
                for c in cs:
                    if c != kp and c not in PROT:
                        bmp.add(c)
        for c in bmp:
            bs = sections[assign[pid][c]]
            nc.append({
                'student': pid, 'name': students[pid], 'grade': grade[pid],
                'code': c, 'course': course_info.get(c, {}).get('title', c),
                'lost_period': bs['period'],
                'lost_sem': 'Full-Year' if len(bs['halves']) == 2 else (
                    'Fall' if bs['halves'][0] == 'S1' else 'Spring')
            })
            rm_place(pid, c)
    # Post-bump redistribution: place bumped students in free periods
    for cl in list(nc):
        pid, cid = cl['student'], cl['code']
        if cid in PROT or cid == '745' or cid in assign.get(pid, {}):
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
            nc.remove(cl)
    return nc


# Establish enhanced baseline
print("  Re-seating with enhanced solver (8-round CSP + redistribution)...")
clash = full_reseat()
print(f"  Enhanced baseline: {len(clash)} clashes")

# Iterative section period moves
stalled = 0
for d_iter in range(25):
    if stalled >= 3:
        break
    # Score sections by clash involvement (both bumped and kept sides)
    sec_sc = Counter()
    for cl in clash:
        for sid in sec_by_code.get(cl['code'], []):
            if sections[sid]['period'] == cl['lost_period']:
                sec_sc[sid] += 1
        pid_cl = cl['student']
        for cid_cl, sid_cl in assign.get(pid_cl, {}).items():
            if sections[sid_cl]['period'] == cl['lost_period']:
                sec_sc[sid_cl] += 1
    # Evaluate valid moves with estimated improvement
    cands = []
    for sid, score in sec_sc.most_common(40):
        if sid in PINNED_SIDS or sid in COGROUP_SIDS or score < 2:
            continue
        s = sections[sid]
        for p in PERIODS:
            if p == s['period']:
                continue
            # Teacher availability check
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
            # Estimate new conflicts in target period
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
    # Test top candidates with full re-seat
    improved = False
    for est, sid, np in cands[:5]:
        s = sections[sid]
        op = s['period']
        s['period'] = np
        tc = full_reseat()
        if len(tc) < len(clash):
            clash = tc
            print(f"    Iter {d_iter+1}: {s['code']} {s['title']} sec#{s['section']} "
                  f"({s['teacher']}): {op}->{np}  clashes={len(clash)}")
            improved = True
            stalled = 0
            break
        s['period'] = op
        clash = full_reseat()
    if not improved:
        stalled += 1

# Recompute stats after section moves
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

print(f"\n  PHASE D COMPLETE: {len(clash)} clashes (started at 266)")


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

sec_sizes = [secfill[sid] for sid in range(len(sections)) if secfill[sid] > 0]
if sec_sizes:
    print(f"  Section sizes: min={min(sec_sizes)}, max={max(sec_sizes)}, avg={statistics.mean(sec_sizes):.1f}")

dept_clashes = Counter()
for c in clash:
    ci = course_info.get(c['code'], {})
    dept_clashes[ci.get('dept', 'Unknown')] += 1
print(f"\n  Clashes by department:")
for dept, cnt in dept_clashes.most_common():
    print(f"    {dept}: {cnt}")

print(f"\n  Prior-year alignment: {prior_match}/{prior_total} sections match 2025-26")
print(f"  Teacher load violations: {len(load_violations)}")
for lv in load_violations:
    print(f"    {lv['teacher']}: S1={lv['s1']}/{lv['max_s1']} S2={lv['s2']}/{lv['max_s2']}")


# ============================================================
# 3b. RESOLVE ROOM CONFLICTS (post-scheduling)
# Priority: teacher who held the room in 2025-26 keeps it.
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
        # Score each section: prior-year count in this room (descending)
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
            # Find best available room for displaced teacher
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
for m in room_moves:
    print(f"    {m}")

# ============================================================
# 4. SAVE RESULTS
# ============================================================
output = {
    'sections': [],
    'assignments': {},
    'clashes': clash,
    'stats': {
        'students': len(students),
        'requests': total_requested,
        'placed': total_placed,
        'clashes': len(clash),
        'sections_used': len([s for s in range(len(sections)) if secfill[s] > 0]),
        'placement_rate': round(placement_rate, 1),
        'prior_year_alignment': f"{prior_match}/{prior_total}"
    },
    'diagnostics': {
        'teacher_conflicts': t_conflicts,
        'load_violations': load_violations,
    }
}

for s in sections:
    # Check prior-year match for this section
    prior_prefs = prior_teacher_periods.get((s['code'], s['teacher']), set())
    if not prior_prefs:
        prior_prefs = prior_course_periods.get(s['code'], set())
    prior_match_flag = s['period'] in prior_prefs if prior_prefs else None

    output['sections'].append({
        'sid': s['sid'], 'code': s['code'], 'title': s['title'],
        'dept': s['dept'], 'period': s['period'], 'halves': list(s['halves']),
        'teacher': s['teacher'], 'room': s['room'], 'cap': s['cap'],
        'enrolled': secfill[s['sid']], 'section': s['section'],
        'prior_year_match': prior_match_flag
    })

for pid in students:
    output['assignments'][pid] = {
        'name': students[pid],
        'grade': grade[pid],
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
            'section': s['section']
        }

SOLUTION_FILE = os.path.join(SCRATCHPAD, "schedule_solution.json")
with open(SOLUTION_FILE, 'w') as f:
    json.dump(output, f)
print(f"\n  Solution saved to {SOLUTION_FILE}")
print("=" * 60)
print("DONE")
print("=" * 60)
