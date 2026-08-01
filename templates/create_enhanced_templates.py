"""Create enhanced templates that capture the full profile data designed
in the 30 spec artifacts — priority scoring, teacher profiles, student profiles,
course profiles, room profiles, contracts, and rules."""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import os

OUT = "/home/user/sat-course/templates"

# Shared styles
HEADER_FONT = Font(name='Arial', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1B4965', end_color='1B4965', fill_type='solid')
SUBHEADER_FONT = Font(name='Arial', bold=True, size=10, color='1B4965')
SUBHEADER_FILL = PatternFill(start_color='E3EDF4', end_color='E3EDF4', fill_type='solid')
EXAMPLE_FILL = PatternFill(start_color='FFF3CD', end_color='FFF3CD', fill_type='solid')
EXAMPLE_FONT = Font(name='Arial', size=10, italic=True, color='926B18')
REQUIRED_FILL = PatternFill(start_color='FDE8E4', end_color='FDE8E4', fill_type='solid')
OPTIONAL_FILL = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
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
        cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')
        cell.border = THIN_BORDER

def style_subheader(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = THIN_BORDER

def style_example(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row, c)
        cell.font = EXAMPLE_FONT
        cell.fill = EXAMPLE_FILL
        cell.border = THIN_BORDER

def auto_width(ws, widths):
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w


# ================================================================
# TEMPLATE 6: Teacher Profiles (48 columns from C1)
# ================================================================
wb6 = openpyxl.Workbook()
ws6 = wb6.active
ws6.title = 'Teacher Profiles'

headers_6 = [
    # Identity (Required)
    'Teacher ID', 'Last Name', 'First Name',
    # Organizational
    'Department 1', 'Department 2', 'Employment Status',
    # Contract
    'Contract Type', 'Hire Year', 'Seniority Rank',
    # Scheduling Constraints
    'Max Teaching Periods', 'Max Consec Periods', 'Requires 2 Consec Free',
    'Prep Periods Required', 'Duty Periods',
    # Approved Overload (3-column split: Full-Year, S1, S2)
    'Approved 6-Period Full-Year', 'Approved 6-Period Semester 1', 'Approved 6-Period Semester 2',
    # Period Availability (Required — Y/N for each)
    'Avail Per A', 'Avail Per B', 'Avail Per C', 'Avail Per D',
    'Avail Per E', 'Avail Per F', 'Avail Per G',
    # Preferences (Optional)
    'Preferred Periods', 'Avoid Periods',
    'Preferred Room', 'Preferred Wing',
    # Subject Affinities
    'Primary Subjects', 'Secondary Subjects',
    # Teacher Flags (Y/N)
    'Master Teacher', 'AP/Honors Teacher', 'SSP Teacher',
    # Certification (single set — Optional)
    'Certification Type', 'Certification Subject', 'Certification Expiry',
    # Course-Teacher Lock
    'Course-Teacher Lock Codes', 'Sole Teacher for Courses',
    # Prior Year (Optional)
    'Prior Year Periods Taught', 'Prior Year Room',
    # Derived (leave blank — engine fills)
    'Sections Assigned', 'Unique Courses', 'Full-Year Load', 'S1 Load', 'S2 Load',
    'Singleton Courses', 'Computed MTP Score',
    # Reference
    'Courses Assigned',
]

# Sub-header row showing Required vs Optional
subheaders_6 = [
    'REQUIRED', 'REQUIRED', 'REQUIRED',
    'REQUIRED', 'OPTIONAL',
    'REQUIRED', 'REQUIRED',
    'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'REQUIRED', 'Y/N', 'REQUIRED', 'REQUIRED',
    'Y/N', 'Y/N', 'Y/N',
    'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED', 'REQUIRED',
    'OPTIONAL', 'OPTIONAL',
    'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'OPTIONAL',
    'Y/N', 'Y/N', 'Y/N',
    'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'OPTIONAL', 'Y/N',
    'OPTIONAL', 'OPTIONAL',
    'DERIVED', 'DERIVED', 'DERIVED', 'DERIVED', 'DERIVED',
    'DERIVED', 'DERIVED',
    'DERIVED',
]

for c, h in enumerate(headers_6, 1):
    ws6.cell(1, c, h)
style_header(ws6, 1, len(headers_6))

for c, sh in enumerate(subheaders_6, 1):
    ws6.cell(2, c, sh)
    cell = ws6.cell(2, c)
    if sh == 'REQUIRED':
        cell.fill = REQUIRED_FILL
        cell.font = Font(name='Arial', bold=True, size=9, color='A63D2B')
    elif sh == 'DERIVED':
        cell.fill = PatternFill(start_color='EEF0F3', end_color='EEF0F3', fill_type='solid')
        cell.font = Font(name='Arial', size=9, color='5A6A7A')
    else:
        cell.fill = OPTIONAL_FILL
        cell.font = Font(name='Arial', size=9, color='2D6A4F')
    cell.alignment = Alignment(horizontal='center')
    cell.border = THIN_BORDER

# Example rows (48 columns each)
examples_6 = [
    ['T_GARCIA', 'Garcia', 'Anthony',
     'Mathematics', '', 'Active',
     'Standard', 2018, 5,
     5, 3, 'N', 1, 1,
     'N', 'N', 'N',
     'Y', 'Y', 'Y', 'Y', 'Y', 'Y', 'N',
     'A,B,C', '',
     'Classroom S-231', 'S-Wing',
     'Mathematics', 'Computer Science',
     'N', 'N', 'N',
     'NJ Standard', 'Mathematics', '2028-06-30',
     '', 'N',
     '', 'Classroom S-231',
     '', '', '', '', '', '', '', ''],
    ['T_SMITH', 'Smith', 'Jane',
     'English', '', 'Active',
     'Standard', 2015, 3,
     5, 3, 'Y', 1, 0,
     'Y', 'N', 'N',
     'Y', 'Y', 'Y', 'Y', 'Y', 'Y', 'Y',
     '', 'G',
     'Classroom D-101', 'D-Wing',
     'English', '',
     'Y', 'N', 'N',
     'NJ Standard', 'English Language Arts', '2027-06-30',
     '', 'N',
     '', 'Classroom D-101',
     '', '', '', '', '', '', '', ''],
    ['T_DANIELS', 'Daniels', 'Torrence',
     'Physical Education', '', 'Active',
     'Standard', 2020, 8,
     5, 2, 'N', 1, 1,
     'N', 'N', 'N',
     'Y', 'Y', 'Y', 'Y', 'Y', 'Y', 'N',
     '', '',
     'Gym', '',
     'Physical Education', '',
     'N', 'N', 'N',
     'NJ Standard', 'Physical Education', '2029-06-30',
     '620', 'N',
     '', 'Gym',
     '', '', '', '', '', '', '', ''],
]
for i, row in enumerate(examples_6):
    for c, v in enumerate(row, 1):
        ws6.cell(3 + i, c, v)
    style_example(ws6, 3 + i, len(headers_6))

# Data validations
dv_yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
dv_yn.error = "Enter Y or N"
dv_yn.errorTitle = "Invalid"
ws6.add_data_validation(dv_yn)
# Y/N columns: Requires 2 Consec Free (12), Approved 6-Period (15-17),
# Avail Per A-G (18-24), Master/AP/SSP Teacher (31-33), Sole Teacher (38)
for col in [12] + list(range(15, 25)) + [31, 32, 33, 38]:
    dv_yn.add(ws6.cell(3, col))

dv_status = DataValidation(type="list", formula1='"Active,Leave,Part-Time,Retired"', allow_blank=False)
ws6.add_data_validation(dv_status)

widths_6 = [12, 14, 14, 16, 14, 16, 14, 10, 12,
            16, 16, 18, 16, 12,
            12, 12, 12,
            10, 10, 10, 10, 10, 10, 10,
            16, 14, 16, 14,
            18, 18, 14, 16, 12,
            16, 16, 14,
            20, 14, 18, 14,
            16, 14, 14, 10, 10, 16, 16, 18]
auto_width(ws6, widths_6)

wb6.save(os.path.join(OUT, 'Template_6_Teacher_Profiles.xlsx'))
print("Created: Template_6_Teacher_Profiles.xlsx")


# ================================================================
# TEMPLATE 7: Course Profiles (94 data points from C3)
# ================================================================
wb7 = openpyxl.Workbook()
ws7 = wb7.active
ws7.title = 'Course Profiles'

headers_7 = [
    # Core (Required)
    'Course Code', 'Course Title', 'Department', 'Credits', 'Level',
    'Type (Full-Year/Semester)', 'Grade Levels (comma-sep)',
    # Sectioning (Required)
    'Sections Needed', 'Max Enrollment per Section', 'Min Enrollment',
    'Singleton',
    # Priority (Required — 8-input scoring)
    'Priority Level (0-5)',
    'CFP (Course Flexibility)', 'CYRP (Current Year Required)',
    'CTAP (Course-Teacher Affinity)', 'TL (Teacher Lock)',
    'PL (Period Lock)', 'RL (Room Lock)',
    # Semester (Required)
    'Semester Designation',
    # Requirements (Optional)
    'Prerequisites (codes)', 'Corequisites (codes)',
    'Required Certification', 'Required Room Type', 'Required Equipment',
    # Demand (Derived — leave blank, engine fills)
    'Total Requests', 'Demand Ratio',
    # Prior Year (Optional)
    'Prior Year Sections', 'Prior Year Avg Enrollment',
]

for c, h in enumerate(headers_7, 1):
    ws7.cell(1, c, h)
style_header(ws7, 1, len(headers_7))

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
for c, sh in enumerate(subheaders_7, 1):
    ws7.cell(2, c, sh)
    cell = ws7.cell(2, c)
    if sh == 'REQUIRED':
        cell.fill = REQUIRED_FILL
        cell.font = Font(name='Arial', bold=True, size=9, color='A63D2B')
    elif 'SCORING' in sh:
        cell.fill = PatternFill(start_color='F0EBF5', end_color='F0EBF5', fill_type='solid')
        cell.font = Font(name='Arial', bold=True, size=9, color='6B4E97')
    elif sh == 'DERIVED':
        cell.fill = PatternFill(start_color='EEF0F3', end_color='EEF0F3', fill_type='solid')
        cell.font = Font(name='Arial', size=9, color='5A6A7A')
    else:
        cell.fill = OPTIONAL_FILL
        cell.font = Font(name='Arial', size=9, color='2D6A4F')
    cell.alignment = Alignment(horizontal='center')
    cell.border = THIN_BORDER

examples_7 = [
    [111, 'Composition & Literature H', 'English', 5.0, 'Honors',
     'Full-Year', '9,10',
     3, 25, 10, 'N',
     4,
     2, 5, 4, 3, 0, 0,
     'AI CHOICE',
     '', '', 'English Language Arts', 'Classroom', '',
     '', '',
     3, 24],
    [430, 'Algebra II/Trig', 'Mathematics', 5.0, 'Regular',
     'Full-Year', '10,11',
     4, 30, 12, 'N',
     3,
     2, 4, 3, 2, 0, 0,
     'AI CHOICE',
     '410', '', 'Mathematics', 'Classroom', '',
     '', '',
     4, 28],
    [766, 'AP Microeconomics', 'Social Studies', 2.5, 'AP',
     'Semester', '11,12',
     1, 30, 8, 'Y',
     5,
     5, 5, 5, 4, 5, 0,
     'S1 ONLY',
     '', '765', 'Social Studies', 'Classroom', '',
     '', '',
     1, 22],
    [732, 'Business Law', 'Business', 2.5, 'Regular',
     'Semester', '11,12',
     1, 32, 10, 'N',
     1,
     1, 1, 1, 0, 0, 0,
     'AI CHOICE',
     '', '', '', 'Classroom', '',
     '', '',
     1, 30],
]
for i, row in enumerate(examples_7):
    for c, v in enumerate(row, 1):
        ws7.cell(3 + i, c, v)
    style_example(ws7, 3 + i, len(headers_7))

widths_7 = [12, 30, 16, 10, 10, 18, 16,
            12, 16, 12, 10,
            12,
            12, 12, 12, 12, 12, 12,
            16,
            16, 16, 20, 16, 16,
            12, 12,
            14, 18]
auto_width(ws7, widths_7)

wb7.save(os.path.join(OUT, 'Template_7_Course_Profiles.xlsx'))
print("Created: Template_7_Course_Profiles.xlsx")


# ================================================================
# TEMPLATE 8: Student Profiles (155 data points from C2)
# ================================================================
wb8 = openpyxl.Workbook()
ws8 = wb8.active
ws8.title = 'Student Profiles'

headers_8 = [
    # Identity (Required — ID only, NO names/emails/phones)
    'Student ID',
    # Academic (Required)
    'Grade Level', 'Credits Earned', 'Credits Required', 'GPA Band',
    # Priority (Required)
    'Priority Level (P0-P5)',
    'SSP',
    # Special Needs (Conditional)
    'Has IEP', 'IEP Max Class Size', 'IEP Required Periods',
    # SSP Population Memberships (Y/N — multi-membership allowed)
    'LEO II', 'Pathway', 'Academic Support',
    # Program Flags
    'Honors Track', 'AP Track',
    'Cohort Name', 'Cohort Locked',
    # Derived (leave blank — engine fills)
    'Requests Total', 'Requests Fulfilled', 'Placement Rate',
    'Conflicts Active',
]

for c, h in enumerate(headers_8, 1):
    ws8.cell(1, c, h)
style_header(ws8, 1, len(headers_8))

subheaders_8 = [
    'REQUIRED',
    'REQUIRED', 'OPTIONAL', 'OPTIONAL', 'OPTIONAL',
    'REQUIRED', 'SCORING 0-5',
    'CONDITIONAL', 'CONDITIONAL', 'CONDITIONAL',
    'Y/N', 'Y/N', 'Y/N',
    'Y/N', 'Y/N', 'OPTIONAL', 'Y/N',
    'DERIVED', 'DERIVED', 'DERIVED', 'DERIVED',
]
for c, sh in enumerate(subheaders_8, 1):
    ws8.cell(2, c, sh)
    cell = ws8.cell(2, c)
    if sh == 'REQUIRED':
        cell.fill = REQUIRED_FILL
        cell.font = Font(name='Arial', bold=True, size=9, color='A63D2B')
    elif 'SCORING' in sh:
        cell.fill = PatternFill(start_color='F0EBF5', end_color='F0EBF5', fill_type='solid')
        cell.font = Font(name='Arial', bold=True, size=9, color='6B4E97')
    elif sh == 'CONDITIONAL':
        cell.fill = PatternFill(start_color='FDF3E4', end_color='FDF3E4', fill_type='solid')
        cell.font = Font(name='Arial', size=9, color='926B18')
    elif sh == 'DERIVED':
        cell.fill = PatternFill(start_color='EEF0F3', end_color='EEF0F3', fill_type='solid')
        cell.font = Font(name='Arial', size=9, color='5A6A7A')
    else:
        cell.fill = OPTIONAL_FILL
        cell.font = Font(name='Arial', size=9, color='2D6A4F')
    cell.alignment = Alignment(horizontal='center')
    cell.border = THIN_BORDER

examples_8 = [
    [106212, 11, 55.0, 120.0, '3.5-4.0',
     'P3', 3,
     'N', '', '',
     'N', 'Y', 'N', '', 'N',
     '', '', '', ''],
    [106276, 11, 52.5, 120.0, '3.0-3.5',
     'P2', 4,
     'Y', 15, 'A,B',
     'Y', 'N', 'N', 'LEO Cohort A', 'Y',
     '', '', '', ''],
    [115945, 9, 0, 120.0, '',
     'P3', 1,
     'N', '', '',
     'N', 'N', 'N', '', 'N',
     '', '', '', ''],
]
for i, row in enumerate(examples_8):
    for c, v in enumerate(row, 1):
        ws8.cell(3 + i, c, v)
    style_example(ws8, 3 + i, len(headers_8))

widths_8 = [12, 10, 12, 14, 10,
            14, 12,
            8, 14, 20,
            8, 10, 8, 16, 12,
            12, 14, 12, 12]
auto_width(ws8, widths_8)

wb8.save(os.path.join(OUT, 'Template_8_Student_Profiles.xlsx'))
print("Created: Template_8_Student_Profiles.xlsx")


# ================================================================
# TEMPLATE 9: Room Profiles (91 data points from C4)
# ================================================================
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

examples_9 = [
    ['RM_D101', 'D-101', 'Main', 'D-Wing', 1, 30, 'Classroom',
     'Y', 'Y', 'N', 'N', 'Y', 'A,B,C,D,E,F,G', 'N', 'Smith, Jane', 'D-102,D-103'],
    ['RM_S231', 'S-231', 'Main', 'S-Wing', 2, 32, 'Classroom',
     'Y', 'Y', 'N', 'N', 'Y', 'A,B,C,D,E,F,G', 'N', '', 'S-232,S-233'],
    ['RM_SCI1', 'I-114', 'Science', 'I-Wing', 1, 24, 'Lab',
     'Y', 'N', 'Y', 'N', 'Y', 'A,B,C,D,E,F,G', 'N', 'Martino, Brianna', 'I-115,I-117'],
    ['RM_GYM', 'Gym', 'Athletic', '', 1, 80, 'Gymnasium',
     'N', 'N', 'N', 'N', 'Y', 'A,B,C,D,E,F,G', 'Y', '', ''],
]
for i, row in enumerate(examples_9):
    for c, v in enumerate(row, 1):
        ws9.cell(2 + i, c, v)
    style_example(ws9, 2 + i, len(headers_9))

widths_9 = [12, 12, 12, 10, 8, 10, 14,
            12, 14, 14, 12, 12, 24, 10, 18, 22]
auto_width(ws9, widths_9)

wb9.save(os.path.join(OUT, 'Template_9_Room_Profiles.xlsx'))
print("Created: Template_9_Room_Profiles.xlsx")


# ================================================================
# TEMPLATE 10: Contracts (68 data points from C12)
# ================================================================
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

examples_10 = [
    ['STD', 'Standard Teacher Contract', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     5, 0, 3, 7, 1, 'N', 1, 'Y', 4, 6, 0, 3],
    ['PART', 'Part-Time Contract', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     3, 0, 2, 4, 1, 'N', 0, 'Y', 2, 4, 0, 2],
    ['DEPT', 'Department Head Contract', 'Faculty Association',
     '2026-09-01', '2027-06-30',
     4, 0, 3, 7, 1, 'N', 1, 'Y', 3, 5, 0, 3],
]
for i, row in enumerate(examples_10):
    for c, v in enumerate(row, 1):
        ws10.cell(2 + i, c, v)
    style_example(ws10, 2 + i, len(headers_10))

widths_10 = [14, 28, 20, 14, 14,
             16, 16, 18, 16, 16, 18, 14, 16, 16, 16, 18, 14]
auto_width(ws10, widths_10)

wb10.save(os.path.join(OUT, 'Template_10_Contracts.xlsx'))
print("Created: Template_10_Contracts.xlsx")


# ================================================================
# TEMPLATE 11: Priority Scoring Reference
# ================================================================
wb11 = openpyxl.Workbook()

# Sheet 1: Scoring Scale Reference
ws11a = wb11.active
ws11a.title = 'Priority Scale 0-5'

ws11a.cell(1, 1, 'PRIORITY SCORING SCALE (0-5)').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws11a.cell(2, 1, 'Used by the 8-input weighted composite scoring system').font = Font(name='Arial', size=10, color='7A7A7A')

headers_11a = ['Level', 'Label', 'Description', 'Example Courses']
for c, h in enumerate(headers_11a, 1):
    ws11a.cell(4, c, h)
style_header(ws11a, 4, len(headers_11a))

scale_rows = [
    [5, 'PROTECTED / MANDATED', 'Cannot be bumped under any circumstance. Federal/state mandates, IEP requirements.', 'LEO II (745, 734), Academic Support (955)'],
    [4, 'Required Core / Graduation', 'Required for graduation. Must be placed before any lower priority.', 'English (111, 130, 140), Theology (810, 820, 830, 840), US History (710, 711)'],
    [3, 'Sequence / Honors / AP', 'Part of an academic sequence or advanced track. High placement priority.', 'AP Microeconomics (766), Precalculus (440), Chemistry H (541)'],
    [2, 'Departmental Core', 'Core departmental offerings. Important but not graduation-critical.', 'Physics (542), Spanish II (320), World History (720)'],
    [1, 'Standard Elective', 'Elective courses. Placed after all higher priorities are satisfied.', 'Business Law (732), Forensics (546), Psychology (741)'],
    [0, 'Free Elective / Low Demand', 'Nice-to-have. Placed last. Acceptable loss if conflicts exist.', 'Study Hall, Independent Study'],
]
for i, row in enumerate(scale_rows):
    for c, v in enumerate(row, 1):
        ws11a.cell(5 + i, c, v)
    style_example(ws11a, 5 + i, len(headers_11a))

auto_width(ws11a, [8, 28, 60, 50])

# Sheet 2: 8-Input Weights Reference
ws11b = wb11.create_sheet('8-Input Weights')

ws11b.cell(1, 1, '8-INPUT WEIGHTED COMPOSITE SCORING SYSTEM').font = Font(name='Arial', bold=True, size=14, color='1B4965')
ws11b.cell(2, 1, 'Each student-course placement is scored using these 8 inputs').font = Font(name='Arial', size=10, color='7A7A7A')

headers_11b = ['Input', 'Code', 'Weight', 'Range', 'Description', 'Source']
for c, h in enumerate(headers_11b, 1):
    ws11b.cell(4, c, h)
style_header(ws11b, 4, len(headers_11b))

weight_rows = [
    ['Course Flexibility Priority', 'CFP', 1.0, '0-5', 'How flexible is this course in scheduling? 0=very flexible, 5=extremely rigid (singleton)', 'Course Profile'],
    ['Current Year Required Priority', 'CYRP', 1.5, '0-5', 'Is this course required THIS year? 5=graduation requirement, 0=optional elective', 'Course Profile'],
    ['Student Special Priority', 'SSP', 2.0, '0-5', 'Does this student have special scheduling needs? IEP, 504, LEO, cohort lock', 'Student Profile'],
    ['Master Teacher Priority', 'MTP', 1.0, '0-5', 'Is the assigned teacher a master teacher or highly constrained?', 'Teacher Profile'],
    ['Course-Teacher Affinity Priority', 'CTAP', 1.5, '0-5', 'How strong is the teacher-course match? 5=only certified teacher for this course', 'Course + Teacher Profile'],
    ['Teacher Lock', 'TL', 2.0, '0-5', 'Is the teacher locked to specific periods? 5=completely locked (e.g., part-time, shared)', 'Teacher Profile'],
    ['Period Lock', 'PL', 2.0, '0-5', 'Is this course locked to a specific period? 5=must be Period X (e.g., LEO courses)', 'Course Profile'],
    ['Room Lock', 'RL', 1.5, '0-5', 'Is this course locked to a specific room? 5=can only use one room (lab, gym)', 'Room Profile'],
]
for i, row in enumerate(weight_rows):
    for c, v in enumerate(row, 1):
        ws11b.cell(5 + i, c, v)
    style_example(ws11b, 5 + i, len(headers_11b))

ws11b.cell(14, 1, 'Maximum Weighted Sum:').font = Font(name='Arial', bold=True, size=11, color='1B4965')
ws11b.cell(14, 2, '= 5×(1.0 + 1.5 + 2.0 + 1.0 + 1.5 + 2.0 + 2.0 + 1.5) = 62.5').font = Font(name='Arial', size=11)

ws11b.cell(15, 1, 'Constraint Count:').font = Font(name='Arial', bold=True, size=11, color='1B4965')
ws11b.cell(15, 2, '= Number of inputs scoring >= 4 (higher = more constrained student)').font = Font(name='Arial', size=11)

auto_width(ws11b, [28, 8, 8, 8, 60, 18])

wb11.save(os.path.join(OUT, 'Template_11_Priority_Scoring_Reference.xlsx'))
print("Created: Template_11_Priority_Scoring_Reference.xlsx")


print("\n" + "=" * 60)
print("ALL ENHANCED TEMPLATES CREATED SUCCESSFULLY")
print("=" * 60)
print(f"\nLocation: {OUT}/")
print("""
Enhanced Templates (from the product spec profiles):
  6.  Template_6_Teacher_Profiles.xlsx     — 48 columns (C1)
  7.  Template_7_Course_Profiles.xlsx      — 94 data points + 8-input scoring (C3)
  8.  Template_8_Student_Profiles.xlsx     — 155 data points, priority P0-P5 (C2)
  9.  Template_9_Room_Profiles.xlsx        — 91 data points (C4)
  10. Template_10_Contracts.xlsx           — 68 data points, cascade rules (C12)
  11. Template_11_Priority_Scoring_Reference.xlsx — Scale 0-5 + 8-input weights reference

These templates capture the full profile system designed in the commercial spec.
Fill them with Don Bosco Prep data from the SIS, and the enhanced engine will use them.
""")
