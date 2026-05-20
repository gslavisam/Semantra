"""
Parse Workday hr_wd_valid.xml (XSD) and generate a flat CSV inventory of all entities and fields for canonical mapping.

Output: knowledge_sources/generated/runtime/workday/hr_wd_webservice_inventory.csv
Columns: wd_entity, wd_field, wd_type, wd_description

Usage:
    python support/workday/generate_workday_webservice_inventory.py
"""

import csv
import re
from pathlib import Path

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parents[2]
XSD_PATH = PROJECT_ROOT / "metadata_dict" / "hr_wd.xml"
OUTPUT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "workday" / "hr_wd_webservice_inventory.csv"


def _norm_type(raw_type: str) -> str:
    if raw_type and ":" in raw_type:
        return raw_type.split(":", 1)[-1]
    return raw_type or ""


def _rows_from_tree(tree: etree._ElementTree) -> list[dict]:
    rows = []
    seen = set()

    # Use local-name() so parsing still works even if namespace declarations are damaged.
    for ctype in tree.xpath("//*[local-name()='complexType']"):
        entity = ctype.get("name")
        if not entity:
            continue

        for elem in ctype.xpath(".//*[local-name()='element']"):
            field = elem.get("name")
            if not field:
                continue
            ftype = _norm_type(elem.get("type") or "")
            doc = elem.xpath("string(./*[local-name()='annotation']/*[local-name()='documentation'])").strip()

            key = (entity, field, ftype, doc)
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                {
                    "wd_entity": entity,
                    "wd_field": field,
                    "wd_type": ftype,
                    "wd_description": doc,
                }
            )

    return rows


def parse_xsd_fields(xsd_path: Path) -> list[dict]:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree = etree.parse(str(xsd_path), parser=parser)
    return _rows_from_tree(tree)


def parse_xsd_fields_text_fallback(xsd_path: Path) -> list[dict]:
    text = xsd_path.read_text(encoding="utf-8", errors="ignore")

    ctype_pattern = re.compile(
        r"<xsd:complexType\\b[^>]*name=\"(?P<entity>[^\"]+)\"[^>]*>(?P<body>.*?)</xsd:complexType>",
        re.DOTALL,
    )
    elem_pattern = re.compile(
        r"<xsd:element\\b[^>]*name=\"(?P<field>[^\"]+)\"[^>]*?(?:type=\"(?P<type>[^\"]+)\")?[^>]*>",
        re.DOTALL,
    )
    self_elem_pattern = re.compile(
        r"<xsd:element\\b[^>]*name=\"(?P<field>[^\"]+)\"[^>]*?(?:type=\"(?P<type>[^\"]+)\")?[^>]*/>",
        re.DOTALL,
    )
    doc_pattern = re.compile(r"<xsd:documentation>(?P<doc>.*?)</xsd:documentation>", re.DOTALL)

    rows = []
    seen = set()

    for ctype in ctype_pattern.finditer(text):
        entity = ctype.group("entity")
        body = ctype.group("body")

        for match in elem_pattern.finditer(body):
            field = match.group("field")
            ftype = _norm_type(match.group("type") or "")

            tail = body[match.end() :]
            doc_match = doc_pattern.search(tail)
            doc = (doc_match.group("doc") if doc_match else "").strip()
            doc = re.sub(r"\s+", " ", doc)

            key = (entity, field, ftype, doc)
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                {
                    "wd_entity": entity,
                    "wd_field": field,
                    "wd_type": ftype,
                    "wd_description": doc,
                }
            )

        for match in self_elem_pattern.finditer(body):
            field = match.group("field")
            ftype = _norm_type(match.group("type") or "")
            key = (entity, field, ftype, "")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "wd_entity": entity,
                    "wd_field": field,
                    "wd_type": ftype,
                    "wd_description": "",
                }
            )

    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["wd_entity", "wd_field", "wd_type", "wd_description"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not XSD_PATH.exists():
        print(f"Not found: {XSD_PATH}")
        return
    try:
        rows = parse_xsd_fields(XSD_PATH)
    except Exception as e:
        print(f"XML parse error: {e}\nTrying regex fallback...")
        rows = parse_xsd_fields_text_fallback(XSD_PATH)

    if not rows:
        print("No rows from XML recovery parse. Trying regex fallback...")
        rows = parse_xsd_fields_text_fallback(XSD_PATH)

    print(f"Parsed {len(rows)} fields from {XSD_PATH.name}")
    write_csv(rows, OUTPUT_PATH)
    print(f"Wrote: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
