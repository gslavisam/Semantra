"""
HRDH (HR Data Hub) → Knowledge Overlay CSV parser

Parses metadata_dict/HRDH_Table_Columns.xlsx  (sheet: result_250926)
which is a SQL Server sys.columns export from the Workday HR Data Hub
integration database.

Outputs:
    metadata_dict/hrdh_knowledge_overlay.csv   - importable via Admin tab
                                                  or auto-loaded at startup

Usage:
    python parse_hrdh_columns.py [--dry-run]
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import openpyxl

# ---------------------------------------------------------------------------
# Table prefixes to ignore (technical / backup / staging tables)
# ---------------------------------------------------------------------------
SKIP_TABLE_SUFFIX = (
    "_bk_ts_", "_fh_", "_STG_", "_BAK_", "_OLD",
    "_CHANGES_MDS", "_MDS", "_CLEANUP",
    "CR_MDI_", "CR_Preformance_",
)

# ---------------------------------------------------------------------------
# Column prefixes that are technical metadata — skip for knowledge
# ---------------------------------------------------------------------------
TECHNICAL_COL_PREFIXES = ("T_", "ID")
SKIP_COL_PATTERNS = ("CUSTOM_ATTRIBUTE", "CUSTOM_DATE", "CUSTOM_NUMBER")

# ---------------------------------------------------------------------------
# MANUAL canonical concept hints:  column_name → canonical_concept_id
# ---------------------------------------------------------------------------
MANUAL_HINTS: dict[str, str] = {
    # ── Employee identity ──────────────────────────────────────────────────
    "EM_EMPLOYEE_NK":              "employee.id",
    "EM_WORKDAY_ID":               "employee.id",
    "EM_FIRST_NAME":               "employee.name",
    "EM_LAST_NAME":                "employee.name",
    "EM_MIDDLE_NAME":              "employee.name",
    "EM_PREFERRED_FIRST_NAME":     "employee.name",
    "EM_PREFERRED_LAST_NAME":      "employee.name",
    "EM_PRE_TITLE_CODE":           "employee.name",
    "EM_POST_TITLE_CODE":          "employee.name",
    # ── Employee contact ───────────────────────────────────────────────────
    "EM_EMAIL_WORK1":              "employee.email",
    "EM_EMAIL_WORK2":              "employee.email",
    "EM_EMAIL_WORK3":              "employee.email",
    "EM_EMAIL_PERSONAL1":          "employee.email",
    "EM_EMAIL_PERSONAL2":          "employee.email",
    "EM_EMAIL_PERSONAL3":          "employee.email",
    "EM_MOBILE_WORK_NUMBER":       "employee.phone",
    "EM_MOBILE_PERSONAL_NUMBER":   "employee.phone",
    "EM_PHONE_WORK_NUMBER":        "employee.phone",
    "EM_PHONE_PERSONAL_NUMBER":    "employee.phone",
    # ── Employee HR dates ─────────────────────────────────────────────────
    "EM_ORIGINAL_HIRE_DATE":       "employee.hire_date",
    "EM_REHIRE_DATE":              "employee.hire_date",
    "EM_TERMINATION_DATE":         "employee.termination_date",
    "EM_LAST_DAY_OF_WORK":         "employee.termination_date",
    "EM_END_EMPLOYMENT_DATE":      "employee.termination_date",
    "EM_BIRTH_DATE":               "employee.birth_date",
    "EM_COMPANY_SERVICE_DATE":     "employee.service_date",
    "EM_MAGNA_SERVICE_DATE":       "employee.service_date",
    "EM_SENIORITY_DATE":           "employee.service_date",
    "EM_WORKER_DIVISION_ENTRY_DATE": "employee.service_date",
    "EM_CONTRACT_EXP_DATE":        "employee.contract_end_date",
    # ── Employee HR attributes ────────────────────────────────────────────
    "EM_GENDER":                   "employee.gender",
    "EM_NATIONALITY":              "employee.nationality",
    "EM_MARITAL_STATUS":           "employee.marital_status",
    "EM_EMPLOYMENT_STATUS":        "employee.employment_status",
    "EM_EMPLOYEE_TYPE":            "employee.employee_type",
    "EM_WORKER_TYPE":              "employee.employee_type",
    "EM_FTE":                      "employee.fte",
    "EM_FULL_PARTTIME_INDICATOR":  "employee.fte",
    "EM_SCHEDULED_WEEKLY_HOURS":   "employee.fte",
    "EM_REMOTE_WORKER":            "employee.employment_status",
    "EM_TERMINATION_REASON":       "employee.termination_reason",
    "EM_PAY_GROUP":                "employee.pay_group",
    "EM_PAY_RATE_TYPE":            "employee.pay_group",
    "EM_CITIZENSHIP_PRIMARY":      "employee.nationality",
    "EM_CITIZENSHIP2":             "employee.nationality",
    "EM_CITIZENSHIP3":             "employee.nationality",
    "EM_CITIZENSHIP4":             "employee.nationality",
    # ── Employee address ──────────────────────────────────────────────────
    "EM_FIRST_ADDRESS_LINE1":      "address.line1",
    "EM_FIRST_ADDRESS_LINE2":      "address.line2",
    "EM_SECOND_ADDRESS_LINE1":     "address.line1",
    "EM_SECOND_ADDRESS_LINE2":     "address.line2",
    "EM_FIRST_ADDRESS_CITY":       "address.city",
    "EM_SECOND_ADDRESS_CITY":      "address.city",
    "EM_FIRST_ADDRESS_COUNTRY":    "address.country",
    "EM_SECOND_ADDRESS_COUNTRY":   "address.country",
    "EM_FIRST_ADDRESS_POSTCODE":   "address.postal_code",
    "EM_SECOND_ADDRESS_POSTCODE":  "address.postal_code",
    "EM_FIRST_ADDRESS_STATE":      "address.region",
    "EM_SECOND_ADDRESS_STATE":     "address.region",
    # ── Position ──────────────────────────────────────────────────────────
    "PO_POSITION_NK":              "position.id",
    "PO_BUSINESS_TITLE":           "position.title",
    "PO_START_DATE":               "position.start_date",
    "PO_END_DATE":                 "position.end_date",
    "PO_DEPARTMENT_CODE":          "department.code",
    "PO_LEGAL_COMPANY":            "company.name",
    "PO_SHOP_FLOOR_OFFICE_STAFF":  "position.title",
    # ── Job ───────────────────────────────────────────────────────────────
    "JO_JOB_NK":                   "job.id",
    "JO_JOB_TITLE":                "job.title",
    "JO_CAREER_STREAM":            "job.career_level",
    "JO_CATEGORY":                 "job.category",
    "JO_FUNCTION":                 "job.function",
    "JO_FUNCTION_REF_ID":          "job.function",
    "JO_SUB_FUNCTION":             "job.function",
    "JO_SUB_FUNCTION_REF_ID":      "job.function",
    "JO_TRAINING_LEVEL":           "job.career_level",
    # ── Department / Supervisory Org ──────────────────────────────────────
    "DP_DEPARTMENT_NK":            "department.id",
    "DP_PARENT_DEPARTMENT":        "department.id",
    "DP_NAME":                     "department.name",
    "DP_CODE":                     "department.code",
    "DP_MANAGER_ID":               "department.manager_id",
    "DP_MANAGER_POSITION_ID":      "position.id",
    # ── Cost Center ───────────────────────────────────────────────────────
    "CC_NK":                       "cost_center.id",
    "CC_CODE":                     "cost_center.code",
    "CC_NAME":                     "cost_center.name",
    "CC_COST_CENTER_MANAGER":      "cost_center.manager_id",
    # ── Location ──────────────────────────────────────────────────────────
    "LO_LOCATION_NK":              "location.id",
    "LO_NAME":                     "location.name",
    "LO_CITY":                     "address.city",
    "LO_POST_ZIP":                 "address.postal_code",
    "LO_COUNTRY":                  "address.country",
    "LO_ADDRESS_LINE1":            "address.line1",
    # ── Company / Legal Entity ────────────────────────────────────────────
    "CO_COMPANY_NK":               "company.id",
    "CO_COMPANY_NAME":             "company.name",
    "CO_LEGAL_NAME":               "company.name",
    # ── Generic / FCT table column names ──────────────────────────────────
    "CostCenter":                  "cost_center.id",
    "CostCenterCode":              "cost_center.code",
    "CostCenterName":              "cost_center.name",
    "JobTitle":                    "job.title",
    "JobReqId":                    "job.id",
    "CountryCode":                 "address.country",
    "CountryName":                 "address.country",
    "CityName":                    "address.city",
    "PostalCode":                  "address.postal_code",
    "ID_EMPLOYEE":                 "employee.id",
    "ID_POSITION":                 "position.id",
    "ID_COMPANY":                  "company.id",
    "ID_JOB":                      "job.id",
    "ID_COST_CENTER":              "cost_center.id",
    "ID_DEPARTMENT":               "department.id",
    "ID_LOCATION":                 "location.id",
    "EMPLOYEE_ID":                 "employee.id",
    "EMPLOYEE_NK":                 "employee.id",
    "POSITION_ID":                 "position.id",
    "POSITION_NK":                 "position.id",
    "COMPANY_ID":                  "company.id",
    "DEPARTMENT_ID":               "department.id",
    "LOCATION_ID":                 "location.id",
    "LOCATION_NK":                 "location.id",
    "COST_CENTER_ID":              "cost_center.id",
    "COST_CENTER_CODE":            "cost_center.code",
    "COST_CENTER_NAME":            "cost_center.name",
    "MANAGER_ID":                  "employee.manager_id",
    "MANAGER_NK":                  "employee.manager_id",
    # ── Compensation ──────────────────────────────────────────────────────
    "COMP_GRADE":                  "compensation.grade",
    "COMP_GRADE_NK":               "compensation.grade",
    "CGR_COMP_GRADE_NK":           "compensation.grade",
    "COMP_STEP":                   "compensation.grade",
    "COMP_PLAN":                   "compensation.plan",
    "ID_COMP_GRADE":               "compensation.grade",
    "ID_COMP_GRADE_PROFILE":       "compensation.grade",
    "ID_COMP_STEP":                "compensation.grade",
    "ID_COMP_PLAN":                "compensation.plan",
    # ── Pay group ─────────────────────────────────────────────────────────
    "PG_PAYGROUP_NK":              "employee.pay_group",
    "PG_NAME":                     "employee.pay_group",
    # ── Worker identifiers ────────────────────────────────────────────────
    "WI_IDENTIFIER_ID":            "employee.national_id",
    "WI_IDENTIFIER_NATIONAL_ID_ISSUED_BY": "employee.national_id",
    "WI_IDENTIFIER_COUNTRY_CODE":  "address.country",
}

# ---------------------------------------------------------------------------
# New canonical entries to add to the glossary
# format: (concept_id, entity, attribute, display_name, description, data_type, aliases_csv)
# ---------------------------------------------------------------------------
NEW_CANONICAL_ENTRIES = [
    ("employee.gender",            "employee", "gender",
     "Gender",                     "Legal or self-identified gender of the employee",
     "string",
     "gender, worker gender, EM_GENDER"),
    ("employee.nationality",       "employee", "nationality",
     "Nationality",                "Primary nationality or citizenship country of the employee",
     "string",
     "nationality, citizenship, EM_NATIONALITY, EM_CITIZENSHIP_PRIMARY"),
    ("employee.marital_status",    "employee", "marital_status",
     "Marital Status",             "Marital or civil partnership status of the employee",
     "string",
     "marital status, civil status, EM_MARITAL_STATUS"),
    ("employee.employment_status", "employee", "employment_status",
     "Employment Status",          "Current active status of the worker: Active, Terminated, On Leave, etc.",
     "string",
     "employment status, worker status, active status, EM_EMPLOYMENT_STATUS"),
    ("employee.employee_type",     "employee", "employee_type",
     "Employee Type",              "Type of worker engagement: Regular, Fixed Term, Intern, Apprentice, Contingent, etc.",
     "string",
     "employee type, worker type, employment type, EM_EMPLOYEE_TYPE, EM_WORKER_TYPE"),
    ("employee.fte",               "employee", "fte",
     "FTE",                        "Full Time Equivalent ratio for the worker's primary position",
     "decimal",
     "fte, full time equivalent, EM_FTE, EM_FULL_PARTTIME_INDICATOR, EM_SCHEDULED_WEEKLY_HOURS"),
    ("employee.service_date",      "employee", "service_date",
     "Service Date",               "Company or division service date, taking into account tenure and breaks",
     "date",
     "service date, seniority date, company service date, division entry date, EM_COMPANY_SERVICE_DATE, EM_SENIORITY_DATE"),
    ("employee.contract_end_date", "employee", "contract_end_date",
     "Contract End Date",          "Expiration date of the fixed-term or contingent worker contract",
     "date",
     "contract end date, contract expiry, EM_CONTRACT_EXP_DATE"),
    ("employee.termination_reason","employee", "termination_reason",
     "Termination Reason",         "Reason code or description for the end of employment",
     "string",
     "termination reason, separation reason, EM_TERMINATION_REASON"),
    ("employee.pay_group",         "employee", "pay_group",
     "Pay Group",                  "Payroll pay group reference for the worker",
     "string",
     "pay group, payroll group, EM_PAY_GROUP, EM_PAY_RATE_TYPE"),
    ("job.id",                     "job", "id",
     "Job Profile ID",             "Unique identifier for the job profile",
     "string",
     "job id, job profile id, job code, job profile code, JO_JOB_NK"),
    ("job.title",                  "job", "title",
     "Job Title",                  "Official job title / job profile name",
     "string",
     "job title, job profile name, JO_JOB_TITLE"),
    ("job.category",               "job", "category",
     "Job Category",               "Job classification category (e.g. Sales, Engineering, Operations)",
     "string",
     "job category, job classification, JO_CATEGORY"),
    ("job.function",               "job", "function",
     "Job Function",               "Job family or functional area grouping for the job profile",
     "string",
     "job function, job family, job family group, JO_FUNCTION, JO_SUB_FUNCTION"),
    ("job.career_level",           "job", "career_level",
     "Career Level",               "Management or career stream level for the job profile",
     "string",
     "career level, management level, career stream, JO_CAREER_STREAM, JO_TRAINING_LEVEL"),
    ("position.id",                "position", "id",
     "Position ID",                "Unique identifier for the organizational position",
     "string",
     "position id, position reference id, PO_POSITION_NK, position number"),
    ("position.title",             "position", "title",
     "Position Title",             "Business title assigned to the organizational position",
     "string",
     "position title, business title, PO_BUSINESS_TITLE"),
    ("position.start_date",        "position", "start_date",
     "Position Start Date",        "Date the organizational position became available",
     "date",
     "position start date, position availability date, PO_START_DATE"),
    ("position.end_date",          "position", "end_date",
     "Position End Date",          "Date the organizational position was closed or ended",
     "date",
     "position end date, position close date, PO_END_DATE"),
    ("department.id",              "department", "id",
     "Department ID",              "Unique reference identifier for the organizational department/supervisory org",
     "string",
     "department id, supervisory org id, department reference id, DP_DEPARTMENT_NK"),
    ("department.name",            "department", "name",
     "Department Name",            "Name of the organizational department or supervisory organization",
     "string",
     "department name, org name, supervisory org name, DP_NAME"),
    ("department.code",            "department", "code",
     "Department Code",            "Short code or organization ID for the department",
     "string",
     "department code, org code, org id, DP_CODE, PO_DEPARTMENT_CODE"),
    ("department.manager_id",      "department", "manager_id",
     "Department Manager ID",      "Employee ID of the department or supervisory org manager",
     "string",
     "department manager id, org manager id, DP_MANAGER_ID"),
    ("location.id",                "location", "id",
     "Location ID",                "Unique identifier for the physical work location",
     "string",
     "location id, site id, LO_LOCATION_NK, location code"),
    ("location.name",              "location", "name",
     "Location Name",              "Human-readable name of the work location or facility",
     "string",
     "location name, site name, facility name, LO_NAME"),
    ("cost_center.code",           "cost_center", "code",
     "Cost Center Code",           "Short numeric or alphanumeric code for the cost center",
     "string",
     "cost center code, cost center number, CC_CODE, kostenstelle"),
    ("cost_center.name",           "cost_center", "name",
     "Cost Center Name",           "Descriptive name of the cost center organizational unit",
     "string",
     "cost center name, CC_NAME, cost centre name"),
    ("cost_center.manager_id",     "cost_center", "manager_id",
     "Cost Center Manager ID",     "Employee ID of the manager responsible for the cost center",
     "string",
     "cost center manager, cc manager id, CC_COST_CENTER_MANAGER"),
    ("compensation.plan",          "compensation", "plan",
     "Compensation Plan",          "Name or ID of the compensation plan assigned to the worker",
     "string",
     "compensation plan, pay plan, salary plan, COMP_PLAN"),
    ("address.line1",              "address", "line1",
     "Address Line 1",             "First line of a street address",
     "string",
     "address line 1, street address, address1, EM_FIRST_ADDRESS_LINE1, LO_ADDRESS_LINE1"),
    ("address.line2",              "address", "line2",
     "Address Line 2",             "Second line of a street address (apartment, suite, floor)",
     "string",
     "address line 2, address2, EM_FIRST_ADDRESS_LINE2"),
    ("address.region",             "address", "region",
     "State/Region",               "State, province, or region code of the address",
     "string",
     "state, region, province, state code, address state, EM_FIRST_ADDRESS_STATE"),
]

OVERLAY_HEADERS = [
    "entry_type", "canonical_term", "canonical_concept_id",
    "alias", "domain", "source_system", "note",
]


def _col_skip(col: str) -> bool:
    if col in ("ID",):
        return True
    if col.startswith("T_"):
        return True
    if any(p in col for p in SKIP_COL_PATTERNS):
        return True
    return False


def _table_skip(table: str) -> bool:
    return any(s in table for s in SKIP_TABLE_SUFFIX)


def parse_sheet(xlsx_path: Path, sheet: str) -> list[dict]:
    """Return list of {table, col, type_name, description, sample} dicts."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))

    # Build (table, col) → {description, sample}
    prop_map: dict[tuple, dict] = defaultdict(dict)
    for r in rows[1:]:
        table, col = r[1] or "", r[4] or ""
        prop = str(r[13] or "").strip()
        val = str(r[14] or "").strip()
        if col and prop in ("Business description", "Sample value") and val not in ("NULL", ""):
            prop_map[(table, col)][prop] = val

    # Build full column records (one per unique table+col)
    seen: set[tuple] = set()
    records: list[dict] = []
    for r in rows[1:]:
        table = r[1] or ""
        col = r[4] or ""
        type_name = r[6] or ""
        key = (table, col)
        if key in seen or not table or not col:
            continue
        seen.add(key)
        if _table_skip(table) or _col_skip(col):
            continue
        info = prop_map.get(key, {})
        records.append({
            "table": table,
            "col": col,
            "type_name": type_name,
            "description": info.get("Business description", ""),
            "sample": info.get("Sample value", ""),
        })
    return records


