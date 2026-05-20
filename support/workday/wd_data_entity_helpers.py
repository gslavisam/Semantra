"""Workday HRDH entity resolver and taxonomy for fast field mapping.

Provides utilities for resolving Workday HRDH fields to canonical concepts
and enumerating available Workday data domains.

Classes:
    WDEntityResolver: resolve_field(table, column) → ConceptInfo
    WDModuleTaxonomy: Map Workday HRDH tables to HR functional areas

Usage:
    from support.workday.wd_data_entity_helpers import WDEntityResolver
    resolver = WDEntityResolver()
    concept = resolver.resolve_field("HR_EMPLOYEE", "EMPLOYEE_ID")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
import csv
import sys


@dataclass
class ConceptInfo:
    concept_id: str
    canonical_name: str
    domain: str
    confidence: str
    source_system: str
    note: str


class WDEntityResolver:
    """Resolve Workday HRDH fields to canonical concepts via materialized contexts + overlay."""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        
        # Load materialized contexts (1:1 field → concept mapping)
        self.materialized_contexts: dict[tuple[str, str], dict] = {}
        self._load_materialized_contexts()
        
        # Load knowledge overlay (concept aliases)
        self.knowledge_overlay: dict[str, str] = {}
        self._load_knowledge_overlay()

    def _load_materialized_contexts(self) -> None:
        contexts_path = self.project_root / "knowledge_sources" / "generated" / "runtime" / "workday" / "workday_materialized_canonical_contexts.csv"
        if not contexts_path.exists():
            return

        with contexts_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                table = row.get("object_name", "").strip()
                field = row.get("field_name", "").strip()
                if table and field:
                    self.materialized_contexts[(table, field)] = row

    def _load_knowledge_overlay(self) -> None:
        overlay_path = self.project_root / "metadata_dict" / "wd_datahub_knowledge_overlay.csv"
        if not overlay_path.exists():
            return

        with overlay_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("entry_type") == "concept_alias":
                    alias = row.get("alias", "").strip()
                    concept_id = row.get("canonical_concept_id", "").strip()
                    if alias and concept_id:
                        self.knowledge_overlay[alias] = concept_id

    def resolve_field(self, table: str, column: str) -> ConceptInfo | None:
        """Resolve a Workday HRDH table.column to canonical concept.
        
        Returns ConceptInfo if found in materialized contexts or knowledge overlay.
        Returns None if not found.
        """
        table = table.strip().upper()
        column = column.strip().upper()

        # Check materialized contexts first (high-confidence direct mappings)
        context = self.materialized_contexts.get((table, column))
        if context:
            note_text = context.get("note", "")
            confidence = "high" if "direct_alias_match" in note_text else "medium" if "knowledge_only" in note_text else "low"
            return ConceptInfo(
                concept_id=context.get("concept_id", ""),
                canonical_name=context.get("field_name", ""),
                domain=context.get("category", "HR"),
                confidence=confidence,
                source_system="Workday_HRDH",
                note=note_text,
            )

        # Check overlay (aliased concepts discovered during wave-2)
        if column in self.knowledge_overlay:
            concept_id = self.knowledge_overlay[column]
            return ConceptInfo(
                concept_id=concept_id,
                canonical_name=column,
                domain="Human Capital Management",
                confidence="medium",
                source_system="Workday_HRDH",
                note="Resolved via knowledge overlay",
            )

        return None

    def list_tables(self) -> list[str]:
        """List all Workday HRDH tables with materialized contexts."""
        tables = set()
        for table, _ in self.materialized_contexts.keys():
            tables.add(table)
        return sorted(tables)

    def list_table_fields(self, table: str) -> list[tuple[str, str]]:
        """List all fields for a Workday table with their concept IDs.
        
        Returns list of (field_name, concept_id) tuples.
        """
        table = table.strip().upper()
        fields = []
        for (t, f), context in self.materialized_contexts.items():
            if t == table:
                concept_id = context.get("concept_id", "")
                fields.append((f, concept_id))
        return sorted(fields)


class WDModuleTaxonomy:
    """Map Workday HRDH tables to HR functional areas."""

    # Workday HRDH tables grouped by HR functional area
    # (Based on HRDH datahub domain coverage: all "Human Capital Management")
    TAXONOMY = {
        "Human Capital Management": {
            "Core HR": [
                "CR_DIM_EMPLOYEE",
                "CR_DIM_POSITION",
                "CR_DIM_ORGANIZATION",
                "CR_DIM_MANAGER",
                "CR_DIM_JOB",
            ],
            "Compensation": [
                "CR_DIM_COMP_ELEMENT",
                "CR_DIM_COMP_PLAN",
                "CR_DIM_COMP_GRADE",
                "CR_DIM_COMP_GRADE_PROFILE",
            ],
            "Staffing": [
                "CR_DIM_APPLICANT",
                "CR_DIM_CANDIDATE",
                "CR_DIM_REQUISITION",
            ],
            "Talent Management": [
                "CR_DIM_PERFORMANCE_RATING",
                "CR_DIM_GOAL",
                "CR_DIM_COMPETENCY",
            ],
            "Benefits": [
                "CR_DIM_BENEFITS_PLAN",
                "CR_DIM_BENEFITS_ENROLLMENT",
            ],
        },
    }

    @classmethod
    def get_functional_area(cls, table: str) -> str | None:
        """Return functional area for a Workday table, or None if not found."""
        table = table.strip().upper()
        for domain, areas in cls.TAXONOMY.items():
            for area, tables in areas.items():
                if table in tables:
                    return area
        return None

    @classmethod
    def get_tables_for_area(cls, area: str) -> list[str]:
        """Return all Workday tables in a functional area."""
        for domain, areas in cls.TAXONOMY.items():
            if area in areas:
                return areas[area]
        return []

    @classmethod
    def list_functional_areas(cls) -> dict[str, list[str]]:
        """Return all functional areas with their tables."""
        result = {}
        for domain, areas in cls.TAXONOMY.items():
            for area, tables in areas.items():
                result[area] = tables
        return result


if __name__ == "__main__":
    # Quick test
    resolver = WDEntityResolver()
    print(f"Loaded {len(resolver.materialized_contexts)} materialized contexts")
    print(f"Loaded {len(resolver.knowledge_overlay)} knowledge overlay entries")
    
    tables = resolver.list_tables()
    print(f"\nWorkday HRDH tables with contexts: {len(tables)}")
    
    print("\nWD Functional Areas:")
    for area, tables in WDModuleTaxonomy.list_functional_areas().items():
        print(f"  {area}: {len(tables)} tables")
