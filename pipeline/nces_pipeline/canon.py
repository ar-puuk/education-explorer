"""Canonical column names for CCD sources, used only to *bootstrap* per-year YAML maps.

The committed YAML maps are the source of truth at build time; this module just
saves typing when a new year or topic is added (`build --scaffold-map` copies the
previous year's map; `bootstrap` uses these aliases for first-time creation).
"""
from __future__ import annotations

import re

# raw column (upper case) -> (canonical name, type)
ALIASES: dict[str, tuple[str, str]] = {
    "FIPST": ("fipst", "VARCHAR"),
    "STABR": ("state_abbrev", "VARCHAR"),
    "ST": ("state_abbrev", "VARCHAR"),
    "STATENAME": ("state_name", "VARCHAR"),
    "SEANAME": ("sea_name", "VARCHAR"),
    "STATE_AGENCY_NO": ("state_agency_no", "VARCHAR"),
    "UNION": ("union_code", "VARCHAR"),
    "LEAID": ("leaid", "VARCHAR"),
    "ST_LEAID": ("st_leaid", "VARCHAR"),
    "SCHID": ("schid", "VARCHAR"),
    "ST_SCHID": ("st_schid", "VARCHAR"),
    "NCESSCH": ("ncessch", "VARCHAR"),
    "SCH_NAME": ("school_name", "VARCHAR"),
    "LEA_NAME": ("lea_name", "VARCHAR"),
    "MSTREET1": ("mail_street1", "VARCHAR"), "MSTREET2": ("mail_street2", "VARCHAR"),
    "MSTREET3": ("mail_street3", "VARCHAR"), "MCITY": ("mail_city", "VARCHAR"),
    "MSTATE": ("mail_state", "VARCHAR"), "MZIP": ("mail_zip", "VARCHAR"), "MZIP4": ("mail_zip4", "VARCHAR"),
    "LSTREET1": ("street1", "VARCHAR"), "LSTREET2": ("street2", "VARCHAR"),
    "LSTREET3": ("street3", "VARCHAR"), "LCITY": ("city", "VARCHAR"),
    "LSTATE": ("state", "VARCHAR"), "LZIP": ("zip", "VARCHAR"), "LZIP4": ("zip4", "VARCHAR"),
    "PHONE": ("phone", "VARCHAR"),
    "WEBSITE": ("website", "VARCHAR"),
    "OUT_OF_STATE_FLAG": ("out_of_state_flag", "VARCHAR"),
    "SCH_TYPE_TEXT": ("school_type", "VARCHAR"),
    "SCH_TYPE": ("school_type_code", "VARCHAR"),
    "LEA_TYPE_TEXT": ("lea_type", "VARCHAR"),
    "LEA_TYPE": ("lea_type_code", "VARCHAR"),
    "RECON_STATUS": ("recon_status", "VARCHAR"),
    "GSLO": ("grade_low", "VARCHAR"),
    "GSHI": ("grade_high", "VARCHAR"),
    "LEVEL": ("level", "VARCHAR"),
    "VIRTUAL": ("virtual_code", "VARCHAR"),
    "VIRTUAL_TEXT": ("virtual", "VARCHAR"),
    "BIES": ("bies", "VARCHAR"),
    "BIEA": ("biea", "VARCHAR"),
    "SY_STATUS_TEXT": ("status", "VARCHAR"),
    "SY_STATUS": ("status_code", "VARCHAR"),
    "UPDATED_STATUS_TEXT": ("updated_status", "VARCHAR"),
    "UPDATED_STATUS": ("updated_status_code", "VARCHAR"),
    "EFFECTIVE_DATE": ("effective_date", "VARCHAR"),
    "CHARTER_TEXT": ("charter", "VARCHAR"),
    "CHARTER_LEA_TEXT": ("charter_lea", "VARCHAR"),
    "CHARTER_LEA": ("charter_lea_code", "VARCHAR"),
    "AGCHRT": ("charter_lea_code", "VARCHAR"),
    "SCH": ("operational_schools", "VARCHAR"),
    "OPERATIONAL_SCHOOLS": ("operational_schools", "VARCHAR"),
    "CHARTAUTH1": ("charter_auth1_id", "VARCHAR"), "CHARTAUTHN1": ("charter_auth1_name", "VARCHAR"),
    "CHARTAUTH2": ("charter_auth2_id", "VARCHAR"), "CHARTAUTHN2": ("charter_auth2_name", "VARCHAR"),
    "NOGRADES": ("no_grades", "VARCHAR"),
    "IGOFFERED": ("ig_offered", "VARCHAR"),
    # characteristics
    "TITLEI_TEXT": ("title_i_status", "VARCHAR"),
    "TITLEI_STATUS": ("title_i_status_code", "VARCHAR"),
    "TITLEI_STATUS_TEXT": ("title_i_status", "VARCHAR"),
    "TITLEI": ("title_i_flag", "VARCHAR"),
    "STITLEI": ("school_wide_title_i_flag", "VARCHAR"),
    "SHARED_TIME": ("shared_time", "VARCHAR"),
    "MAGNET_TEXT": ("magnet", "VARCHAR"),
    "NSLPSTATUS_TEXT": ("nslp_status", "VARCHAR"),
    "NSLPSTATUS_CODE": ("nslp_status_code", "VARCHAR"),
    "NSLP_STATUS": ("nslp_status_code", "VARCHAR"),
    "NSLP_STATUS_TEXT": ("nslp_status", "VARCHAR"),
}

_GRADE_OFFERED = re.compile(r"^(?:G_)?(PK|KG|UG|AE|\d{1,2})_?OFFERED$|^G_(PK|KG|UG|AE|\d{1,2})_OFFERED$")


def alias(col: str) -> tuple[str, str] | None:
    c = col.upper()
    if c in ALIASES:
        return ALIASES[c]
    m = re.match(r"^G_(PK|KG|UG|AE|\d{1,2})_OFFERED$", c) or re.match(r"^(PK|KG|UG|AE|G?\d{1,2})OFFERED$", c)
    if m:
        g = m.group(1).lstrip("G").lstrip("0") if m.group(1)[0] == "G" else m.group(1)
        g = g if g else "0"
        return (f"offers_{g.lower()}", "VARCHAR")
    return None