def resolve_canonical(col: str, description: str) -> str | None:
    """Resolve a column name to a canonical concept ID."""
    # Manual hint (exact match first)
    if col in MANUAL_HINTS:
        return MANUAL_HINTS[col]

    # Generic keyword match on description
    d = description.lower()
    rules = [
        (["employee id", "worker id", "natural key", "personnel number"], "employee.id"),
        (["first name", "given name"], "employee.name"),
        (["last name", "family name", "surname"], "employee.name"),
        (["work email", "personal email", "email address"], "employee.email"),
        (["work phone", "mobile", "phone number", "landline"], "employee.phone"),
        (["birth date", "date of birth"], "employee.birth_date"),
        (["hire date", "employment start"], "employee.hire_date"),
        (["termination date", "separation date"], "employee.termination_date"),
        (["termination reason"], "employee.termination_reason"),
        (["employment status", "active status"], "employee.employment_status"),
        (["employee type", "worker type"], "employee.employee_type"),
        (["full time equivalent", "fte"], "employee.fte"),
        (["seniority date", "service date", "division entry date"], "employee.service_date"),
        (["contract end", "contract expir"], "employee.contract_end_date"),
        (["pay group"], "employee.pay_group"),
        (["gender"], "employee.gender"),
        (["nationality", "citizen"], "employee.nationality"),
        (["marital status"], "employee.marital_status"),
        (["national id", "social security"], "employee.national_id"),
        (["job title", "job profile name"], "job.title"),
        (["job profile id", "job code"], "job.id"),
        (["job category", "job classification"], "job.category"),
        (["job family", "job function"], "job.function"),
        (["career stream", "management level", "training level"], "job.career_level"),
        (["business title", "position title"], "position.title"),
        (["position id", "position reference"], "position.id"),
        (["department name", "org name", "organization name"], "department.name"),
        (["department id", "supervisory org"], "department.id"),
        (["department code", "org code", "organization id"], "department.code"),
        (["department manager", "org manager"], "department.manager_id"),
        (["cost center id", "cost center reference"], "cost_center.id"),
        (["cost center code", "cost center number"], "cost_center.code"),
        (["cost center name"], "cost_center.name"),
        (["location id", "site id"], "location.id"),
        (["location name", "site name"], "location.name"),
        (["city"], "address.city"),
        (["postal code", "zip code", "postcode", "post zip"], "address.postal_code"),
        (["country"], "address.country"),
        (["address line 1", "street name"], "address.line1"),
        (["address line 2"], "address.line2"),
        (["state iso", "state code", "province"], "address.region"),
        (["company name", "legal name"], "company.name"),
        (["company id", "legal entity"], "company.id"),
        (["compensation grade"], "compensation.grade"),
        (["base salary", "base pay", "annual salary"], "compensation.base_salary"),
        (["compensation plan", "pay plan"], "compensation.plan"),
        (["currency"], "invoice.currency"),
    ]
    for keywords, cid in rules:
        if any(kw in d for kw in keywords):
            return cid
    return None


