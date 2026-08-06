"""Detect student pathway membership from Historical Grades + Course Requests.

Rules (established by JC Iofalo):
- Grade 12: completed 2+ pathway courses in prior 3 years → enrolled
- Grade 11: completed 1+ pathway course in prior 3 years → enrolled
- Grade 10: completed pathway course in G9 + G10 requests match same pathway → that pathway;
             if G10 requests match different pathway → use G10 pathway
- Grade 9:  elective request matching a pathway → auto-enroll
- Tie-break: pathway with most matches wins
- LEO rule: all LEO students → Business pathway

Updates Template 8 Pathway column with pathway name (or 'N').
"""

import json
import os
import openpyxl
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(BASE, 'templates')

with open(os.path.join(BASE, 'course_priorities.json')) as f:
    config = json.load(f)

PATHWAY_COURSES = config['pathway_courses']
PATHWAY_COURSES.pop('_notes', None)

# Build reverse map: course_code → list of pathway names
code_to_pathways = defaultdict(list)
for pathway_name, codes in PATHWAY_COURSES.items():
    for code in codes:
        code_to_pathways[str(code)].append(pathway_name)

# ── Load Transcript History from Template 8 Sheet 2 ──
t8_path = os.path.join(TEMPLATES, 'Template_8_Student_Profiles.xlsx')
wb_hist = openpyxl.load_workbook(t8_path, data_only=True)
ws_hist = wb_hist['Transcript History']

student_history = defaultdict(set)  # sid → set of completed pathway course codes
# Cols: A=Student ID, B=Academic Year, C=Course Code, ..., H=Passed (Y/N)
for r in range(3, ws_hist.max_row + 1):
    sid = ws_hist.cell(r, 1).value
    ccode = ws_hist.cell(r, 3).value
    passed = ws_hist.cell(r, 8).value
    if sid and ccode:
        sid_str = str(sid).strip()
        ccode_str = str(ccode).strip()
        if ccode_str in code_to_pathways:
            if str(passed or '').upper() == 'Y':
                student_history[sid_str].add(ccode_str)
wb_hist.close()
print(f"Transcript history: {len(student_history)} students with pathway course completions")

# ── Load Course Requests (Template 2) ──
t2_path = os.path.join(TEMPLATES, 'Template_2_Student_Course_Requests.xlsx')
wb_t2 = openpyxl.load_workbook(t2_path, data_only=True)
ws_t2 = wb_t2.active

student_requests = defaultdict(set)  # sid → set of requested pathway course codes
for r in range(3, ws_t2.max_row + 1):
    sid = ws_t2.cell(r, 1).value
    ccode = ws_t2.cell(r, 2).value
    if sid and ccode:
        sid_str = str(sid).strip()
        ccode_str = str(ccode).strip()
        if ccode_str in code_to_pathways:
            student_requests[sid_str].add(ccode_str)
wb_t2.close()
print(f"Course requests: {len(student_requests)} students with pathway course requests")

# ── Load Template 8 for grades + LEO flags ──
t8_path = os.path.join(TEMPLATES, 'Template_8_Student_Profiles.xlsx')
wb_t8 = openpyxl.load_workbook(t8_path)
ws_t8 = wb_t8.active

t8_hdr = {}
for c in range(1, ws_t8.max_column + 1):
    v = ws_t8.cell(1, c).value
    if v:
        t8_hdr[str(v).strip()] = c

sid_col = t8_hdr.get('Student ID', 1)
grade_col = t8_hdr.get('Grade Level', 4)
leo2_col = t8_hdr.get('LEO II')
pathway_col = t8_hdr.get('Pathway')

if not pathway_col:
    print("ERROR: Pathway column not found in Template 8")
    exit(1)

student_grades = {}  # sid → grade (int)
leo_students = set()

for r in range(3, ws_t8.max_row + 1):
    sid = ws_t8.cell(r, sid_col).value
    if not sid:
        continue
    sid_str = str(sid).strip()
    g = ws_t8.cell(r, grade_col).value
    student_grades[sid_str] = int(g) if g and str(g).strip().isdigit() else 0
    if leo2_col:
        leo_val = str(ws_t8.cell(r, leo2_col).value or 'N').upper()
        if leo_val == 'Y':
            leo_students.add(sid_str)

print(f"Template 8: {len(student_grades)} students, {len(leo_students)} LEO II")


