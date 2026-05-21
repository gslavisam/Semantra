from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service


SUMMARY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_coverage_exercise_summary.csv"
OVERLAY_PATH = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_unmapped_auto_enrichment_aggressive_sd_pp_overlay.csv"
KEYS = ["mapped_strict", "mapped_strong", "mapped_with_review", "coverage_any_path", "knowledge_only", "unmapped"]


def read_summary() -> dict[str, int]:
    df = pd.read_csv(SUMMARY_PATH)
    metrics = df.set_index("metric")["value"].to_dict()
    return {key: int(float(metrics.get(key, 0))) for key in KEYS}


def build_entry(row) -> dict[str, str]:
    return {
        "entry_type": row.entry_type or "field_alias",
        "canonical_term": row.canonical_term,
        "canonical_concept_id": row.canonical_concept_id,
        "alias": row.alias,
        "domain": row.domain,
        "source_system": row.source_system,
        "note": row.note,
        "normalized_canonical_term": row.normalized_canonical_term or (row.canonical_term.lower() if row.canonical_term else ""),
        "normalized_alias": row.normalized_alias or (row.alias.lower() if row.alias else ""),
    }


pre = read_summary()
for key, value in pre.items():
    print(f"PRE_{key}={value}")

payload = OVERLAY_PATH.read_bytes()
validation = knowledge_overlay_validation_service.validate_csv_payload(payload, OVERLAY_PATH.name)
if validation.invalid_rows > 0:
    print(f"ERROR: {validation.invalid_rows} invalid rows found.")
    sys.exit(1)

prev_version = persistence_service.get_active_knowledge_overlay_version()
if prev_version:
    print(f"PREV_ACTIVE_ID={prev_version.overlay_id}")
    print(f"PREV_ACTIVE_NAME={prev_version.name}")
else:
    print("PREV_ACTIVE_ID=None")
    print("PREV_ACTIVE_NAME=None")

timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
new_name = f"sap-auto-aggressive-sd-pp-{timestamp}"
new_version = persistence_service.save_knowledge_overlay_version(
    name=new_name,
    status="validated",
    created_by="copilot",
    source_filename=OVERLAY_PATH.name,
)

new_id = getattr(new_version, "overlay_id", new_version)

valid_entries = 0
for row in validation.normalized_preview:
    if row.status == "valid":
        persistence_service.save_knowledge_overlay_entry(new_id, build_entry(row))
        valid_entries += 1

persistence_service.activate_knowledge_overlay_version(new_id)
metadata_knowledge_service.refresh_metadata()

active_version = persistence_service.get_active_knowledge_overlay_version()
print(f"NEW_ID={new_id}")
print(f"NEW_NAME={new_name}")
print(f"NEW_ENTRIES={valid_entries}")
print(f"ACTIVE_ID={active_version.overlay_id}")
print(f"ACTIVE_NAME={active_version.name}")

print("Running audit...")
subprocess.run(
    [sys.executable, str(PROJECT_ROOT / "support" / "sap" / "run_sap_full_coverage_exercise.py"), "--mode", "audit"],
    check=True,
    cwd=PROJECT_ROOT,
)

post = read_summary()
for key, value in post.items():
    print(f"POST_{key}={value}")

for key in KEYS:
    print(f"DELTA_{key}={post[key] - pre[key]}")