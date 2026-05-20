"""QuickBooks data entity mapping helpers for canonical discovery.

Provides utilities for mapping new QB data sources to canonical business concepts
using established QB wave artifacts and overlays.

This enables easy, repeatable QB entity mapping pattern for future QB data ingests.

Usage:
    from support.quickbooks.qb_data_entity_helpers import QBEntityResolver
    
    resolver = QBEntityResolver()
    concept_info = resolver.resolve_field("Customer", "FullName")
    # Returns: {'concept_id': 'contact.name', 'confidence': 'high', 'context': {...}}
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, TypedDict


class ConceptInfo(TypedDict, total=False):
    """QB field → canonical concept resolution info."""
    concept_id: str
    confidence: str
    source: str
    qb_table: str
    qb_field: str
    description: str


class QBEntityResolver:
    """Maps QB table-field combinations to canonical concepts."""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self._materialized_contexts: dict[tuple[str, str], dict[str, str]] = {}
        self._knowledge_overlay: dict[str, str] = {}
        self._load_contexts()

    def _load_contexts(self) -> None:
        """Load QB materialized contexts and knowledge overlay."""
        contexts_path = (
            self.project_root 
            / "knowledge_sources" / "generated" / "runtime" / "quickbooks"
            / "quickbooks_materialized_canonical_contexts.csv"
        )
        if contexts_path.exists():
            with contexts_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("object_name", ""), row.get("field_name", ""))
                    self._materialized_contexts[key] = row

        overlay_path = (
            self.project_root 
            / "knowledge_sources" / "generated" / "overlays"
            / "qb_knowledge_overlay.csv"
        )
        if overlay_path.exists():
            with overlay_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("entry_type") == "concept_alias":
                        self._knowledge_overlay[row.get("alias", "")] = row.get("canonical_concept_id", "")

    def resolve_field(self, qb_table: str, qb_field: str) -> Optional[ConceptInfo]:
        """Resolve QB field to canonical concept info.
        
        Args:
            qb_table: QB table name (e.g., "Customer", "Invoice")
            qb_field: QB field name (e.g., "FullName", "DueDate")
        
        Returns:
            ConceptInfo dict with concept_id, confidence, source, or None if not found.
        """
        key = (qb_table, qb_field)
        
        # Check materialized contexts first (high confidence)
        if key in self._materialized_contexts:
            ctx = self._materialized_contexts[key]
            confidence = "high" if "direct" in ctx.get("note", "") else "medium"
            return ConceptInfo(
                concept_id=ctx.get("concept_id", ""),
                confidence=confidence,
                source="materialized_context",
                qb_table=qb_table,
                qb_field=qb_field,
                description=ctx.get("field_description", ""),
            )
        
        # Check knowledge overlay (indexed)
        if qb_field in self._knowledge_overlay:
            return ConceptInfo(
                concept_id=self._knowledge_overlay[qb_field],
                confidence="medium",
                source="knowledge_overlay",
                qb_table=qb_table,
                qb_field=qb_field,
                description="",
            )
        
        return None

    def list_module_fields(self, module: str) -> list[dict[str, str]]:
        """List all QB fields in a given module with their canonical mappings.
        
        Args:
            module: QB module code (AR, AP, GL, INV, PAY, RPT)
        
        Returns:
            List of field info dicts with table, field, concept_id, confidence.
        """
        results = []
        for (table, field), ctx in self._materialized_contexts.items():
            if ctx.get("category", "") == module:
                confidence = "high" if "direct" in ctx.get("note", "") else "medium"
                results.append({
                    "table": table,
                    "field": field,
                    "concept_id": ctx.get("concept_id", ""),
                    "confidence": confidence,
                    "description": ctx.get("field_description", ""),
                })
        return results

    def list_modules(self) -> dict[str, int]:
        """List all QB modules with field count.
        
        Returns:
            Dict mapping module code to field count.
        """
        module_count: dict[str, int] = {}
        for ctx in self._materialized_contexts.values():
            module = ctx.get("category", "General")
            module_count[module] = module_count.get(module, 0) + 1
        return module_count


class QBModuleTaxonomy:
    """QuickBooks module classification and domain mapping."""

    MODULE_TO_DOMAIN = {
        "AR": "Accounts Receivable",
        "AP": "Accounts Payable",
        "GL": "General Ledger",
        "INV": "Inventory",
        "PAY": "Payroll",
        "RPT": "Reporting",
    }

    MODULE_DESCRIPTION = {
        "AR": "Customer invoices, receipts, credit memos, payments",
        "AP": "Vendor bills, payments, purchase orders",
        "GL": "Journal entries, accounts, financial reports",
        "INV": "Items, inventory adjustments, assemblies",
        "PAY": "Employees, payroll, wages, taxes",
        "RPT": "Financial reports, dashboards, analytics",
    }

    @classmethod
    def get_domain(cls, module: str) -> str:
        """Get business domain for QB module."""
        return cls.MODULE_TO_DOMAIN.get(module, "General")

    @classmethod
    def get_description(cls, module: str) -> str:
        """Get description for QB module."""
        return cls.MODULE_DESCRIPTION.get(module, "")


def example_usage():
    """Show example QB entity mapping pattern."""
    resolver = QBEntityResolver()
    
    # Resolve a single field
    info = resolver.resolve_field("Customer", "FullName")
    if info:
        print(f"Customer.FullName → {info['concept_id']} (confidence: {info['confidence']})")
    
    # List all AR fields with mappings
    ar_fields = resolver.list_module_fields("AR")
    print(f"\nAR module has {len(ar_fields)} materialized fields")
    for field_info in ar_fields[:3]:
        print(f"  {field_info['table']}.{field_info['field']} → {field_info['concept_id']}")
    
    # Get module summary
    modules = resolver.list_modules()
    print(f"\nQB modules: {modules}")


if __name__ == "__main__":
    example_usage()
