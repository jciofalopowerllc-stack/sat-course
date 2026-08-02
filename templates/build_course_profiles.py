#!/usr/bin/env python3
"""Build Template_7_Course_Profiles.xlsx from source course list and PDF catalog data."""

import openpyxl
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from collections import Counter
import re

HEADER_FONT = Font(name='Arial', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1B4965', end_color='1B4965', fill_type='solid')
SUBHEADER_FONT = Font(name='Arial', bold=True, size=9, color='A63D2B')
SUBHEADER_FILL = PatternFill(start_color='FDE8E4', end_color='FDE8E4', fill_type='solid')
OPT_FONT = Font(name='Arial', size=9, color='2D6A4F')
OPT_FILL = PatternFill(start_color='E8F5EE', end_color='E8F5EE', fill_type='solid')
DATA_FONT = Font(name='Arial', size=10)
THIN_BORDER = Border(
    left=Side(style='thin', color='D4D0C8'),
    right=Side(style='thin', color='D4D0C8'),
    top=Side(style='thin', color='D4D0C8'),
    bottom=Side(style='thin', color='D4D0C8'),
)

HEADERS = [
    "Course Code", "Course Title", "Department", "Credits",
    "Prescribed Term", "Grade Levels", "Sections Needed",
    "Max Enrollment per Section", "Singleton", "AP",
    "Graduation Requirement", "Cohort", "NCAA",
    "Prerequisites", "Corequisites"
]

REQ_OPT = [
    "REQUIRED", "REQUIRED", "REQUIRED", "REQUIRED",
    "REQUIRED", "REQUIRED", "REQUIRED",
    "REQUIRED", "REQUIRED", "REQUIRED",
    "OPTIONAL", "OPTIONAL", "OPTIONAL",
    "OPTIONAL", "OPTIONAL"
]

# ---- Load source course list ----
src_path = "/root/.claude/uploads/a04b5f0d-60df-588f-8acb-79549aab48c5/961ac155-Course_List_373_records_20260801.xlsx"
wb_src = openpyxl.load_workbook(src_path)
ws_src = wb_src.active

courses_raw = []
for r in range(2, ws_src.max_row + 1):
    vals = [ws_src.cell(r, c).value for c in range(1, ws_src.max_column + 1)]
    code = str(vals[0]).strip() if vals[0] else ""
    name = str(vals[1] or "").strip()
    dept = str(vals[2] or "").strip()
    credits = vals[3]
    ctype = str(vals[4] or "").strip()
    subj = str(vals[5] or "").strip()
    ap_flag = str(vals[6] or "").strip().upper() == "TRUE"
    if code:
        courses_raw.append({
            "code": code, "name": name, "dept": dept,
            "credits": credits, "type": ctype, "subject": subj,
            "ap_src": ap_flag
        })

print(f"Loaded {len(courses_raw)} courses from source")

# ---- Load section counts from Prior Year Master Schedule ----
wb_py = openpyxl.load_workbook("templates/new/Template_Prior_Year_Master_Schedule.xlsx")
ws_py = wb_py.active
section_counts = Counter()
for r in range(3, ws_py.max_row + 1):
    code = str(ws_py.cell(r, 2).value).strip() if ws_py.cell(r, 2).value else ""
    if code:
        section_counts[code] += 1

# ---- PDF catalog data: manually parsed course metadata ----
# Grade levels, prerequisites, term (full/half year), NCAA, grad req
# Parsed from the 49-page Don Bosco Prep 2026-2027 Course Catalog

catalog = {}

def cat(code, grades=None, term="FY", ncaa=False, prereqs=None, coreqs=None, grad_req=None):
    catalog[str(code)] = {
        "grades": grades or [],
        "term": term,
        "ncaa": ncaa,
        "prereqs": prereqs or [],
        "coreqs": coreqs or [],
        "grad_req": grad_req
    }

# BUSINESS DEPARTMENT
cat("708", grades=[9,10,12], term="S1", ncaa=True, grad_req=None)  # Intro to Business - half year
cat("729", grades=[10], term="FY", ncaa=False, prereqs=["708"])  # AP Business w/ Personal Finance
cat("726", grades=[10], term="S1", ncaa=True)  # Business Concepts
cat("727", grades=[10,11], term="S1", ncaa=True)  # Sports & Entertainment Marketing
cat("732", grades=[11,12], term="S1", ncaa=True)  # Business Law
cat("740", grades=[11], term="FY", ncaa=True, prereqs=["729"])  # International Business Strategy
cat("757", grades=[11], term="FY", ncaa=True, prereqs=["729"])  # International Business Strategy (dup code)
cat("734", grades=[11], term="S1", ncaa=False, prereqs=["728"])  # LEO I
cat("742", grades=[12], term="FY", ncaa=True)  # Economics
cat("752", grades=[12], term="FY", ncaa=True)  # Economics Honors
cat("745", grades=[12], term="S1", ncaa=False, prereqs=["734"])  # LEO II
cat("709", grades=[9,10,11,12], term="S1", ncaa=False)  # Financial Literacy
cat("7090", grades=[9,10,11,12], term="S1", ncaa=False)  # Financial Literacy (dup)
cat("728", grades=[10,11], term="S1", ncaa=False)  # Principles of Accounting
cat("746", grades=[10,11,12], term="S1", ncaa=False)  # Principles of Marketing
cat("758", grades=[11,12], term="S1", ncaa=False)  # Bloomberg Market Concepts
cat("750", grades=[12], term="S1", ncaa=False)  # American Government (old code in business)

# COMMUNICATION ARTS DEPARTMENT
cat("2014", grades=[9], term="S1")  # Multi-Media Production
cat("2054", grades=[9,10,11,12], term="S1")  # Digital Media
cat("2024", grades=[10], term="S1", prereqs=["2014"])  # TV/Film Process and Principles
cat("2034", grades=[11], term="S1", prereqs=["2024"])  # TV/Film Production & Editing I
cat("2044", grades=[12], term="S1", prereqs=["2034"])  # TV/Film Production II
cat("2003", grades=[10,11,12], term="S1")  # TV Production Engineering & Technology
cat("2001", grades=[10,11,12], term="S1")  # TV/Film Production (general)

# COMPUTER SCIENCE DEPARTMENT
cat("473", grades=[9,10,11,12], term="S1")  # Introduction to Programming
cat("472", grades=[10,11,12], term="S1")  # Web Design
cat("494", grades=[10,11,12], term="S1", prereqs=["473"])  # Applied Programming
cat("491", grades=[10,11,12], term="FY", prereqs=["473"])  # AP Computer Science Principles
cat("490", grades=[11,12], term="FY", prereqs=["473"])  # AP Computer Science A
cat("496", grades=[11,12], term="FY", ncaa=True, prereqs=["490"])  # AP Cybersecurity
cat("495", grades=[12], term="FY", prereqs=["490"])  # App Development (full year)
cat("480", grades=[12], term="FY", prereqs=["490"])  # App Development I
cat("481", grades=[12], term="FY", prereqs=["480"])  # App Development II
cat("485", grades=[10,11,12], term="S1")  # Programming I: Coding in Visual Basic
cat("4940", grades=[11,12], term="S1", prereqs=["485"])  # Programming II: Game Development in C#
cat("4950", grades=[10,11,12], term="S1")  # Animation

# ENGINEERING DEPARTMENT
cat("570", grades=[9], term="S1", ncaa=True)  # Introduction to Robotics
cat("580", grades=[10,11], term="S1", ncaa=True, prereqs=["410"])  # Robotics Engineering
cat("585", grades=[10,11], term="S1", ncaa=True, prereqs=["580"])  # Robotics Design
cat("590", grades=[11,12], term="S1", ncaa=True, prereqs=["585"])  # Robotics Project
cat("591", grades=[11,12], term="S1", ncaa=True, prereqs=["590"])  # Robotics Project II
cat("595", grades=[12], term="S1", ncaa=True, coreqs=["530"])  # Engineering Design
cat("596", grades=[12], term="S1", ncaa=True, prereqs=["595"])  # Engineering Design II

# ENGLISH DEPARTMENT - Core
cat("110", grades=[9], term="FY", ncaa=True, grad_req="English")  # Comp & Lit
cat("111", grades=[9], term="FY", ncaa=True, grad_req="English")  # Comp & Lit H
cat("112", grades=[9], term="FY", ncaa=True, grad_req="English")  # Comp & Lit (dup)
cat("120", grades=[10], term="FY", ncaa=True, grad_req="English")  # American Literature
cat("121", grades=[10], term="FY", ncaa=True, grad_req="English")  # American Literature H
cat("122", grades=[10], term="FY", ncaa=True, grad_req="English")  # American Literature (dup)
cat("129", grades=[10], term="FY", ncaa=True, grad_req="English")  # AP Seminar
cat("130", grades=[11], term="FY", ncaa=True, grad_req="English")  # British Literature
cat("131", grades=[11], term="FY", ncaa=True, grad_req="English")  # British Literature H
cat("132", grades=[11], term="FY", ncaa=True, grad_req="English")  # British Literature (dup)
cat("139", grades=[11], term="FY", ncaa=True, grad_req="English")  # AP English Language
cat("150", grades=[11], term="FY", ncaa=True, grad_req="English", prereqs=["129"])  # AP Research
cat("140", grades=[12], term="FY", ncaa=True, grad_req="English")  # World Literature
cat("146", grades=[12], term="FY", ncaa=True, grad_req="English")  # World Literature (dup)
cat("141", grades=[12], term="FY", ncaa=True, grad_req="English")  # College English Honors
cat("149", grades=[12], term="FY", ncaa=True, grad_req="English")  # AP English Literature
# English Electives
cat("144", grades=[9,10,11,12], term="S1", ncaa=True)  # Public Speaking
cat("143", grades=[10,11,12], term="S1", ncaa=True)  # Creative Writing
cat("145", grades=[10,11,12], term="S1", ncaa=True)  # Journalism

# HUMANITIES (ART/MUSIC)
cat("241", grades=[9,10,11,12], term="S1")  # Studio Art I
cat("242", grades=[10,11,12], term="S1", prereqs=["241"])  # Studio Art II
cat("243", grades=[11,12], term="S1", prereqs=["242"])  # Studio Art III
cat("244", grades=[11,12], term="S1", prereqs=["243"])  # Studio Art IV
cat("245", grades=[12], term="S1", prereqs=["244"])  # Studio Art V
cat("247", grades=[10,11,12], term="S1", prereqs=["241"])  # Studio Art II - 3-D
cat("2450", grades=[10,11,12], term="S1", prereqs=["241"])  # Studio Art II - Drawing
cat("248", grades=[10,11,12], term="S1", prereqs=["241"])  # Advanced Drawing
cat("249", grades=[10,11,12], term="S1", prereqs=["241"])  # Advanced Painting
cat("253", grades=[11,12], term="FY", prereqs=["242"])  # AP Drawing
cat("254", grades=[11,12], term="FY", prereqs=["242"])  # AP 2-D Art and Design
cat("255", grades=[11,12], term="FY", prereqs=["242"])  # AP 3-D Art and Design
cat("252", grades=[11,12], term="FY", prereqs=["242"])  # AP Art and Design
cat("250", grades=[10,11,12], term="S1")  # Digital Design and Illustration
cat("206", grades=[9,10,11,12], term="FY")  # Band
cat("209", grades=[9,10,11,12], term="FY")  # String Orchestra
cat("211", grades=[9,10,11,12], term="FY")  # String Orchestra (dup)
cat("212", grades=[9,10,11,12], term="FY")  # String Orchestra (dup)
cat("201", grades=[9,10,11,12], term="S1")  # Introduction to Guitar
cat("203", grades=[9,10,11,12], term="FY", prereqs=["201"])  # Guitar Ensemble
cat("220", grades=[10,11,12], term="S1")  # Music Theory
cat("210", grades=[9,10,11,12], term="S1")  # Introduction to Art

# MATHEMATICS DEPARTMENT - Core
cat("410", grades=[9], term="FY", ncaa=True, grad_req="Mathematics")  # Algebra I
cat("411", grades=[9], term="FY", ncaa=True, grad_req="Mathematics")  # Algebra I H
cat("412", grades=[9], term="FY", ncaa=True, grad_req="Mathematics")  # Algebra I (dup)
cat("425", grades=[9], term="FY", ncaa=True, grad_req="Mathematics")  # Adv Geometry H
cat("420", grades=[10], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["410"])  # Geometry
cat("421", grades=[9,10], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["411"])  # Geometry H
cat("422", grades=[10], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["410"])  # Geometry (dup)
cat("435", grades=[10], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["425"])  # Adv Algebra II/Trig H
cat("430", grades=[10,11], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["420"])  # Algebra II/Trig
cat("431", grades=[10,11], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["421"])  # Algebra II/Trig H
cat("432", grades=[10,11], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["420"])  # Algebra II/Trig (dup)
cat("445", grades=[11], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["435"])  # Adv Precalculus H
cat("440", grades=[11,12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["430"])  # Precalculus
cat("441", grades=[11,12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["431"])  # Precalculus H (now AP Precalc)
cat("443", grades=[11,12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["431"])  # AP Precalculus
cat("448", grades=[12], term="FY", ncaa=True, grad_req="Mathematics")  # Pre-college Math
cat("450", grades=[12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["440"])  # Calculus H
cat("453", grades=[12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["443"])  # AP Calc AB
cat("455", grades=[12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["443"])  # AP Calc BC
cat("456", grades=[12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["453"])  # AP Statistics
cat("444", grades=[11,12], term="FY", ncaa=True, grad_req="Mathematics")  # Probability & Statistics
cat("460", grades=[12], term="FY", ncaa=True, grad_req="Mathematics", prereqs=["455"])  # Multivariable Calculus H

# PHYSICAL EDUCATION DEPARTMENT
cat("610", grades=[9], term="S1", grad_req="Physical Education")  # Health/PE
cat("613", grades=[9], term="S1", grad_req="Physical Education")  # Health
cat("620", grades=[10], term="S1", grad_req="Physical Education")  # Driver's Ed/PE
cat("622", grades=[10], term="S1", grad_req="Physical Education")  # Driver's Ed/PE (dup)
cat("631", grades=[11], term="S1", grad_req="Physical Education")  # CPR-AED Training/PE
cat("633", grades=[11], term="S1", grad_req="Physical Education")  # CPR-AED Training/PE (dup)
cat("642", grades=[12], term="S1", grad_req="Physical Education")  # Nutrition & Fitness/PE

# SCIENCE DEPARTMENT - Core
cat("500", grades=[9], term="FY", ncaa=True, grad_req="Science")  # Earth Science
cat("510", grades=[9,10], term="FY", ncaa=True, grad_req="Science")  # Biology
cat("511", grades=[9], term="FY", ncaa=True, grad_req="Science")  # Biology H
cat("520", grades=[10,11], term="FY", ncaa=True, grad_req="Science", prereqs=["510"])  # Chemistry
cat("521", grades=[10], term="FY", ncaa=True, grad_req="Science", prereqs=["511"])  # Chemistry H
cat("530", grades=[11,12], term="FY", ncaa=True, grad_req="Science", prereqs=["520"])  # Physics
cat("531", grades=[11,12], term="FY", ncaa=True, grad_req="Science", prereqs=["521"])  # Physics H
cat("551", grades=[10,11,12], term="FY", ncaa=True, grad_req="Science", prereqs=["511"])  # AP Biology
cat("553", grades=[11,12], term="FY", ncaa=True, grad_req="Science", prereqs=["521"])  # AP Chemistry
cat("556", grades=[12], term="FY", ncaa=True, grad_req="Science")  # AP Physics (general)
cat("557", grades=[12], term="FY", ncaa=True, grad_req="Science", prereqs=["531"])  # AP Physics 1
cat("558", grades=[12], term="FY", ncaa=True, grad_req="Science", prereqs=["531"])  # AP Physics C
# Science Electives
cat("542", grades=[11,12], term="FY", ncaa=True, prereqs=["510","520"])  # Anatomy/Physiology
cat("543", grades=[11,12], term="FY", ncaa=True, prereqs=["510","520"])  # Anatomy/Physiology H
cat("544", grades=[12], term="FY", ncaa=True, prereqs=["510","520","530"])  # Sports Medicine
cat("545", grades=[11,12], term="FY", ncaa=True)  # Biotechnology Lab Skills H
cat("546", grades=[11,12], term="FY", ncaa=True)  # Forensics

# SOCIAL STUDIES DEPARTMENT - Core
cat("710", grades=[9], term="FY", ncaa=True, grad_req="Social Studies")  # World History
cat("711", grades=[9], term="FY", ncaa=True, grad_req="Social Studies")  # World History H
cat("713", grades=[9], term="FY", ncaa=True, grad_req="Social Studies")  # AP World History
cat("720", grades=[10], term="FY", ncaa=True, grad_req="Social Studies")  # US History I
cat("721", grades=[10], term="FY", ncaa=True, grad_req="Social Studies")  # US History I H
cat("722", grades=[10], term="FY", ncaa=True, grad_req="Social Studies")  # Adv US History I H
cat("730", grades=[11], term="FY", ncaa=True, grad_req="Social Studies")  # US History II
cat("731", grades=[11], term="FY", ncaa=True, grad_req="Social Studies")  # US History II H
cat("733", grades=[11], term="FY", ncaa=True, grad_req="Social Studies", prereqs=["722"])  # AP US History
# Senior SS (half year requirement)
cat("751", grades=[11,12], term="S1", ncaa=True, grad_req="Social Studies")  # American Gov & Politics
cat("763", grades=[12], term="FY", ncaa=True, grad_req="Social Studies", prereqs=["731"])  # AP US Gov & Politics
cat("767", grades=[12], term="FY", ncaa=True, grad_req="Social Studies", prereqs=["731"])  # AP US Gov (dup)
cat("764", grades=[10,11,12], term="FY", ncaa=True, grad_req="Social Studies")  # AP Art History
cat("743", grades=[12], term="FY", ncaa=True, grad_req="Social Studies", prereqs=["731"])  # AP European History
cat("765", grades=[12], term="S1", ncaa=True, prereqs=["733"])  # AP Macroeconomics
cat("766", grades=[12], term="S1", ncaa=True, prereqs=["733"])  # AP Microeconomics
# Social Studies Electives
cat("744", grades=[10,11,12], term="S1", ncaa=True)  # Sociology
cat("723", grades=[10,11,12], term="S1")  # Intro to Political Science
cat("741", grades=[11,12], term="S1", ncaa=True)  # Psychology
cat("761", grades=[12], term="FY", ncaa=True, prereqs=["131"])  # AP Psychology
cat("747", grades=[12], term="S1", ncaa=True)  # Philosophy
cat("756", grades=[12], term="S1")  # Introduction to Law
cat("749", grades=[11,12], term="S1", ncaa=True)  # Government & Politics
cat("748", grades=[11,12], term="S1", ncaa=True)  # History of Music in Modern America
cat("753", grades=[11,12], term="S1", ncaa=True)  # History of American Democracy

# THEATER ARTS DEPARTMENT
cat("226", grades=[9,10,11,12], term="S1")  # Introduction to Theater
cat("227", grades=[10,11,12], term="S1", prereqs=["226"])  # Intermediate Theater
cat("228", grades=[11,12], term="S1", prereqs=["226"])  # Advanced Theater Production
cat("221", grades=[9,10,11,12], term="S1")  # Acting 1 / Story Lab
cat("223", grades=[10,11,12], term="S1")  # Theater Production / Tech Theater
cat("224", grades=[10,11,12], term="S1")  # Playwriting
cat("225", grades=[9,10,11,12], term="S1")  # Tech Theater Level 1 (not in source but in schedule)
cat("2120", grades=[11,12], term="S1")  # Independent Study - Playwriting

# THEOLOGY DEPARTMENT - Core
cat("810", grades=[9], term="FY", grad_req="Theology")  # Theology 9
cat("820", grades=[10], term="FY", grad_req="Theology")  # Theology 10
cat("830", grades=[11], term="FY", grad_req="Theology")  # Theology 11
cat("849", grades=[12], term="S1", grad_req="Theology")  # Catholic Social Teaching
cat("851", grades=[12], term="S1", grad_req="Theology")  # Spirituality of Vocation
cat("911", grades=[9], term="S1", grad_req="Theology")  # Community Service 9
cat("921", grades=[10], term="S1", grad_req="Theology")  # Community Service 10
cat("931", grades=[11], term="S1", grad_req="Theology")  # Community Service 11
cat("941", grades=[12], term="S1", grad_req="Theology")  # Community Service 12

# WORLD LANGUAGE DEPARTMENT
cat("312", grades=[9,10], term="FY", ncaa=True, grad_req="World Language")  # Italian I
cat("322", grades=[9,10,11], term="FY", ncaa=True, grad_req="World Language", prereqs=["312"])  # Italian II
cat("323", grades=[9,10,11], term="FY", ncaa=True, grad_req="World Language", prereqs=["312"])  # Italian II H
cat("332", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["322"])  # Italian III
cat("333", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["323"])  # Italian III H
cat("343", grades=[11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["333"])  # Italian IV H
cat("352", grades=[11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["333"])  # AP Italian
cat("314", grades=[9,10], term="FY", ncaa=True, grad_req="World Language")  # Latin I
cat("315", grades=[9,10], term="FY", ncaa=True, grad_req="World Language")  # Latin I H
cat("327", grades=[9,10,11], term="FY", ncaa=True, grad_req="World Language", prereqs=["315"])  # Latin II H
cat("339", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["327"])  # Latin III H
cat("353", grades=[11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["339"])  # Latin IV H
cat("359", grades=[11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["339"])  # AP Latin
cat("310", grades=[9,10], term="FY", ncaa=True, grad_req="World Language")  # Spanish I
cat("311", grades=[9,10], term="FY", ncaa=True, grad_req="World Language")  # Spanish I H
cat("320", grades=[9,10,11], term="FY", ncaa=True, grad_req="World Language", prereqs=["310"])  # Spanish II
cat("321", grades=[9,10,11], term="FY", ncaa=True, grad_req="World Language", prereqs=["311"])  # Spanish II H
cat("330", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["320"])  # Spanish III
cat("331", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["321"])  # Spanish III H
cat("334", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language")  # French III
cat("336", grades=[10,11,12], term="FY", ncaa=True, grad_req="World Language")  # German III
cat("340", grades=[11,12], term="FY", ncaa=True, grad_req="World Language")  # Spanish IV
cat("344", grades=[11,12], term="FY", ncaa=True, grad_req="World Language")  # French IV
cat("3440", grades=[11,12], term="FY", ncaa=True, grad_req="World Language")  # French IV (dup)
cat("351", grades=[11,12], term="FY", ncaa=True, grad_req="World Language", prereqs=["331"])  # AP Spanish

# SPECIAL EDUCATION
cat("955", grades=[9,10,11,12], term="FY")  # Academic Support
cat("IDEA-EF", grades=[9,10,11,12], term="FY")  # IDEA - Executive Functioning
cat("IDEA-M", grades=[9,10,11,12], term="FY")  # IDEA - Math
cat("IDEA-R", grades=[9,10,11,12], term="FY")  # IDEA - Reading

# ---- Department mapping (standardize from source) ----
DEPT_MAP = {
    "Special Education": "Special Education",
    "Theater Arts": "Theater Arts",
    "Mathematics": "Mathematics",
    "Music/Art": "Humanities",
    "Social Studies": "Social Studies",
    "Science": "Science",
    "English": "English",
    "Physical Education": "Physical Education",
    "Computer Science": "Computer Science",
    "Language": "World Language",
    "Business": "Business",
    "Theology": "Theology",
    "Engineering": "Engineering",
    "Communication Arts": "Communication Arts",
}

# ---- Determine AP status: from source flag + name pattern ----
def is_ap(course):
    if course["ap_src"]:
        return True
    name = course["name"].upper()
    if name.startswith("AP ") or name.startswith("ADVANCED PLACEMENT"):
        return True
    return False

# ---- Default max enrollment per department ----
DEFAULT_MAX_ENROLL = {
    "Special Education": 15,
    "Communication Arts": 12,
    "Engineering": 20,
    "Theater Arts": 20,
    "Humanities": 25,
}

# ---- Build output ----
wb_out = openpyxl.Workbook()
ws = wb_out.active
ws.title = "Course Profiles"

# Row 1: Headers
for c, header in enumerate(HEADERS, 1):
    cell = ws.cell(1, c, header)
    cell.font = HEADER_FONT
    cell.fill = HEADER_FILL
    cell.border = THIN_BORDER
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

# Row 2: REQUIRED/OPTIONAL
for c, label in enumerate(REQ_OPT, 1):
    cell = ws.cell(2, c, label)
    if label == "REQUIRED":
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL
    else:
        cell.font = OPT_FONT
        cell.fill = OPT_FILL
    cell.border = THIN_BORDER
    cell.alignment = Alignment(horizontal='center', vertical='center')

# Row 3+: Data
row_num = 3
for course in sorted(courses_raw, key=lambda x: (x["dept"], x["code"])):
    code = course["code"]
    name = course["name"]
    dept = DEPT_MAP.get(course["dept"], course["dept"])

    # Credits
    credits = course["credits"]
    if credits is not None:
        credits = float(credits)
    else:
        credits = 2.5

    cat_data = catalog.get(code, {})

    # Prescribed Term
    if cat_data:
        term = cat_data.get("term", "FY")
    else:
        # Default: if credits <= 1.25 then semester, else full year
        if credits <= 1.25:
            term = "S1"
        else:
            term = "FY"

    # Grade Levels
    if cat_data and cat_data.get("grades"):
        grade_levels = ",".join(str(g) for g in sorted(cat_data["grades"]))
    else:
        grade_levels = "9,10,11,12"

    # Sections Needed (from prior year schedule)
    sections = section_counts.get(code, 1)

    # Max Enrollment per Section
    dept_default = DEFAULT_MAX_ENROLL.get(dept, 25)
    if code == "955":
        max_enroll = 15
    elif "IDEA" in code:
        max_enroll = 10
    elif dept == "Communication Arts":
        max_enroll = 12
    else:
        max_enroll = dept_default

    # Singleton
    singleton = "Y" if sections == 1 else "N"

    # AP
    ap = "Y" if is_ap(course) else "N"

    # Graduation Requirement
    grad_req = ""
    if cat_data and cat_data.get("grad_req"):
        grad_req = cat_data["grad_req"]

    # Cohort (LEO II = course 745)
    cohort = ""
    if code == "745":
        cohort = "LEO II"

    # NCAA
    ncaa = "N"
    if cat_data and cat_data.get("ncaa"):
        ncaa = "Y"

    # Prerequisites
    prereqs = ""
    if cat_data and cat_data.get("prereqs"):
        prereqs = ",".join(cat_data["prereqs"])

    # Corequisites
    coreqs = ""
    if cat_data and cat_data.get("coreqs"):
        coreqs = ",".join(cat_data["coreqs"])

    # Community Service courses have 0 credits, no sections
    if "Community Service" in name:
        sections = 1
        max_enroll = 250
        singleton = "Y"

    # Band/Orchestra - full year, special enrollment
    if code in ("206", "209", "211", "212"):
        max_enroll = 40

    row_data = [
        code, name, dept, credits, term, grade_levels,
        sections, max_enroll, singleton, ap,
        grad_req if grad_req else "", cohort if cohort else "", ncaa,
        prereqs if prereqs else "", coreqs if coreqs else ""
    ]

    for c, val in enumerate(row_data, 1):
        cell = ws.cell(row_num, c, val)
        cell.font = DATA_FONT
        cell.border = THIN_BORDER
        if c in (1, 5, 7, 8, 9, 10, 13):
            cell.alignment = Alignment(horizontal='center')

    row_num += 1

# Column widths
col_widths = [12, 45, 22, 10, 15, 18, 15, 22, 10, 6, 22, 12, 8, 25, 20]
for i, w in enumerate(col_widths, 1):
    ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

# Freeze header rows
ws.freeze_panes = "A3"

out_path = "templates/new/Template_7_Course_Profiles.xlsx"
wb_out.save(out_path)
print(f"Saved {row_num - 3} courses to {out_path}")
