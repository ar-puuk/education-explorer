"""CCD topic registry and first-time map bootstrap (wide->long rules for the 2014-15 era)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .canon import alias

RACES = {"AM": "American Indian or Alaska Native", "AS": "Asian", "HI": "Hispanic/Latino",
         "BL": "Black or African American", "WH": "White",
         "HP": "Native Hawaiian or Other Pacific Islander", "TR": "Two or more races"}
SEXES = {"M": "Male", "F": "Female"}
GRADES = {"PK": "Pre-Kindergarten", "KG": "Kindergarten", "UG": "Ungraded", "AE": "Adult Education",
          **{f"{n:02d}": f"Grade {n}" for n in range(1, 14)}}
NOCAT = "No Category Codes"

STAFF_WIDE = {
    "STAFF": "Total Staff (STAFF)", "SCHSUP": "School Administrative Support Staff", "SECTCH": "Secondary Teachers",
    "ELMGUI": "Elementary School Counselors", "KGTCH": "Kindergarten Teachers",
    "LEASUP": "LEA Administrative Support Staff", "PARA": "Paraprofessionals/Instructional Aides",
    "SECGUI": "Secondary School Counselors", "CORSUP": "Instructional Coordinators and Supervisors to the Staff",
    "ELMTCH": "Elementary Teachers", "LIBSUP": "Library/Media Support Staff", "SCHADM": "School administrators",
    "STUSUP": "Student Support Services Staff", "GUI": "Guidance Counselors (GUI)", "LEAADM": "LEA Administrators",
    "LIBSPE": "Librarians/media specialists", "OTHSUP": "All Other Support Staff", "PKTCH": "Pre-kindergarten Teachers",
    "UGTCH": "Ungraded Teachers", "TOTTCH": "Teachers", "TOTGUI": "Guidance Counselors (TOTGUI)",
}


@dataclass(frozen=True)
class Topic:
    name: str                 # output table name
    component: str            # raw file key: <level>_<component>
    kind: str                 # flat | long
    sort: tuple[str, ...]
    value: str | None = None  # long tables: canonical value column
    value_type: str = "INTEGER"
    dims: tuple[str, ...] = ()
    ids: tuple[str, ...] = ()
    years: tuple[int, int] = (2014, 9999)


TOPICS: dict[str, Topic] = {t.name: t for t in [
    Topic("school_directory", "sch_directory", "flat", ("ncessch",)),
    Topic("district_directory", "lea_directory", "flat", ("leaid",)),
    Topic("school_characteristics", "sch_characteristics", "flat", ("ncessch",)),
    Topic("membership", "sch_membership", "long", ("ncessch", "grade", "race", "sex", "total_indicator"),
          value="student_count", dims=("grade", "race", "sex", "total_indicator"), ids=("ncessch", "leaid")),
    Topic("district_membership", "lea_membership", "long", ("leaid", "grade", "race", "sex", "total_indicator"),
          value="student_count", dims=("grade", "race", "sex", "total_indicator"), ids=("leaid",)),
    Topic("lunch", "sch_lunch", "long", ("ncessch", "data_group", "lunch_program", "total_indicator"),
          value="student_count", dims=("data_group", "lunch_program", "total_indicator"), ids=("ncessch", "leaid")),
    Topic("staff", "sch_staff", "long", ("ncessch", "total_indicator"), value="teachers", value_type="DOUBLE",
          dims=("total_indicator",), ids=("ncessch", "leaid")),
    Topic("district_staff", "lea_staff", "long", ("leaid", "staff_category", "total_indicator"),
          value="staff_count", value_type="DOUBLE", dims=("staff_category", "total_indicator"), ids=("leaid",)),
    Topic("district_idea", "lea_idea", "long", ("leaid",), value="idea_count", ids=("leaid",)),
    Topic("district_el", "lea_el", "long", ("leaid",), value="lep_count", ids=("leaid",)),
]}

# long-format (2016+) raw column -> (canonical, type, role)
LONG_RAW = {
    "GRADE": ("grade", "VARCHAR"), "RACE_ETHNICITY": ("race", "VARCHAR"), "SEX": ("sex", "VARCHAR"),
    "TOTAL_INDICATOR": ("total_indicator", "VARCHAR"), "DATA_GROUP": ("data_group", "VARCHAR"),
    "LUNCH_PROGRAM": ("lunch_program", "VARCHAR"), "STAFF": ("staff_category", "VARCHAR"),
    "DMS_FLAG": ("value_flag", "VARCHAR"),
}
LONG_VALUE_RAW = {"STUDENT_COUNT": "student_count", "TEACHERS": "teachers", "STAFF_COUNT": "staff_count",
                  "IDEA_COUNT": "idea_count", "LEP_COUNT": "lep_count"}
DERIVED_YEAR = {"SURVYEAR", "SCHOOL_YEAR"}


def _id_cols(raw_cols: list[str], cols: dict) -> None:
    for c in raw_cols:
        if c in DERIVED_YEAR:
            cols[c] = {"ignore": True, "reason": "replaced by derived year/school_year columns"}
        elif (a := alias(c)) and c not in cols:
            cols[c] = {"name": a[0], "type": a[1]}


def bootstrap(topic: Topic, year: int, raw_cols: list[str]) -> tuple[dict, list[dict]]:
    """Return (columns, unpivot) for a first-time map. Unrecognized columns get a TODO name."""
    cols: dict[str, dict] = {}
    unpivot: list[dict] = []
    _id_cols(raw_cols, cols)
    long_format = any(c in raw_cols for c in LONG_RAW) and any(c in raw_cols for c in LONG_VALUE_RAW)
    if topic.kind == "long" and long_format:
        for c in raw_cols:
            if c in LONG_RAW and not (c == "STAFF" and topic.name != "district_staff"):
                n, t = LONG_RAW[c]
                cols[c] = {"name": n, "type": t}
                if c == "DMS_FLAG":
                    cols[c]["recode"] = "dms_flag"
            elif c in LONG_VALUE_RAW:
                cols[c] = {"name": LONG_VALUE_RAW[c], "type": topic.value_type, "value": True}
    elif topic.kind == "long":
        _wide(topic, raw_cols, cols, unpivot)
    for c in raw_cols:
        if c not in cols:
            cols[c] = {"name": "TODO_" + c.lower(), "type": "VARCHAR", "todo": True}
    return cols, unpivot


def _wide(topic: Topic, raw_cols: list[str], cols: dict, unpivot: list[dict]) -> None:
    def un(src: str, **dims) -> None:
        cols[src] = {"unpivot": True}
        unpivot.append({"source": src, **dims})

    n = topic.name
    if n in ("membership", "district_membership"):
        rg = re.compile(r"^(AM|AS|HI|BL|WH|HP|TR)(PK|KG|\d\d|UG|AE)(M|F)$")
        for c in raw_cols:
            if m := rg.match(c):
                un(c, grade=GRADES[m.group(2)], race=RACES[m.group(1)], sex=SEXES[m.group(3)],
                   total_indicator="Category Set A - By Race/Ethnicity; Sex; Grade")
            elif (m := re.match(r"^(PK|KG|G\d\d|UG|AE)$", c)):
                g = m.group(1)[1:] if m.group(1).startswith("G") else m.group(1)
                un(c, grade=GRADES[g], race=NOCAT, sex=NOCAT, total_indicator="Subtotal 4 - By Grade")
            elif c in ("TOTAL", "MEMBER"):
                un(c, grade=NOCAT, race=NOCAT, sex=NOCAT,
                   total_indicator="Education Unit Total" if c == "MEMBER"
                   else "Derived - Education Unit Total minus Adult Education Count")
            elif (m := re.match(r"^(AM|AS|HI|BL|WH|HP|TR)$", c)):
                un(c, grade=NOCAT, race=RACES[c], sex=NOCAT, total_indicator="Subtotal - By Race/Ethnicity (all grades)")
            elif (m := re.match(r"^(AM|AS|HI|BL|WH|HP|TR)ALL?([MF])$", c)):
                un(c, grade=NOCAT, race=RACES[m.group(1)], sex=SEXES[m.group(2)],
                   total_indicator="Derived - Subtotal by Race/Ethnicity and Sex minus Adult Education Count")
            elif re.match(r"^(ISMEMPUP|IAMEMPUP|ISPELM|ISPFEMALE|ISPWHITE)$", c):
                cols[c] = {"ignore": True, "reason": "NCES derived indicator/percentage (not a count); recomputable from counts"}
    elif n == "lunch":
        for c, lp, ti in (("FRELCH", "Free lunch qualified", "Category Set A"),
                          ("REDLCH", "Reduced-price lunch qualified", "Category Set A"),
                          ("TOTFRL", NOCAT, "Education Unit Total")):
            if c in raw_cols:
                un(c, data_group="Free and Reduced-price Lunch Table", lunch_program=lp, total_indicator=ti)
        if "ISFLE" in raw_cols:
            cols["ISFLE"] = {"ignore": True, "reason": "NCES imputation indicator for the lunch counts"}
    elif n == "staff":
        if "FTE" in raw_cols:
            un("FTE", total_indicator="Education Unit Total")
        for c in ("ISFTEPUP",):
            if c in raw_cols:
                cols[c] = {"ignore": True, "reason": "NCES imputation indicator for FTE"}
    elif n == "district_staff":
        for c, label in STAFF_WIDE.items():
            if c in raw_cols:
                un(c, staff_category=label, total_indicator="Category Set A")
        for c in raw_cols:
            if c.startswith("IA") and c not in cols:
                cols[c] = {"ignore": True, "reason": "NCES imputation indicator for the staff counts"}
    elif n == "district_idea":
        if "SPECED" in raw_cols:
            un("SPECED")
        if "IASPECED" in raw_cols:
            cols["IASPECED"] = {"ignore": True, "reason": "NCES imputation indicator"}
    elif n == "district_el":
        if "ELL" in raw_cols:
            un("ELL")
        if "IAELL" in raw_cols:
            cols["IAELL"] = {"ignore": True, "reason": "NCES imputation indicator"}
