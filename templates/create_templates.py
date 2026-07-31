"""Create 5 Excel upload templates for the Don Bosco Prep Scheduling Engine.
Each template matches the exact column positions the engine reads from."""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os

OUT = "/home/user/sat-course/templates"

# Shared styles
HEADER_FONT = Font(name='Arial', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1B4965', end_color='1B4965', fill_type='solid')
EXAMPLE_FILL = PatternFill(start_color='FFF3CD', end_color='FFF3CD', fill_type='solid')
EXAMPLE_FONT = Font(name='Arial', size=10, italic=True, color='926B18')
DATA_FONT = Font(name='Arial', size=10)
LEGEND_FONT = Font(name='Arial', size=10, color='2D6A4F')
LEGEND_FILL = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
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
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = THIN_BORDER

def style_example(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.font = EXAMPLE_FONT
        cell.fill = EXAMPLE_FILL
        cell.border = THIN_BORDER

def style_data(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.font = DATA_FONT
        cell.border = THIN_BORDER

def add_legend(ws, start_row, items):
    for i, (label, desc) in enumerate(items):
        r = start_row + i
        ws.cell(r, 1, label).font = Font(name='Arial', bold=True, size=10, color='1B4965')
        ws.cell(r, 1).fill = LEGEND_FILL
        ws.cell(r, 2, desc).font = LEGEND_FONT
        ws.cell(r, 2).fill = LEGEND_FILL
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)

def auto_width(ws, cols, min_w=12, max_w=30):
    for c in range(1, cols + 1):
        ws.column_dimensions[get_column_letter(c)].width = min(max_w, max(min_w, 15))


# ================================================================
# TEMPLATE 1: Course Sectioning Template (2 sheets)
# ================================================================
wb1 = openpyxl.Workbook()

# Sheet 1: Step 1 - Set Sections (course catalog)
ws1a = wb1.active
ws1a.title = 'Step 1 - Set Sections'

# Engine reads columns: A=Code, B=Title, C=Department, D=Credits, E=Type
headers_1a = ['Course Code', 'Course Title', 'Department', 'Credits', 'Type (Full-Year/Semester)']
for c, h in enumerate(headers_1a, 1):
    ws1a.cell(1, c, h)
style_header(ws1a, 1, len(headers_1a))

# Example rows
examples_1a = [
    [111, 'Composition & Literature H', 'English', 5.0, 'Full-Year'],
    [430, 'Algebra II/Trig', 'Mathematics', 5.0, 'Full-Year'],
    [766, 'AP Microeconomics', 'Social Studies', 2.5, 'Semester'],
    [620, "Driver's Ed/PE", 'Physical Education', 2.5, 'Semester'],
    [849, 'Catholic Social Teaching', 'Theology', 2.5, 'Full-Year'],
]
for i, row in enumerate(examples_1a):
    for c, v in enumerate(row, 1):
        ws1a.cell(2 + i, c, v)
    style_example(ws1a, 2 + i, len(headers_1a))

auto_width(ws1a, len(headers_1a))
ws1a.column_dimensions['B'].width = 35

# Legend
add_legend(ws1a, 9, [
    ('HOW TO USE:', 'Replace the yellow example rows with your actual course catalog data from the SIS.'),
    ('Course Code:', 'The numeric course code from your SIS (e.g., 111, 430, 766)'),
    ('Type:', 'Enter "Full-Year" for courses that run both semesters, or "Semester" for half-year courses'),
    ('Credits:', 'Standard credits (typically 5.0 for full-year, 2.5 for semester)'),
    ('DELETE:', 'Delete the yellow example rows before uploading — they are just format guides.'),
])

# Sheet 2: Step 2 - Assign Sections (individual sections with teachers/rooms)
ws1b = wb1.create_sheet('Step 2 - Assign Sections')

# Engine reads: A=Code, G=SectionNum, H=Semester, I=Cap, J=Teacher, K=Room
# Columns B-F are for display only (title, dept, etc.) — engine skips them
headers_1b = ['Course Code', 'Course Title', 'Department', 'Credits', 'Type',
              'Level', 'Section #', 'Semester', 'Cap', 'Teacher', 'Room']
for c, h in enumerate(headers_1b, 1):
    ws1b.cell(1, c, h)
style_header(ws1b, 1, len(headers_1b))

examples_1b = [
    [111, 'Composition & Literature H', 'English', 5.0, 'Full-Year', 'Honors', 1, 'Fall & Spring', 25, 'Smith, Jane', 'Classroom D-101'],
    [111, 'Composition & Literature H', 'English', 5.0, 'Full-Year', 'Honors', 2, 'Fall & Spring', 25, 'Smith, Jane', 'Classroom D-101'],
    [766, 'AP Microeconomics', 'Social Studies', 2.5, 'Semester', 'AP', 1, 'Fall Only', 30, 'Jones, Robert', 'Classroom S-231'],
    [766, 'AP Microeconomics', 'Social Studies', 2.5, 'Semester', 'AP', 2, 'Spring Only', 30, 'Jones, Robert', 'Classroom S-231'],
    [849, 'Catholic Social Teaching', 'Theology', 2.5, 'Full-Year', 'Regular', 1, 'Builder Choice', 32, 'TBD', 'TBD'],
]
for i, row in enumerate(examples_1b):
    for c, v in enumerate(row, 1):
        ws1b.cell(2 + i, c, v)
    style_example(ws1b, 2 + i, len(headers_1b))

auto_width(ws1b, len(headers_1b))
ws1b.column_dimensions['B'].width = 35
ws1b.column_dimensions['K'].width = 22

add_legend(ws1b, 9, [
    ('HOW TO USE:', 'One row per SECTION (not per course). A course with 3 sections gets 3 rows.'),
    ('Section #:', 'Sequential number within the course (1, 2, 3...)'),
    ('Semester:', '"Fall & Spring" = full year, "Fall Only" = S1, "Spring Only" = S2, "Builder Choice" = engine decides'),
    ('Cap:', 'Maximum students in this section (e.g., 25, 30, 32)'),
    ('Teacher:', 'Full name "Last, First" — enter "TBD" if not yet assigned'),
    ('Room:', 'Room name/number — enter "TBD" if not yet assigned'),
    ('DELETE:', 'Delete the yellow example rows before uploading.'),
])

wb1.save(os.path.join(OUT, 'Template_1_Course_Sectioning.xlsx'))
print("Created: Template_1_Course_Sectioning.xlsx")


# ================================================================
# TEMPLATE 2: Student Course Requests
# ================================================================
wb2 = openpyxl.Workbook()
ws2 = wb2.active
ws2.title = 'Student Requests'

# Engine reads: A=StudentID, B=StudentName, D=CourseCode, E=CourseName, G=GradeLevel
# Columns C and F are spacers (the engine skips them)
headers_2 = ['Student ID', 'Student Name', 'Alt Course Code', 'Course Code',
             'Course Name', 'Request Type', 'Grade Level']
for c, h in enumerate(headers_2, 1):
    ws2.cell(1, c, h)
style_header(ws2, 1, len(headers_2))

examples_2 = [
    [106212, 'Garcia, Anthony', '', 111, 'Composition & Literature H', 'Primary', 'Grade 11'],
    [106212, 'Garcia, Anthony', '', 430, 'Algebra II/Trig', 'Primary', 'Grade 11'],
    [106212, 'Garcia, Anthony', '', 820, 'Theology 10', 'Required', 'Grade 11'],
    [106212, 'Garcia, Anthony', '', 732, 'Business Law', 'Elective', 'Grade 11'],
    [115945, 'Smith, Michael', '', 112, 'English 9', 'Required', 'Grade 9'],
    [115945, 'Smith, Michael', '', 410, 'Algebra I', 'Required', 'Grade 9'],
]
for i, row in enumerate(examples_2):
    for c, v in enumerate(row, 1):
        ws2.cell(2 + i, c, v)
    style_example(ws2, 2 + i, len(headers_2))

auto_width(ws2, len(headers_2))
ws2.column_dimensions['E'].width = 35

add_legend(ws2, 10, [
    ('HOW TO USE:', 'One row per COURSE REQUEST. A student requesting 8 courses gets 8 rows.'),
    ('Student ID:', 'Unique numeric ID from your SIS (e.g., 106212)'),
    ('Student Name:', '"Last, First" format'),
    ('Course Code:', 'Must match a code in Template 1 (Step 1 - Set Sections)'),
    ('Grade Level:', '"Grade 9", "Grade 10", "Grade 11", or "Grade 12"'),
    ('Alt Course Code:', 'Leave blank — column exists for SIS compatibility'),
    ('TYPICAL SIZE:', 'About 7,000-8,000 rows for 800 students (each student requests ~8-9 courses)'),
    ('DELETE:', 'Delete the yellow example rows before uploading.'),
])

wb2.save(os.path.join(OUT, 'Template_2_Student_Course_Requests.xlsx'))
print("Created: Template_2_Student_Course_Requests.xlsx")


# ================================================================
# TEMPLATE 3: LEO II Cohorts
# ================================================================
wb3 = openpyxl.Workbook()
ws3 = wb3.active
ws3.title = 'LEO II Cohorts'

# Engine reads: D=StudentName, F=Cohort (A or B)
headers_3 = ['Student ID', 'Last Name', 'First Name', 'Student Name (Last, First)',
             'Program', 'Cohort (A or B)']
for c, h in enumerate(headers_3, 1):
    ws3.cell(1, c, h)
style_header(ws3, 1, len(headers_3))

examples_3 = [
    [106300, 'Martinez', 'Carlos', 'Martinez, Carlos', 'LEO II', 'A'],
    [106415, 'Johnson', 'David', 'Johnson, David', 'LEO II', 'A'],
    [106522, 'Williams', 'James', 'Williams, James', 'LEO II', 'B'],
    [106688, 'Brown', 'Michael', 'Brown, Michael', 'LEO II', 'B'],
]
for i, row in enumerate(examples_3):
    for c, v in enumerate(row, 1):
        ws3.cell(2 + i, c, v)
    style_example(ws3, 2 + i, len(headers_3))

auto_width(ws3, len(headers_3))
ws3.column_dimensions['D'].width = 28

add_legend(ws3, 8, [
    ('HOW TO USE:', 'List all students in the LEO II program, with their cohort assignment (A or B).'),
    ('Student Name:', 'Must EXACTLY match the name in Template 2 (Student Course Requests)'),
    ('Cohort:', 'Enter "A" or "B" — cohort A and B are pinned to specific LEO sections'),
    ('TYPICAL SIZE:', 'About 36 students (18 per cohort)'),
    ('DELETE:', 'Delete the yellow example rows before uploading.'),
])

wb3.save(os.path.join(OUT, 'Template_3_LEO_II_Cohorts.xlsx'))
print("Created: Template_3_LEO_II_Cohorts.xlsx")


# ================================================================
# TEMPLATE 4: Tenant Intake / Co-Schedule Groups
# ================================================================
wb4 = openpyxl.Workbook()

# The engine reads sheet '5 Co-Schedule Groups'
ws4 = wb4.active
ws4.title = '5 Co-Schedule Groups'

# Engine reads: A=GroupName, B=CourseCodes(comma-sep), G=Period, H=Semester
headers_4 = ['Group Name', 'Course Codes (comma separated)', 'Description',
             'Min Sections', 'Max Sections', 'Priority',
             'Period (if fixed)', 'Semester (if fixed)']
for c, h in enumerate(headers_4, 1):
    ws4.cell(3, c, h)
style_header(ws4, 3, len(headers_4))

# Row 1-2 are title rows (engine starts reading at row 4)
ws4.cell(1, 1, 'CO-SCHEDULE GROUPS').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws4.cell(2, 1, 'Courses that must be scheduled in the same period').font = Font(name='Arial', size=10, color='7A7A7A')

examples_4 = [
    ['AP Art', '253, 254, 255, 764', 'AP Art courses share one period', 4, 4, 'High', '', ''],
    ['Studio Art II-III', '242, 243', 'Studio Art upper levels together', 2, 2, 'Medium', 3, ''],
    ['Robotics Project', '590, 591', 'Robotics paired sections', 2, 2, 'Medium', 'C', ''],
    ['Italian III/AP', '333, 352', 'Italian upper levels co-scheduled', 2, 2, 'Medium', 'G', ''],
    ['Guitar', '201, 203', 'Guitar levels together', 2, 2, 'Low', '', ''],
    ['Theater', '227, 228', 'Theater levels together', 1, 2, 'Low', '', ''],
]
for i, row in enumerate(examples_4):
    for c, v in enumerate(row, 1):
        ws4.cell(4 + i, c, v)
    style_example(ws4, 4 + i, len(headers_4))

auto_width(ws4, len(headers_4))
ws4.column_dimensions['B'].width = 30
ws4.column_dimensions['C'].width = 35

add_legend(ws4, 12, [
    ('HOW TO USE:', 'List groups of courses that MUST be scheduled in the same period.'),
    ('Course Codes:', 'Comma-separated list of course codes that share a period (e.g., "253, 254, 255, 764")'),
    ('Period:', 'Leave blank to let the engine choose, or enter A-G to fix the period'),
    ('Semester:', 'Leave blank for engine choice, or enter S1/S2 to fix the semester'),
    ('DELETE:', 'Delete the yellow example rows before uploading.'),
])

wb4.save(os.path.join(OUT, 'Template_4_CoSchedule_Groups.xlsx'))
print("Created: Template_4_CoSchedule_Groups.xlsx")


# ================================================================
# TEMPLATE 5: Prior-Year Master Schedule (Reference)
# ================================================================
wb5 = openpyxl.Workbook()
ws5 = wb5.active
ws5.title = 'Prior Year Schedule'

# Engine reads: A=ClassID, D=Teacher, E=Grading(S1/S2/FY), F=Period, H=Room
headers_5 = ['Class ID', 'Course Code', 'Course Title', 'Teacher',
             'Grading Period', 'Period', 'Section', 'Room']
for c, h in enumerate(headers_5, 1):
    ws5.cell(1, c, h)
style_header(ws5, 1, len(headers_5))

examples_5 = [
    ['111-1', 111, 'Composition & Literature H', 'Smith, Jane', 'S1', 'A', 1, 'Classroom D-101'],
    ['111-1', 111, 'Composition & Literature H', 'Smith, Jane', 'S2', 'A', 1, 'Classroom D-101'],
    ['430-1', 430, 'Algebra II/Trig', 'Jones, Robert', 'S1', 'C', 1, 'Classroom S-231'],
    ['430-1', 430, 'Algebra II/Trig', 'Jones, Robert', 'S2', 'C', 1, 'Classroom S-231'],
    ['766-1', 766, 'AP Microeconomics', 'Davis, Mark', 'S1', 'D', 1, 'Classroom S-238'],
]
for i, row in enumerate(examples_5):
    for c, v in enumerate(row, 1):
        ws5.cell(2 + i, c, v)
    style_example(ws5, 2 + i, len(headers_5))

auto_width(ws5, len(headers_5))
ws5.column_dimensions['C'].width = 35

add_legend(ws5, 9, [
    ('HOW TO USE:', 'Export last year\'s master schedule from your SIS. This is used for reference only — it helps the engine maintain teacher/period continuity.'),
    ('Class ID:', 'Format: CourseCode-SectionNumber (e.g., "111-1", "430-2")'),
    ('Grading Period:', '"S1" for Fall, "S2" for Spring, "FY" for Full-Year'),
    ('Period:', 'Letter A through G'),
    ('OPTIONAL:', 'This template is optional but recommended — it helps preserve prior-year alignment.'),
    ('DELETE:', 'Delete the yellow example rows before uploading.'),
])

wb5.save(os.path.join(OUT, 'Template_5_Prior_Year_Schedule.xlsx'))
print("Created: Template_5_Prior_Year_Schedule.xlsx")


print("\n" + "=" * 60)
print("ALL 5 TEMPLATES CREATED SUCCESSFULLY")
print("=" * 60)
print(f"\nLocation: {OUT}/")
print("""
Files:
  1. Template_1_Course_Sectioning.xlsx
     - Sheet 'Step 1 - Set Sections': Course catalog (code, title, dept, credits, type)
     - Sheet 'Step 2 - Assign Sections': Individual sections (teacher, room, cap, semester)

  2. Template_2_Student_Course_Requests.xlsx
     - One row per student-course request (~7,000-8,000 rows for 800 students)

  3. Template_3_LEO_II_Cohorts.xlsx
     - LEO II program students with cohort A/B assignment (~36 students)

  4. Template_4_CoSchedule_Groups.xlsx
     - Courses that must share the same period (e.g., AP Art, Guitar, Theater)

  5. Template_5_Prior_Year_Schedule.xlsx
     - Last year's master schedule for reference/alignment (OPTIONAL)
""")
