"""
Workday HR XSD → Knowledge Overlay CSV + WD Excel updater

Usage:
    python support/vendor_ingest/parse_workday_xsd.py [--xsd metadata_dict/hr_wd.xml] [--dry-run]

Outputs:
    metadata_dict/wd_hr_knowledge_overlay.csv   - importable via Admin tab
    (also prints summary stats)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# lxml with recovery (handles unescaped < in WD docs)
# ---------------------------------------------------------------------------
try:
    from lxml import etree
except ImportError:
    sys.exit("Run:  pip install lxml")

XSD_NS = "http://www.w3.org/2001/XMLSchema"
WD_NS  = "urn:com.workday/bsvc"

# ---------------------------------------------------------------------------
# Which complexType suffixes are real data containers (skip refs/requests)
# ---------------------------------------------------------------------------
SKIP_SUFFIX = (
    "RequestType", "ResponseType", "CriteriaType", "FilterType",
    "ParametersType", "RequestReferencesType", "ObjectType",
    "ReferenceType", "InstanceType", "FaultType",
)

# Manually curated entity → functional area mapping
ENTITY_LABELS: dict[str, tuple[str, str]] = {
    "Worker":               ("Worker",               "Human Capital Management"),
    "Employee":             ("Employee",              "Human Capital Management"),
    "ContingentWorker":     ("Contingent Worker",     "Human Capital Management"),
    "Personal":             ("Personal Information",  "Human Capital Management"),
    "ContactInformation":   ("Contact Information",   "Human Capital Management"),
    "Address":              ("Address",               "Human Capital Management"),
    "Phone":                ("Phone",                 "Human Capital Management"),
    "EmailAddress":         ("Email Address",         "Human Capital Management"),
    "WebAddress":           ("Web Address",           "Human Capital Management"),
    "Name":                 ("Name",                  "Human Capital Management"),
    "Organization":         ("Organization",          "Organizations & Roles"),
    "Supervisory":          ("Supervisory Org",       "Organizations & Roles"),
    "CostCenter":           ("Cost Center",           "Financial Management"),
    "Company":              ("Company",               "Financial Management"),
    "Position":             ("Position",              "Staffing"),
    "Job":                  ("Job",                   "Staffing"),
    "Compensation":         ("Compensation",          "Compensation"),
    "Payroll":              ("Payroll",               "Payroll"),
    "Location":             ("Location",              "Locations"),
    "TimeOff":              ("Time Off",              "Time & Attendance"),
    "Leave":                ("Leave",                 "Time & Attendance"),
    "Absence":              ("Absence",               "Time & Attendance"),
    "Benefit":              ("Benefits",              "Benefits"),
    "Dependent":            ("Dependent",             "Benefits"),
    "Emergency":            ("Emergency Contact",     "Human Capital Management"),
    "WorkerDocument":       ("Worker Document",       "Human Capital Management"),
    "AcademicUnit":         ("Academic Unit",         "Academic Foundation"),
    "Student":              ("Student",               "Academic Foundation"),
}

# ---------------------------------------------------------------------------
# Canonical concept hints: display_name / partial → canonical concept ID
# Hard-coded additions that XSD text alone cannot derive
# ---------------------------------------------------------------------------
MANUAL_CANONICAL_HINTS: dict[str, str] = {
    "Employee_ID":             "employee.id",
    "Worker_ID":               "employee.id",
    "Personnel_ID":            "employee.id",
    "Employee_Number":         "employee.id",
    "Worker_Reference_ID":     "employee.id",
    "First_Name":              "employee.name",
    "Last_Name":               "employee.name",
    "Full_Name":               "employee.name",
    "Legal_Name":              "employee.name",
    "Preferred_Name":          "employee.name",
    "Employee_Email":          "employee.email",
    "Work_Email":              "employee.email",
    "Primary_Work_Email":      "employee.email",
    "Home_Phone":              "employee.phone",
    "Work_Phone":              "employee.phone",
    "Mobile_Phone":            "employee.phone",
    "Phone_Number":            "employee.phone",
    "Department":              "employee.department",
    "Cost_Center_ID":          "cost_center.id",
    "Cost_Center_Reference_ID":"cost_center.id",
    "Supervisory_Organization":"employee.department",
    "Organization_Reference_ID":"company.id",
    "Company_Reference_ID":    "company.id",
    "Legal_Entity_ID":         "company.id",
    "Position_ID":             "employee.position",
    "Position_Reference_ID":   "employee.position",
    "Job_Title":               "employee.position",
    "Manager_Reference_ID":    "employee.manager_id",
    "Reports_To_Reference_ID": "employee.manager_id",
    "Location_ID":             "warehouse.id",
    "Location_Reference_ID":   "warehouse.id",
    "Country_ISO_Code":        "address.country",
    "Country_Code":            "address.country",
    "City":                    "address.city",
    "Postal_Code":             "address.postal_code",
    "Zip_Code":                "address.postal_code",
    "Hire_Date":               "employee.hire_date",
    "Termination_Date":        "employee.termination_date",
    "Birth_Date":              "employee.birth_date",
    "Date_of_Birth":           "employee.birth_date",
    "Compensation_Grade":      "compensation.grade",
    "Annual_Salary":           "compensation.base_salary",
    "Base_Pay":                "compensation.base_salary",
    "Pay_Rate":                "compensation.base_salary",
    "Currency_Code":           "invoice.currency",
    "Tax_ID":                  "tax.id",
    "National_ID":             "employee.national_id",
    "Social_Security_Number":  "employee.national_id",
    "Passport_ID":             "employee.passport_id",
}

# ---------------------------------------------------------------------------
# New canonical entries to add to canonical_glossary.csv
# (concepts referenced in MANUAL_CANONICAL_HINTS but missing from glossary)
# ---------------------------------------------------------------------------
NEW_CANONICAL_ENTRIES = [
    # concept_id, entity, attribute, display_name, description, data_type, aliases
    ("employee.hire_date",        "employee", "hire_date",        "Hire Date",
     "Date employee was first hired",                                "date",
     "hire date, employment start date, start date, original hire date, Hire_Date"),
    ("employee.termination_date", "employee", "termination_date", "Termination Date",
     "Date employee contract or employment ended",                   "date",
     "termination date, end date, separation date, Termination_Date"),
    ("employee.birth_date",       "employee", "birth_date",       "Date of Birth",
     "Employee birth date",                                          "date",
     "birth date, date of birth, dob, Birth_Date, Date_of_Birth"),
    ("employee.national_id",      "employee", "national_id",      "National ID",
     "Government-issued national identification number",             "string",
     "national id, national id number, ssn, social security number, nin, National_ID"),
    ("employee.passport_id",      "employee", "passport_id",      "Passport ID",
     "Passport document number",                                     "string",
     "passport number, passport id, Passport_ID"),
    ("compensation.grade",        "compensation", "grade",         "Compensation Grade",
     "Pay grade or salary band assigned to an employee",             "string",
     "compensation grade, pay grade, salary grade, salary band, Compensation_Grade"),
    ("compensation.base_salary",  "compensation", "base_salary",   "Base Salary",
     "Annual or periodic base salary amount",                        "decimal",
     "base salary, annual salary, base pay, base wage, pay rate, Annual_Salary, Base_Pay"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def clean_doc(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def entity_from_type_name(type_name: str) -> str:
    """Worker_DataType → Worker,  Personal_Information_DataType → PersonalInformation"""
    name = type_name
    name = re.sub(r"(DataType|Type)$", "", name)
    name = name.replace("_", "")
    return name


def functional_area(entity_key: str) -> tuple[str, str]:
    for key, (label, area) in ENTITY_LABELS.items():
        if entity_key.lower().startswith(key.lower()):
            return label, area
    return entity_key, "Human Capital Management"


def canonical_from_description(desc: str) -> str | None:
    """Simple keyword match against common canonical concepts."""
    d = desc.lower()
    rules = [
        (["employee id", "worker id", "personnel number", "employee number"], "employee.id"),
        (["employee name", "worker name", "full name", "legal name"], "employee.name"),
        (["employee email", "work email", "personal email"], "employee.email"),
        (["employee phone", "work phone", "mobile", "phone number"], "employee.phone"),
        (["department", "org unit", "supervisory org"], "employee.department"),
        (["position", "job title", "job code"], "employee.position"),
        (["manager", "supervisor", "reports to"], "employee.manager_id"),
        (["hire date", "employment start", "original hire"], "employee.hire_date"),
        (["termination date", "separation date", "end date of employ"], "employee.termination_date"),
        (["birth date", "date of birth", "dob"], "employee.birth_date"),
        (["national id", "social security", "national identification"], "employee.national_id"),
        (["cost center id", "cost center reference"], "cost_center.id"),
        (["company id", "company reference", "legal entity"], "company.id"),
        (["location id", "location reference", "facility id"], "warehouse.id"),
        (["country", "country iso", "country code"], "address.country"),
        (["city"], "address.city"),
        (["postal code", "zip code", "postcode"], "address.postal_code"),
        (["base salary", "annual salary", "base pay", "pay rate"], "compensation.base_salary"),
        (["compensation grade", "pay grade", "salary grade"], "compensation.grade"),
        (["currency"], "invoice.currency"),
        (["tax id", "tax registration", "tax number"], "tax.id"),
    ]
    for keywords, concept_id in rules:
        if any(kw in d for kw in keywords):
            return concept_id
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class FieldRecord(NamedTuple):
    entity: str
    functional_area: str
    type_name: str
    section: str
    field_name: str
    xsd_type: str
    required: bool
    description: str
    canonical_concept_id: str | None


def parse_xsd(xsd_path: Path) -> list[FieldRecord]:
    with xsd_path.open("rb") as fh:
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(fh, parser)
    root = tree.getroot()

    NS = f"{{{XSD_NS}}}"
    records: list[FieldRecord] = []

    for ct in root.iter(f"{NS}complexType"):
        type_name = ct.get("name", "")
        if not type_name:
            continue
        if any(type_name.endswith(s) for s in SKIP_SUFFIX):
            continue

        entity_key = entity_from_type_name(type_name)
        entity_label, func_area = functional_area(entity_key)

        for el in ct.iter(f"{NS}element"):
            field_name = el.get("name", "")
            if not field_name:
                continue
            xsd_type = el.get("type", "").replace(f"{{{WD_NS}}}", "wd:").replace(f"{{{XSD_NS}}}", "xsd:")
            min_occ = el.get("minOccurs", "1")
            required = (min_occ != "0")

            doc_el = el.find(f"{NS}annotation/{NS}documentation")
            description = clean_doc(doc_el.text if doc_el is not None else "")

            # Determine canonical concept ID
            canon = MANUAL_CANONICAL_HINTS.get(field_name)
            if canon is None and description:
                canon = canonical_from_description(description)

            # Section = first segment of type_name (e.g. "Personal" from Personal_Info_DataType)
            section = type_name.split("_")[0]

            records.append(FieldRecord(
                entity=entity_label,
                functional_area=func_area,
                type_name=type_name,
                section=section,
                field_name=field_name,
                xsd_type=xsd_type,
                required=required,
                description=description,
                canonical_concept_id=canon,
            ))

    return records


# ---------------------------------------------------------------------------
# Generate Knowledge Overlay CSV
# ---------------------------------------------------------------------------
OVERLAY_HEADERS = [
    "entry_type", "canonical_term", "canonical_concept_id",
    "alias", "domain", "source_system", "note",
]

def generate_overlay_csv(records: list[FieldRecord], out_path: Path) -> int:
    """Write concept_alias rows for every field that has a canonical mapping."""
    # Load canonical glossary to resolve display names
    glossary_path = PROJECT_ROOT / "metadata_dict" / "canonical_glossary_erp.csv"
    id_to_display: dict[str, str] = {}
    if glossary_path.exists():
        with glossary_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                id_to_display[row["concept_id"]] = row["display_name"]

    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    for rec in records:
        if rec.canonical_concept_id is None:
            continue
        key = (rec.canonical_concept_id, rec.field_name)
        if key in seen:
            continue
        seen.add(key)
        display = id_to_display.get(rec.canonical_concept_id, rec.canonical_concept_id)
        rows.append({
            "entry_type":           "concept_alias",
            "canonical_term":       display,
            "canonical_concept_id": rec.canonical_concept_id,
            "alias":                rec.field_name,
            "domain":               rec.functional_area,
            "source_system":        "Workday",
            "note":                 rec.description[:120] if rec.description else "",
        })

    # Also add un-derived aliases from MANUAL_CANONICAL_HINTS not covered by XSD fields
    parsed_fields = {rec.field_name for rec in records}
    for field_name, cid in MANUAL_CANONICAL_HINTS.items():
        key = (cid, field_name)
        if key in seen or field_name in parsed_fields:
            continue
        seen.add(key)
        display = id_to_display.get(cid, cid)
        rows.append({
            "entry_type":           "concept_alias",
            "canonical_term":       display,
            "canonical_concept_id": cid,
            "alias":                field_name,
            "domain":               "Human Capital Management",
            "source_system":        "Workday",
            "note":                 f"Manual hint: {field_name}",
        })

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OVERLAY_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


# ---------------------------------------------------------------------------
# Update canonical_glossary.csv with new entries
# ---------------------------------------------------------------------------

def extend_canonical_glossary(glossary_path: Path) -> int:
    existing_ids: set[str] = set()
    if glossary_path.exists():
        with glossary_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                existing_ids.add(row["concept_id"])

    new_entries = [e for e in NEW_CANONICAL_ENTRIES if e[0] not in existing_ids]
    if not new_entries:
        return 0

    with glossary_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for entry in new_entries:
            writer.writerow(entry)

    return len(new_entries)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--xsd", type=Path, default=PROJECT_ROOT / "metadata_dict" / "hr_wd.xml")
    p.add_argument("--out", type=Path, default=PROJECT_ROOT / "metadata_dict" / "wd_hr_knowledge_overlay.csv")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    xsd_path = Path(args.xsd)
    out_path = Path(args.out)
    glossary_path = PROJECT_ROOT / "metadata_dict" / "canonical_glossary_erp.csv"

    print(f"Parsing {xsd_path} ({xsd_path.stat().st_size / 1024:.0f} KB)...")
    records = parse_xsd(xsd_path)

    mapped     = [r for r in records if r.canonical_concept_id]
    unmapped   = [r for r in records if r.canonical_concept_id is None]
    unique_fields = {r.field_name for r in records}
    unique_mapped = {r.field_name for r in mapped}

    print(f"\n{'='*55}")
    print(f"Total XSD field entries parsed : {len(records):>6}")
    print(f"Unique field names             : {len(unique_fields):>6}")
    print(f"Fields with canonical match    : {len(unique_mapped):>6}")
    print(f"Fields without canonical match : {len(unique_fields - unique_mapped):>6}")
    print(f"Distinct entities              : {len({r.entity for r in records}):>6}")

    print(f"\nCanonical concept coverage:")
    from collections import Counter
    ctr = Counter(r.canonical_concept_id for r in mapped if r.canonical_concept_id)
    for cid, cnt in ctr.most_common(20):
        print(f"  {cid:45} {cnt:>4} fields")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    # Extend canonical glossary
    added = extend_canonical_glossary(glossary_path)
    if added:
        print(f"\n+ Added {added} new entries to canonical_glossary.csv")
        for entry in NEW_CANONICAL_ENTRIES:
            print(f"  {entry[0]}")
    else:
        print("\n  Canonical glossary already up-to-date.")

    # Write overlay CSV
    n = generate_overlay_csv(records, out_path)
    print(f"\n+ Wrote {n} overlay rows → {out_path}")
    print(f"\nNext step: Admin tab → Knowledge Overlay → upload {out_path.name}")


if __name__ == "__main__":
    main()
