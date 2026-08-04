import json
from collections import Counter, defaultdict
import math

with open('/tmp/claude-0/-home-user-sat-course/a04b5f0d-60df-588f-8acb-79549aab48c5/scratchpad/schedule_solution.json') as f:
    data = json.load(f)

sections = data['sections']
assignments = data['assignments']
conflicts = data['conflicts']

# Build course info: for each course code, what halves patterns exist across sections?
course_sections = defaultdict(list)
for s in sections:
    course_sections[s['code']].append({
        'sid': s['sid'],
        'period': s['period'],
        'halves': tuple(s['halves']),
        'teacher': s['teacher'],
        'section': s['section'],
        'title': s['title'],
    })

def get_course_type(code):
    secs = course_sections.get(code, [])
    if not secs:
        return 'UNKNOWN'
    halves_set = set(s['halves'] for s in secs)
    if halves_set == {('S1', 'S2')}:
        return 'FY'
    elif halves_set == {('S1',)}:
        return 'S1'
    elif halves_set == {('S2',)}:
        return 'S2'
    elif halves_set == {('S1',), ('S2',)}:
        return 'HALF'
    else:
        return 'MIXED'

def lost_sem_to_halves(lost_sem):
    if lost_sem == 'Full-Year':
        return ('S1', 'S2')
    elif lost_sem == 'Fall':
        return ('S1',)
    elif lost_sem == 'Spring':
        return ('S2',)
    return None

conflict_students = set(c['student'] for c in conflicts)

student_data = []

for student_id in sorted(conflict_students):
    assigned_courses = {}
    if student_id in assignments:
        a = assignments[student_id]
        name = a['name']
        grade = a['grade']
        for code, info in a['courses'].items():
            assigned_courses[code] = {
                'title': info['title'],
                'halves': tuple(info['halves']),
                'period': info['period'],
                'teacher': info['teacher'],
                'section': info['section'],
                'source': 'assigned',
            }
    else:
        conflict_entry = [c for c in conflicts if c['student'] == student_id][0]
        name = conflict_entry['name']
        grade = conflict_entry['grade']

    conflicted_courses = {}
    for c in conflicts:
        if c['student'] == student_id:
            code = c['code']
            halves = lost_sem_to_halves(c['lost_sem'])
            conflicted_courses[code] = {
                'title': c['course'],
                'halves': halves,
                'lost_period': c['lost_period'],
                'lost_sem': c['lost_sem'],
                'source': 'conflicted',
            }

    all_courses = {}
    for code, info in assigned_courses.items():
        all_courses[code] = info
    for code, info in conflicted_courses.items():
        if code not in all_courses:
            all_courses[code] = info

    fy_courses = []
    s1_courses = []
    s2_courses = []
    half_courses = []

    for code, info in all_courses.items():
        halves = info['halves']
        course_type = get_course_type(code)

        if halves == ('S1', 'S2'):
            fy_courses.append((code, info))
        elif halves == ('S1',):
            if course_type == 'HALF':
                half_courses.append((code, info, 'S1'))
            else:
                s1_courses.append((code, info))
        elif halves == ('S2',):
            if course_type == 'HALF':
                half_courses.append((code, info, 'S2'))
            else:
                s2_courses.append((code, info))

    FY = len(fy_courses)
    H1_fixed = len(s1_courses)
    H2_fixed = len(s2_courses)
    H_flex = len(half_courses)

    best_x = (H2_fixed + H_flex - H1_fixed) / 2
    best_x = max(0, min(H_flex, best_x))
    best_x_floor = int(best_x)
    best_x_ceil = min(H_flex, best_x_floor + 1)

    options = []
    for x in set([best_x_floor, best_x_ceil]):
        h1_total = H1_fixed + x
        h2_total = H2_fixed + (H_flex - x)
        slots = FY + max(h1_total, h2_total)
        options.append((slots, h1_total, h2_total, x))

    best = min(options, key=lambda o: o[0])
    min_slots, best_h1, best_h2, best_flex_to_s1 = best

    student_data.append({
        'student_id': student_id,
        'name': name,
        'grade': grade,
        'total_courses': len(all_courses),
        'fy_count': FY,
        'h1_fixed': H1_fixed,
        'h2_fixed': H2_fixed,
        'h_flex': H_flex,
        'min_slots': min_slots,
        'best_h1': best_h1,
        'best_h2': best_h2,
        'fy_courses': fy_courses,
        's1_courses': s1_courses,
        's2_courses': s2_courses,
        'half_courses': half_courses,
        'all_courses': all_courses,
        'assigned_courses': assigned_courses,
        'conflicted_courses': conflicted_courses,
        'num_conflicts': len(conflicted_courses),
    })

cat_a = [s for s in student_data if s['min_slots'] > 7]
cat_b = [s for s in student_data if s['min_slots'] == 7]
cat_c = [s for s in student_data if s['min_slots'] < 7]

print("=" * 100)
print("STRUCTURAL CONFLICT ANALYSIS")
print("=" * 100)
print(f"\nTotal students with conflicts: {len(student_data)}")
print(f"Total conflicts: {len(conflicts)}")

