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
ENGINE_WB_PATH = os.path.join(BASE, 'Engine_Templates_With_Data.xlsx')

with open(os.path.join(BASE, 'course_priorities.json')) as f:
    config = json.load(f)

PATHWAY_COURSES = config['pathway_courses']
PATHWAY_COURSES.pop('_notes', None)

# Build reverse map: course_code → list of pathway names
code_to_pathways = defaultdict(list)
for pathway_name, codes in PATHWAY_COURSES.items():
    for code in codes:
        code_to_pathways[str(code)].append(pathway_name)

# ── Load Transcript History from Engine_Templates_With_Data.xlsx → T6_Student Prerequisites ──
wb_engine = openpyxl.load_workbook(ENGINE_WB_PATH, data_only=True)
ws_hist = wb_engine['T6_Student Prerequisites']

student_history = defaultdict(set)  # sid → set of completed pathway course codes
# T6 Cols: A=Grad Year, B=Student ID, C=Course Code, D=Final Grade, E=Passed (Y/N), F=Final Exam Grade
for r in range(2, ws_hist.max_row + 1):
    sid = ws_hist.cell(r, 2).value
    ccode = ws_hist.cell(r, 3).value
    passed = ws_hist.cell(r, 5).value
    if sid and ccode:
        sid_str = str(sid).strip()
        ccode_str = str(ccode).strip()
        if ccode_str in code_to_pathways:
            if str(passed or '').upper() == 'Y':
                student_history[sid_str].add(ccode_str)
print(f"Transcript history: {len(student_history)} students with pathway course completions")

# ── Load Course Requests from Engine_Templates_With_Data.xlsx → T5_Student Course Requests ──
ws_t5 = wb_engine['T5_Student Course Requests']

student_requests = defaultdict(set)  # sid → set of requested pathway course codes
_t5_rows = 0
for r in range(2, (ws_t5.max_row or 1) + 1):
    sid = ws_t5.cell(r, 1).value
    ccode = ws_t5.cell(r, 2).value
    if sid and ccode:
        sid_str = str(sid).strip()
        ccode_str = str(ccode).strip()
        if ccode_str in code_to_pathways:
            student_requests[sid_str].add(ccode_str)
        _t5_rows += 1
if _t5_rows == 0:
    print("WARNING: T5_Student Course Requests is EMPTY — pathway detection from requests will be incomplete")
else:
    print(f"Course requests: {len(student_requests)} students with pathway course requests")

# ── Load Student Profiles from Engine_Templates_With_Data.xlsx → T3_Student Profiles ──
ws_t3 = wb_engine['T3_Student Profiles']
wb_engine.close()

# T3 columns: 1=Grad Year, 2=Student ID, 3=Last Name, 4=First Name, 5=Grade Level,
#   6=NCAA Athlete(Y/N), 7=LEO II(Y/N), ...
# Note: T3 does not have a Pathway column — pathway results are printed to console only

student_grades = {}  # sid → grade (int)
leo_students = set()

for r in range(2, ws_t3.max_row + 1):
    sid = ws_t3.cell(r, 2).value
    if not sid:
        continue
    sid_str = str(sid).strip()
    g = ws_t3.cell(r, 5).value  # Grade Level (col 5)
    student_grades[sid_str] = int(g) if g and str(g).strip().isdigit() else 0
    leo_val = str(ws_t3.cell(r, 7).value or 'N').upper()  # LEO II (col 7)
    if leo_val == 'Y':
        leo_students.add(sid_str)

print(f"T3 Student Profiles: {len(student_grades)} students, {len(leo_students)} LEO II")


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

# ── Output results (T3 does not have a Pathway column — results printed only) ──
print(f"\nPathway detection complete. Results available in 'results' dict ({len(results)} students).")
print("Note: T3_Student Profiles does not have a Pathway column. SSP column (col 10) holds pathway data.")
print("To update SSP pathways in the workbook, add pathway assignments to T3 column 10.")