def extend_canonical_glossary(glossary_path: Path) -> int:
    existing: set[str] = set()
    if glossary_path.exists():
        with glossary_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                existing.add(row["concept_id"])
    new_entries = [e for e in NEW_CANONICAL_ENTRIES if e[0] not in existing]
    if not new_entries:
        return 0
    with glossary_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for entry in new_entries:
            writer.writerow(entry)
    return len(new_entries)


def generate_overlay_csv(records: list[dict], glossary_path: Path, out_path: Path) -> int:
    id_to_display: dict[str, str] = {}
    if glossary_path.exists():
        with glossary_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                id_to_display[row["concept_id"]] = row["display_name"]

    seen: set[tuple] = set()
    rows_out: list[dict] = []

    for rec in records:
        col = rec["col"]
        desc = rec["description"]
        cid = resolve_canonical(col, desc)
        if cid is None:
            continue
        # Normalize alias: strip table prefix (EM_, PO_, etc.) and lowercase-underscore
        alias_raw = col  # keep original case for overlay so service normalizes it
        key = (cid, alias_raw.lower())
        if key in seen:
            continue
        seen.add(key)
        display = id_to_display.get(cid, cid)
        rows_out.append({
            "entry_type":           "concept_alias",
            "canonical_term":       display,
            "canonical_concept_id": cid,
            "alias":                alias_raw,
            "domain":               "Human Capital Management",
            "source_system":        "Workday_HRDH",
            "note":                 desc[:120] if desc else f"HRDH column: {col}",
        })

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OVERLAY_HEADERS)
        writer.writeheader()
        writer.writerows(rows_out)

    return len(rows_out)