def count_pathway_matches(courses, pathway_name):
    """Count how many courses from a set belong to a given pathway."""
    pathway_codes = set(str(c) for c in PATHWAY_COURSES[pathway_name])
    return len(courses & pathway_codes)


def detect_pathway(sid):
    """Apply the detection rules to determine a student's pathway."""
    g = student_grades.get(sid, 0)
    history = student_history.get(sid, set())
    requests = student_requests.get(sid, set())

    # LEO rule: all LEO students are Business pathway
    if sid in leo_students:
        return 'Business'

    if g == 12:
        # Grade 12: completed 2+ courses from a pathway in prior 3 years
        best_pathway = None
        best_count = 0
        for pw_name in PATHWAY_COURSES:
            count = count_pathway_matches(history, pw_name)
            if count >= 2 and count > best_count:
                best_count = count
                best_pathway = pw_name
        return best_pathway or 'N'

    elif g == 11:
        # Grade 11: completed 1+ course from a pathway in prior 3 years
        best_pathway = None
        best_count = 0
        for pw_name in PATHWAY_COURSES:
            count = count_pathway_matches(history, pw_name)
            if count >= 1 and count > best_count:
                best_count = count
                best_pathway = pw_name
        return best_pathway or 'N'

    elif g == 10:
        # Grade 10: completed pathway course in G9 + G10 requests
        g9_pathways = defaultdict(int)
        for code in history:
            for pw in code_to_pathways.get(code, []):
                g9_pathways[pw] += 1

        g10_pathways = defaultdict(int)
        for code in requests:
            for pw in code_to_pathways.get(code, []):
                g10_pathways[pw] += 1

        if g9_pathways and g10_pathways:
            # Check if G10 requests match same pathway as G9
            best_g9 = max(g9_pathways, key=g9_pathways.get)
            if best_g9 in g10_pathways:
                return best_g9
            # If G10 requests match different pathway, use G10
            best_g10 = max(g10_pathways, key=g10_pathways.get)
            return best_g10
        elif g10_pathways:
            # No G9 history but has pathway requests
            return max(g10_pathways, key=g10_pathways.get)
        elif g9_pathways:
            return max(g9_pathways, key=g9_pathways.get)
        return 'N'

    elif g == 9:
        # Grade 9: elective request matching a pathway → auto-enroll
        req_pathways = defaultdict(int)
        for code in requests:
            for pw in code_to_pathways.get(code, []):
                req_pathways[pw] += 1
        if req_pathways:
            return max(req_pathways, key=req_pathways.get)
        return 'N'

    return 'N'


# ── Detect pathways for all students ──
results = {}
for sid in student_grades:
    pw = detect_pathway(sid)
    # LEO is a subset of Business — map any LEO detection to Business
    if pw == 'LEO':
        pw = 'Business'
    results[sid] = pw

# ── Summary ──
pathway_counts = defaultdict(int)
grade_pathway = defaultdict(lambda: defaultdict(int))
for sid, pw in results.items():
    pathway_counts[pw] += 1
    grade_pathway[student_grades[sid]][pw] += 1

print("\n=== Pathway Detection Results ===")
print(f"Total students: {len(results)}")
for pw in sorted(pathway_counts, key=lambda x: (-pathway_counts[x], x)):
    print(f"  {pw}: {pathway_counts[pw]}")

print("\nBy grade:")
for g in [9, 10, 11, 12]:
    counts = grade_pathway.get(g, {})
    enrolled = sum(v for k, v in counts.items() if k != 'N')
    total = sum(counts.values())
    print(f"  Grade {g}: {enrolled}/{total} enrolled in a pathway")
    for pw in sorted(counts, key=lambda x: (-counts[x], x)):
        if pw != 'N':
            print(f"    {pw}: {counts[pw]}")

# ── Update Template 8 ──
updated = 0
for r in range(3, ws_t8.max_row + 1):
    sid = ws_t8.cell(r, sid_col).value
    if not sid:
        continue
    sid_str = str(sid).strip()
    pw = results.get(sid_str, 'N')
    old_val = ws_t8.cell(r, pathway_col).value
    ws_t8.cell(r, pathway_col).value = pw
    if str(old_val or 'N') != pw:
        updated += 1

wb_t8.save(t8_path)
wb_t8.close()
print(f"\nTemplate 8 updated: {updated} students changed, saved to {t8_path}")