print()
print("=" * 100)
print("CATEGORY A: STRUCTURALLY UNRESOLVABLE (need > 7 period slots)")
print("=" * 100)
if cat_a:
    for s in sorted(cat_a, key=lambda x: -x['min_slots']):
        print(f"\n  Student {s['student_id']}: {s['name']} (Grade {s['grade']})")
        print(f"    Total courses requested: {s['total_courses']}")
        print(f"    FY: {s['fy_count']}, S1-fixed: {s['h1_fixed']}, S2-fixed: {s['h2_fixed']}, Flex-half: {s['h_flex']}")
        print(f"    MINIMUM SLOTS NEEDED: {s['min_slots']} (exceeds 7 by {s['min_slots'] - 7})")
        print(f"    Must drop at least {s['min_slots'] - 7} course(s)")
        print(f"    All courses:")
        for code, info in s['fy_courses']:
            src = info['source']
            print(f"      [{src:8s}] {code} {info['title']} (Full-Year)")
        for code, info in s['s1_courses']:
            src = info['source']
            print(f"      [{src:8s}] {code} {info['title']} (S1-only, fixed)")
        for code, info in s['s2_courses']:
            src = info['source']
            print(f"      [{src:8s}] {code} {info['title']} (S2-only, fixed)")
        for code, info, sem in s['half_courses']:
            src = info['source']
            print(f"      [{src:8s}] {code} {info['title']} (Half-year, currently {sem}, flexible)")
        print(f"    Conflicted courses (candidates for dropping):")
        for code, info in s['conflicted_courses'].items():
            print(f"      {code} {info['title']} (lost period {info['lost_period']}, {info['lost_sem']})")
else:
    print("  NONE - No students have requests exceeding 7 period slots")

print()
print("=" * 100)
print("CATEGORY B: TIGHT FIT (exactly 7 slots needed - every period must be used)")
print("=" * 100)
if cat_b:
    for s in sorted(cat_b, key=lambda x: x['name']):
        conflicted_str = "; ".join(f"{code} {info['title']} ({info['lost_sem']})"
                                for code, info in s['conflicted_courses'].items())
        print(f"\n  Student {s['student_id']}: {s['name']} (Grade {s['grade']})")
        print(f"    Total courses: {s['total_courses']}, Conflictes: {s['num_conflicts']}")
        print(f"    FY: {s['fy_count']}, S1-fixed: {s['h1_fixed']}, S2-fixed: {s['h2_fixed']}, Flex-half: {s['h_flex']}")
        print(f"    Conflicted: {conflicted_str}")
        print(f"    All courses:")
        for code, info in s['fy_courses']:
            src = info['source']
            prd = info.get('period', info.get('lost_period', '?'))
            print(f"      [{src:8s}] {code} {info['title']} (FY, period {prd})")
        for code, info in s['s1_courses']:
            src = info['source']
            prd = info.get('period', info.get('lost_period', '?'))
            print(f"      [{src:8s}] {code} {info['title']} (S1-fixed, period {prd})")
        for code, info in s['s2_courses']:
            src = info['source']
            prd = info.get('period', info.get('lost_period', '?'))
            print(f"      [{src:8s}] {code} {info['title']} (S2-fixed, period {prd})")
        for code, info, sem in s['half_courses']:
            src = info['source']
            prd = info.get('period', info.get('lost_period', '?'))
            print(f"      [{src:8s}] {code} {info['title']} (half-flex, {sem}, period {prd})")
else:
    print("  NONE")

print()
print("=" * 100)
print("CATEGORY C: RESOLVABLE (< 7 slots needed - room for rearrangement)")
print("=" * 100)
print(f"  Total students: {len(cat_c)}")

slots_dist = Counter(s['min_slots'] for s in cat_c)
for slots in sorted(slots_dist.keys()):
    students_at = [s for s in cat_c if s['min_slots'] == slots]
    print(f"\n  --- {slots} slots needed ({len(students_at)} students) ---")
    for s in sorted(students_at, key=lambda x: x['name']):
        conflicted_str = "; ".join(f"{code} {info['title']} ({info['lost_sem']})"
                                for code, info in s['conflicted_courses'].items())
        print(f"    {s['student_id']}: {s['name']} (Gr {s['grade']}) - "
              f"{s['total_courses']} courses [{s['fy_count']}FY+{s['h1_fixed']}S1+{s['h2_fixed']}S2+{s['h_flex']}flex] "
              f"Conflicted: {conflicted_str}")

print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"  Category A (UNRESOLVABLE, > 7 slots): {len(cat_a)} students, {sum(s['num_conflicts'] for s in cat_a)} conflicts")
print(f"  Category B (TIGHT, = 7 slots):        {len(cat_b)} students, {sum(s['num_conflicts'] for s in cat_b)} conflicts")
print(f"  Category C (RESOLVABLE, < 7 slots):   {len(cat_c)} students, {sum(s['num_conflicts'] for s in cat_c)} conflicts")
print(f"  Total:                                 {len(student_data)} students, {sum(s['num_conflicts'] for s in student_data)} conflicts")
