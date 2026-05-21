from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def read_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    summary: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) >= 2:
                summary[row[0]] = row[1]
    return summary


try:
    summary_path = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_full_coverage_exercise_summary.csv"
    overlay_path = PROJECT_ROOT / "knowledge_sources" / "generated" / "runtime" / "sap" / "sap_unmapped_auto_enrichment_aggressive_fi_mm_overlay.csv"

    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "support" / "sap" / "run_sap_full_coverage_exercise.py"), "--mode", "audit"],
        check=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
    )
    baseline = read_summary(summary_path)

    payload = overlay_path.read_bytes()

    from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
    from app.services.metadata_knowledge_service import metadata_knowledge_service
    from app.services.persistence_service import persistence_service

    validation = knowledge_overlay_validation_service.validate_csv_payload(payload, overlay_path.name)
    if validation.invalid_rows > 0:
        print(f"Validation failed: {validation.invalid_rows} invalid rows")
        sys.exit(1)

    prev_overlay = persistence_service.get_active_knowledge_overlay_version()
    prev_id = prev_overlay.id if prev_overlay else "none"
    prev_name = prev_overlay.name if prev_overlay else "none"

    new_name = f"sap-auto-aggressive-fi-mm-{datetime.utcnow():%Y%m%d%H%M%S}"
    new_version = persistence_service.create_knowledge_overlay_version(name=new_name, created_by="copilot")
    new_id = new_version.id

    entries = [row for row in validation.normalized_preview if row.get("status") == "valid"]
    persistence_service.save_knowledge_overlay_entries(new_id, entries)
    persistence_service.activate_knowledge_overlay_version(new_id)

    metadata_knowledge_service.refresh()

    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "support" / "sap" / "run_sap_full_coverage_exercise.py"), "--mode", "audit"],
        check=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
    )
    post = read_summary(summary_path)

    def get_val(values: dict[str, str], key: str) -> float | int:
        raw_value = values.get(key, "0")
        try:
            return float(raw_value) if "." in raw_value else int(raw_value)
        except Exception:
            return 0

    metrics = ["mapped_strict", "mapped_strong", "mapped_with_review", "coverage_any_path", "knowledge_only", "unmapped"]

    print(f"PREVIOUS_ACTIVE_OVERLAY_ID={prev_id}")
    print(f"PREVIOUS_ACTIVE_OVERLAY_NAME={prev_name}")
    print(f"NEW_OVERLAY_ID={new_id}")
    print(f"NEW_OVERLAY_NAME={new_name}")
    print(f"NEW_OVERLAY_ENTRIES={len(entries)}")

    for metric in metrics:
        print(f"BASELINE_{metric}={baseline.get(metric, '0')}")
    for metric in metrics:
        print(f"POST_{metric}={post.get(metric, '0')}")
    for metric in metrics:
        baseline_value = get_val(baseline, metric)
        post_value = get_val(post, metric)
        diff = post_value - baseline_value
        if isinstance(diff, float):
            print(f"DELTA_{metric}={diff:.4f}")
        else:
            print(f"DELTA_{metric}={diff}")

    curr_overlay = persistence_service.get_active_knowledge_overlay_version()
    print(f"CURRENT_ACTIVE_OVERLAY_ID={curr_overlay.id if curr_overlay else 'none'}")
    print(f"CURRENT_ACTIVE_OVERLAY_NAME={curr_overlay.name if curr_overlay else 'none'}")

except Exception:
    import traceback

    traceback.print_exc()
    sys.exit(1)