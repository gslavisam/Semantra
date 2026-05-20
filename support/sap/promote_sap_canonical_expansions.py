"""Promote a second SAP wave of safe canonical expansions.

This script promotes two additional SAP slices into the canonical layer:
- safe `knowledge_only` families into new canonical concepts
- safe `strong_canonical_candidate` families into existing canonical concepts

Outputs under knowledge_sources/generated/runtime/sap/:
    - sap_wave2_promoted_canonical_expansions.csv
    - sap_wave2_promotion_summary.csv
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.services.metadata_knowledge_service import CANONICAL_GLOSSARY_HEADERS, metadata_knowledge_service
from app.utils.knowledge_text import filter_canonical_aliases, normalize_canonical_alias_text, split_csv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_inventory_classification.csv"
PROMOTED_REPORT_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_wave2_promoted_canonical_expansions.csv"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_wave2_promotion_summary.csv"


@dataclass(frozen=True)
class NewConceptRule:
    rule_name: str
    sap_field: str
    concept_id: str
    display_name: str
    description: str
    data_type: str
    classification_bucket: str = "knowledge_only"
    top_knowledge_concept_id: str = ""
    extra_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExistingConceptRule:
    rule_name: str
    sap_field: str
    concept_id: str
    classification_bucket: str = "strong_canonical_candidate"
    top_knowledge_concept_id: str = ""
    top_canonical_concept_id: str = ""


NEW_CONCEPT_RULES: tuple[NewConceptRule, ...] = (
    NewConceptRule(
        rule_name="material_net_weight",
        sap_field="NTGEW",
        top_knowledge_concept_id="net weight",
        concept_id="material.net_weight",
        display_name="Material Net Weight",
        description="Net weight or net mass associated with a material, product, or logistics line item.",
        data_type="decimal",
        extra_aliases=("net weight",),
    ),
    NewConceptRule(
        rule_name="volume_unit_code",
        sap_field="VOLEH",
        top_knowledge_concept_id="volume unit",
        concept_id="volume.unit_code",
        display_name="Volume Unit Code",
        description="Unit of measure code used for volume quantities.",
        data_type="string",
        extra_aliases=("volume unit", "volume uom"),
    ),
    NewConceptRule(
        rule_name="material_type_code",
        sap_field="MTART",
        top_knowledge_concept_id="material type",
        concept_id="material.type_code",
        display_name="Material Type Code",
        description="Code identifying the SAP material type or a materially equivalent product-type classification.",
        data_type="string",
        extra_aliases=("material type",),
    ),
    NewConceptRule(
        rule_name="address_id",
        sap_field="ADRNR",
        top_knowledge_concept_id="address id",
        concept_id="address.id",
        display_name="Address ID",
        description="Stable identifier for an address master or address reference record.",
        data_type="string",
        extra_aliases=("address id", "address number"),
    ),
    NewConceptRule(
        rule_name="chart_of_accounts_id",
        sap_field="KTOPL",
        top_knowledge_concept_id="chart of accounts",
        concept_id="chart_of_accounts.id",
        display_name="Chart of Accounts ID",
        description="Identifier for a chart of accounts used by accounting entities and ledgers.",
        data_type="string",
        extra_aliases=("chart of accounts",),
    ),
    NewConceptRule(
        rule_name="asset_class_code",
        sap_field="ANLKL",
        top_knowledge_concept_id="asset class",
        concept_id="asset.class_code",
        display_name="Asset Class Code",
        description="Classification code that identifies the fixed-asset class used for accounting and reporting.",
        data_type="string",
        extra_aliases=("asset class",),
    ),
    NewConceptRule(
        rule_name="asset_manufacturer_name",
        sap_field="HERST",
        top_knowledge_concept_id="manufacturer",
        concept_id="asset.manufacturer_name",
        display_name="Asset Manufacturer Name",
        description="Name of the manufacturer associated with a fixed asset.",
        data_type="string",
        extra_aliases=("asset manufacturer", "manufacturer of asset", "manufacturer"),
    ),
    NewConceptRule(
        rule_name="project_wbs_element_id_ps_posid",
        sap_field="PS_POSID",
        top_knowledge_concept_id="wbs element",
        concept_id="project.wbs_element_id",
        display_name="WBS Element ID",
        description="Identifier for a work breakdown structure element used for project planning, accounting, or logistics assignment.",
        data_type="string",
        extra_aliases=("wbs element", "work breakdown structure element", "wbs id"),
    ),
    NewConceptRule(
        rule_name="project_wbs_element_id_mat_pspnr",
        sap_field="MAT_PSPNR",
        top_knowledge_concept_id="wbs element",
        concept_id="project.wbs_element_id",
        display_name="WBS Element ID",
        description="Identifier for a work breakdown structure element used for project planning, accounting, or logistics assignment.",
        data_type="string",
        extra_aliases=("wbs element", "work breakdown structure element", "wbs id"),
    ),
    NewConceptRule(
        rule_name="project_wbs_element_id_mat_ps_posid",
        sap_field="MAT_PS_POSID",
        top_knowledge_concept_id="wbs element",
        concept_id="project.wbs_element_id",
        display_name="WBS Element ID",
        description="Identifier for a work breakdown structure element used for project planning, accounting, or logistics assignment.",
        data_type="string",
        extra_aliases=("wbs element", "work breakdown structure element", "wbs id"),
    ),
    NewConceptRule(
        rule_name="project_wbs_element_id_pspnr",
        sap_field="PSPNR",
        top_knowledge_concept_id="wbs element",
        concept_id="project.wbs_element_id",
        display_name="WBS Element ID",
        description="Identifier for a work breakdown structure element used for project planning, accounting, or logistics assignment.",
        data_type="string",
        extra_aliases=("wbs element", "work breakdown structure element", "wbs id"),
    ),
    NewConceptRule(
        rule_name="validity_start_date_datab",
        sap_field="DATAB",
        concept_id="validity.start_date",
        display_name="Validity Start Date",
        description="Date from which a record, agreement, assignment, or configuration becomes effective.",
        data_type="date",
        classification_bucket="description_alias_match",
        extra_aliases=("valid from date", "effective from", "start date"),
    ),
    NewConceptRule(
        rule_name="party_salutation_anred",
        sap_field="ANRED",
        concept_id="party.salutation",
        display_name="Party Salutation",
        description="Honorific, form-of-address, or salutation associated with a person or organization.",
        data_type="string",
        classification_bucket="description_alias_match",
        extra_aliases=("salutation", "form of address", "title"),
    ),
    NewConceptRule(
        rule_name="manufacturer_id_mfrnr",
        sap_field="MFRNR",
        concept_id="manufacturer.id",
        display_name="Manufacturer ID",
        description="Identifier for a manufacturer referenced by a source transaction or master record.",
        data_type="string",
        classification_bucket="description_alias_match",
        extra_aliases=("manufacturer id", "manufacturer number"),
    ),
    NewConceptRule(
        rule_name="reason_code_reason_code",
        sap_field="REASON_CODE",
        top_knowledge_concept_id="adjustment reason",
        concept_id="reason.code",
        display_name="Reason Code",
        description="Generic code or identifier describing the business reason for a status, movement, exception, or adjustment.",
        data_type="string",
        extra_aliases=("reason code", "adjustment reason", "movement reason"),
    ),
    NewConceptRule(
        rule_name="reason_code_grund",
        sap_field="GRUND",
        top_knowledge_concept_id="adjustment reason",
        concept_id="reason.code",
        display_name="Reason Code",
        description="Generic code or identifier describing the business reason for a status, movement, exception, or adjustment.",
        data_type="string",
        extra_aliases=("reason code", "adjustment reason", "movement reason"),
    ),
    NewConceptRule(
        rule_name="reason_code_blk_reason_id",
        sap_field="BLK_REASON_ID",
        top_knowledge_concept_id="adjustment reason",
        concept_id="reason.code",
        display_name="Reason Code",
        description="Generic code or identifier describing the business reason for a status, movement, exception, or adjustment.",
        data_type="string",
        extra_aliases=("reason code", "adjustment reason", "blocking reason"),
    ),
    NewConceptRule(
        rule_name="reason_code_rstgr",
        sap_field="RSTGR",
        top_knowledge_concept_id="adjustment reason",
        concept_id="reason.code",
        display_name="Reason Code",
        description="Generic code or identifier describing the business reason for a status, movement, exception, or adjustment.",
        data_type="string",
        extra_aliases=("reason code", "adjustment reason", "payment reason code"),
    ),
    NewConceptRule(
        rule_name="reason_code_rsncd",
        sap_field="RSNCD",
        top_knowledge_concept_id="adjustment reason",
        concept_id="reason.code",
        display_name="Reason Code",
        description="Generic code or identifier describing the business reason for a status, movement, exception, or adjustment.",
        data_type="string",
        extra_aliases=("reason code", "adjustment reason"),
    ),
    NewConceptRule(
        rule_name="system_guid_vcm_chain_uuid",
        sap_field="VCM_CHAIN_UUID",
        top_knowledge_concept_id="guid",
        concept_id="system.guid",
        display_name="System GUID",
        description="Globally unique identifier or UUID generated by a source system for an entity, record, or processing chain.",
        data_type="string",
        extra_aliases=("guid", "uuid", "globally unique identifier"),
    ),
    NewConceptRule(
        rule_name="system_guid_uuid",
        sap_field="UUID",
        top_knowledge_concept_id="guid",
        concept_id="system.guid",
        display_name="System GUID",
        description="Globally unique identifier or UUID generated by a source system for an entity, record, or processing chain.",
        data_type="string",
        extra_aliases=("guid", "uuid", "globally unique identifier"),
    ),
    NewConceptRule(
        rule_name="system_guid_status_obj_guid",
        sap_field="STATUS_OBJ_GUID",
        top_knowledge_concept_id="guid",
        concept_id="system.guid",
        display_name="System GUID",
        description="Globally unique identifier or UUID generated by a source system for an entity, record, or processing chain.",
        data_type="string",
        extra_aliases=("guid", "uuid", "globally unique identifier"),
    ),
    NewConceptRule(
        rule_name="version_number_revno",
        sap_field="REVNO",
        top_knowledge_concept_id="version number",
        concept_id="version.number",
        display_name="Version Number",
        description="Version identifier or revision number associated with a business object, requirement, or planning record.",
        data_type="string",
        extra_aliases=("version number", "revision number", "version"),
    ),
    NewConceptRule(
        rule_name="version_number_numvr",
        sap_field="NUMVR",
        top_knowledge_concept_id="version number",
        concept_id="version.number",
        display_name="Version Number",
        description="Version identifier or revision number associated with a business object, requirement, or planning record.",
        data_type="string",
        extra_aliases=("version number", "revision number", "version"),
    ),
    NewConceptRule(
        rule_name="version_number_versb",
        sap_field="VERSB",
        top_knowledge_concept_id="version number",
        concept_id="version.number",
        display_name="Version Number",
        description="Version identifier or revision number associated with a business object, requirement, or planning record.",
        data_type="string",
        extra_aliases=("version number", "revision number", "version"),
    ),
    NewConceptRule(
        rule_name="external_reference_id",
        sap_field="EXTERNALREFERENCEID",
        top_knowledge_concept_id="external id",
        concept_id="external_reference.id",
        display_name="External Reference ID",
        description="Identifier assigned by an external system, partner, or reference process to a business object.",
        data_type="string",
        extra_aliases=("external reference id", "external id"),
    ),
)

EXISTING_CONCEPT_RULES: tuple[ExistingConceptRule, ...] = (
    ExistingConceptRule(rule_name="invoice_due_date", sap_field="NETDT", concept_id="invoice.due_date", top_canonical_concept_id="invoice.due_date"),
    ExistingConceptRule(rule_name="payment_method_pay_method", sap_field="PAY_METHOD", concept_id="payment.method_code", top_canonical_concept_id="payment.method_code"),
    ExistingConceptRule(rule_name="payment_method_pay_type", sap_field="PAY_TYPE", concept_id="payment.method_code", top_canonical_concept_id="payment.method_code"),
    ExistingConceptRule(rule_name="sales_order_id", sap_field="KDAUF", concept_id="sales_order.id", top_canonical_concept_id="sales_order.id"),
    ExistingConceptRule(
        rule_name="sales_unit_code",
        sap_field="VRKME",
        concept_id="uom.code",
        classification_bucket="knowledge_only",
        top_knowledge_concept_id="sales unit",
    ),
    ExistingConceptRule(
        rule_name="document_type_blart",
        sap_field="BLART",
        concept_id="document.type",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="document.type",
    ),
    ExistingConceptRule(
        rule_name="project_wbs_element_id_projn",
        sap_field="PROJN",
        concept_id="project.wbs_element_id",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="project.wbs_element_id",
    ),
    ExistingConceptRule(
        rule_name="plant_id_umwrk",
        sap_field="UMWRK",
        concept_id="plant.id",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="plant.id",
    ),
    ExistingConceptRule(
        rule_name="plant_id_plwrk",
        sap_field="PLWRK",
        concept_id="plant.id",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="plant.id",
    ),
    ExistingConceptRule(
        rule_name="company_id_vbund",
        sap_field="VBUND",
        concept_id="company.id",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="company.id",
    ),
    ExistingConceptRule(
        rule_name="address_id_adrn2",
        sap_field="ADRN2",
        concept_id="address.id",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="address.id",
    ),
    ExistingConceptRule(
        rule_name="uom_code_meinh",
        sap_field="MEINH",
        concept_id="uom.code",
        classification_bucket="description_alias_match",
    ),
    ExistingConceptRule(
        rule_name="material_number_ematn",
        sap_field="EMATN",
        concept_id="material.number",
        classification_bucket="description_alias_match",
    ),
    ExistingConceptRule(
        rule_name="route_id_plnnr",
        sap_field="PLNNR",
        concept_id="route.id",
        classification_bucket="knowledge_only",
        top_knowledge_concept_id="routing",
    ),
    ExistingConceptRule(
        rule_name="system_guid_handle",
        sap_field="HANDLE",
        concept_id="system.guid",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="system.guid",
    ),
    ExistingConceptRule(
        rule_name="version_number_versn",
        sap_field="VERSN",
        concept_id="version.number",
        classification_bucket="description_alias_match",
        top_canonical_concept_id="version.number",
    ),
)


def main() -> None:
    classification_rows = list(read_csv(CLASSIFICATION_PATH))
    glossary_path = metadata_knowledge_service.canonical_glossary_path
    context_path = glossary_path.parent / "canonical_field_context_enrichment.csv"

    glossary_rows = load_glossary_rows(glossary_path)
    glossary_by_concept = {row["concept_id"]: row for row in glossary_rows}
    context_rows = list(read_csv(context_path))
    existing_context_keys = {(row["concept_id"], row["system"], row["object_name"], row["field_name"]) for row in context_rows}

    promoted_rows: list[dict[str, str]] = []
    used_rows: set[tuple[str, str, str]] = set()

    for rule in NEW_CONCEPT_RULES:
        matching_rows = [
            row for row in classification_rows
            if row["classification_bucket"] == rule.classification_bucket
            and row["sap_field"].strip() == rule.sap_field
            and (
                not rule.top_knowledge_concept_id
                or row.get("top_knowledge_concept_id", "").strip() == rule.top_knowledge_concept_id
            )
        ]
        promoted_rows.extend(
            promote_rows_to_concept(
                matching_rows,
                concept_id=rule.concept_id,
                display_name=rule.display_name,
                description=rule.description,
                data_type=rule.data_type,
                glossary_rows=glossary_rows,
                glossary_by_concept=glossary_by_concept,
                context_rows=context_rows,
                existing_context_keys=existing_context_keys,
                used_rows=used_rows,
                action_type="new_canonical_concept",
                rule_name=rule.rule_name,
                extra_aliases=rule.extra_aliases,
            )
        )

    for rule in EXISTING_CONCEPT_RULES:
        matching_rows = [
            row for row in classification_rows
            if row["classification_bucket"] == rule.classification_bucket
            and row["sap_field"].strip() == rule.sap_field
            and (
                not rule.top_canonical_concept_id
                or row.get("top_canonical_concept_id", "").strip() == rule.top_canonical_concept_id
            )
            and (
                not rule.top_knowledge_concept_id
                or row.get("top_knowledge_concept_id", "").strip() == rule.top_knowledge_concept_id
            )
        ]
        promoted_rows.extend(
            promote_rows_to_concept(
                matching_rows,
                concept_id=rule.concept_id,
                display_name=None,
                description="",
                data_type="",
                glossary_rows=glossary_rows,
                glossary_by_concept=glossary_by_concept,
                context_rows=context_rows,
                existing_context_keys=existing_context_keys,
                used_rows=used_rows,
                action_type="existing_canonical_alias",
                rule_name=rule.rule_name,
                extra_aliases=(),
            )
        )

    write_glossary_rows(glossary_path, glossary_rows)
    write_csv(
        context_path,
        context_rows,
        ["concept_id", "system", "object_name", "field_name", "category", "object_description", "field_description", "note"],
    )
    metadata_knowledge_service.refresh()

    write_csv(PROMOTED_REPORT_PATH, promoted_rows, promoted_headers())
    write_summary(promoted_rows, len(classification_rows))

    print(f"Processed classification rows: {len(classification_rows)}")
    print(f"Wave-2 promoted rows: {len(promoted_rows)}")
    print(f"Wave-2 alias additions: {sum(1 for row in promoted_rows if row['alias_added'] == 'true')}")
    print(f"Wave-2 concept creations: {sum(1 for row in promoted_rows if row['concept_created'] == 'true')}")
    print(f"Wave-2 context additions: {sum(1 for row in promoted_rows if row['context_added'] == 'true')}")
    print(f"Wrote: {PROMOTED_REPORT_PATH}")
    print(f"Wrote: {SUMMARY_PATH}")


def promote_rows_to_concept(
    rows: list[dict[str, str]],
    *,
    concept_id: str,
    display_name: str | None,
    description: str,
    data_type: str,
    glossary_rows: list[dict[str, str]],
    glossary_by_concept: dict[str, dict[str, str]],
    context_rows: list[dict[str, str]],
    existing_context_keys: set[tuple[str, str, str, str]],
    used_rows: set[tuple[str, str, str]],
    action_type: str,
    rule_name: str,
    extra_aliases: tuple[str, ...],
) -> list[dict[str, str]]:
    if not rows:
        return []

    report_rows: list[dict[str, str]] = []
    concept_row = glossary_by_concept.get(concept_id)
    concept_was_created = concept_row is None
    if concept_row is None:
        concept_row = {
            "concept_id": concept_id,
            "entity": concept_id.split(".", 1)[0] if "." in concept_id else "general",
            "attribute": concept_id.split(".", 1)[1] if "." in concept_id else concept_id,
            "display_name": (display_name or concept_id).strip() or concept_id,
            "description": description.strip(),
            "data_type": data_type.strip(),
            "aliases": "",
        }
        glossary_rows.append(concept_row)
        glossary_by_concept[concept_id] = concept_row

    existing_aliases = {
        normalized
        for normalized in (
            normalize_canonical_alias_text(value)
            for value in split_csv_values(concept_row.get("aliases") or "")
        )
        if normalized
    }
    concept_alias_added = False
    concept_creation_report_pending = concept_was_created

    for row in rows:
        row_key = (row["sap_module"], row["sap_table"], row["sap_field"])
        if row_key in used_rows:
            continue
        used_rows.add(row_key)

        aliases_to_add = {
            normalize_canonical_alias_text(row["sap_field"]),
            normalize_canonical_alias_text(row["sap_description"]),
            *(normalize_canonical_alias_text(alias) for alias in extra_aliases),
        }
        aliases_to_add = {alias for alias in aliases_to_add if alias}
        before_count = len(existing_aliases)
        existing_aliases.update(aliases_to_add)
        alias_added = len(existing_aliases) > before_count
        concept_alias_added = concept_alias_added or alias_added
        row_concept_created = concept_creation_report_pending

        context_key = (concept_id, "SAP", row["sap_table"].strip(), row["sap_field"].strip())
        context_added = context_key not in existing_context_keys
        if context_added:
            context_rows.append(
                {
                    "concept_id": concept_id,
                    "system": "SAP",
                    "object_name": row["sap_table"].strip(),
                    "field_name": row["sap_field"].strip(),
                    "category": concept_id.split(".", 1)[0] if "." in concept_id else "general",
                    "object_description": row.get("sap_table_description", "").strip(),
                    "field_description": row.get("sap_description", "").strip(),
                    "note": (
                        "source=sap_full_inventory_classification; confidence=high; "
                        f"reason={action_type}; rule={rule_name}; module={row.get('sap_module', '').strip() or 'UNKNOWN'}"
                    ),
                }
            )
            existing_context_keys.add(context_key)

        if not alias_added and not context_added and not row_concept_created:
            continue

        report_rows.append(
            {
                "action_type": action_type,
                "rule_name": rule_name,
                "sap_module": row.get("sap_module", ""),
                "sap_table": row.get("sap_table", ""),
                "sap_field": row.get("sap_field", ""),
                "sap_description": row.get("sap_description", ""),
                "source_bucket": row.get("classification_bucket", ""),
                "canonical_concept_id": concept_id,
                "alias_added": str(alias_added).lower(),
                "concept_created": str(row_concept_created).lower(),
                "context_added": str(context_added).lower(),
            }
        )
        concept_creation_report_pending = False

    if concept_alias_added:
        concept_row["aliases"] = ", ".join(sorted(filter_canonical_aliases(existing_aliases)))
    return report_rows


def write_summary(promoted_rows: list[dict[str, str]], total_rows: int) -> None:
    rows: list[dict[str, str]] = []
    if not promoted_rows:
        rows.append({"scope": "run_status", "label": "no_changes", "row_count": "0", "ratio": "0.0000"})
        write_csv(SUMMARY_PATH, rows, ["scope", "label", "row_count", "ratio"])
        return
    for action_type, count in sorted(Counter(row["action_type"] for row in promoted_rows).items()):
        rows.append({"scope": "action_type", "label": action_type, "row_count": str(count), "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000"})
    for rule_name, count in sorted(Counter(row["rule_name"] for row in promoted_rows).items()):
        rows.append({"scope": "rule_name", "label": rule_name, "row_count": str(count), "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000"})
    for label, count in sorted(Counter(row["concept_created"] for row in promoted_rows).items()):
        rows.append({"scope": "concept_created", "label": label, "row_count": str(count), "ratio": f"{(count / total_rows):.4f}" if total_rows else "0.0000"})
    write_csv(SUMMARY_PATH, rows, ["scope", "label", "row_count", "ratio"])


def load_glossary_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{header: str(row.get(header) or "").strip() for header in CANONICAL_GLOSSARY_HEADERS} for row in reader]


def write_glossary_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_GLOSSARY_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def promoted_headers() -> list[str]:
    return [
        "action_type",
        "rule_name",
        "sap_module",
        "sap_table",
        "sap_field",
        "sap_description",
        "source_bucket",
        "canonical_concept_id",
        "alias_added",
        "concept_created",
        "context_added",
    ]


if __name__ == "__main__":
    main()