def main() -> None:
    import argparse
    from collections import Counter

    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", default="metadata_dict/HRDH_Table_Columns.xlsx")
    p.add_argument("--sheet", default="result_250926")
    p.add_argument("--out", default="metadata_dict/hrdh_knowledge_overlay.csv")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    xlsx_path     = Path(args.xlsx)
    out_path      = Path(args.out)
    glossary_path = Path("metadata_dict/canonical_glossary.csv")

    print(f"Parsing {xlsx_path.name} / sheet={args.sheet}...")
    records = parse_sheet(xlsx_path, args.sheet)
    print(f"  Total columns (after skip): {len(records)}")

    mapped   = [(r, resolve_canonical(r["col"], r["description"])) for r in records]
    with_cid = [(r, cid) for r, cid in mapped if cid]
    print(f"  Columns with canonical match: {len(with_cid)}")
    print(f"  Columns without match:        {len(records) - len(with_cid)}")
    print()

    # Stats per concept
    ctr = Counter(cid for _, cid in with_cid)
    print("Top canonical concepts:")
    for cid, cnt in ctr.most_common(20):
        print(f"  {cid:45} {cnt:>4} columns")

    print()
    print("Unmapped columns (sample 20):")
    unmapped_sample = [(r["table"], r["col"], r["description"]) for r, cid in mapped if cid is None][:20]
    for tbl, col, desc in unmapped_sample:
        print(f"  {col:50} {desc[:60]}")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    added = extend_canonical_glossary(glossary_path)
    if added:
        print(f"\n+ Added {added} new canonical concepts to canonical_glossary.csv")
        for entry in NEW_CANONICAL_ENTRIES:
            print(f"    {entry[0]}")
    else:
        print("\n  Canonical glossary already up-to-date.")

    n = generate_overlay_csv(records, glossary_path, out_path)
    print(f"\n+ Wrote {n} overlay rows -> {out_path}")
    print(f"\nNext: Admin tab -> Knowledge Overlay -> upload {out_path.name}")
    print("      OR rely on auto-load (knowledge service will pick it up at startup)")


if __name__ == "__main__":
    main()
