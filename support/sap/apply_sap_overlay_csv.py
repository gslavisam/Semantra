"""Apply a generated SAP overlay CSV as a persisted knowledge overlay version.

This utility validates a CSV payload with the same rules as the API,
persists a new overlay version, stores rows, and optionally activates it.

Example:
    python support/sap/apply_sap_overlay_csv.py \
        --overlay-csv knowledge_sources/generated/runtime/sap/sap_unmapped_auto_enrichment_aggressive_sd_pp_overlay.csv \
        --name sap-auto-aggressive-sd-pp
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist and optionally activate a SAP overlay CSV.")
    parser.add_argument(
        "--overlay-csv",
        type=Path,
        required=True,
        help="Path to overlay CSV (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Optional overlay version name. If empty, name is derived from file stem and timestamp.",
    )
    parser.add_argument(
        "--created-by",
        default="sap-overlay-cli",
        help="Audit identity stored on the overlay version.",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Persist as validated overlay but do not activate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    overlay_path = args.overlay_csv
    if not overlay_path.is_absolute():
        overlay_path = (PROJECT_ROOT / overlay_path).resolve()
    if not overlay_path.exists():
        raise FileNotFoundError(f"Overlay CSV not found: {overlay_path}")

    payload = overlay_path.read_bytes()
    validation = knowledge_overlay_validation_service.validate_csv_payload(payload, filename=overlay_path.name)
    print(f"validation_total_rows={validation.total_rows}")
    print(f"validation_valid_rows={validation.valid_rows}")
    print(f"validation_invalid_rows={validation.invalid_rows}")
    print(f"validation_warnings={validation.warnings}")

    if validation.invalid_rows > 0:
        print("status=validation_failed")
        for row in validation.normalized_preview:
            if row.status != "invalid":
                continue
            for issue in row.issues:
                if issue.severity == "error":
                    print(f"error_row={row.row_number} code={issue.code} message={issue.message}")
        raise SystemExit(1)

    now_token = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    overlay_name = (args.name or "").strip() or f"{overlay_path.stem}-{now_token}"

    previous_active = persistence_service.get_active_knowledge_overlay_version()

    version = persistence_service.save_knowledge_overlay_version(
        name=overlay_name,
        status="validated",
        created_by=(args.created_by or "").strip() or None,
        source_filename=overlay_path.name,
    )
    entries = [
        knowledge_overlay_validation_service.build_entry(row)
        for row in validation.normalized_preview
        if row.status == "valid"
    ]
    persistence_service.save_knowledge_overlay_entries(version.overlay_id, entries)

    if args.no_activate:
        metadata_knowledge_service.refresh()
        print(f"overlay_id={version.overlay_id}")
        print(f"overlay_name={version.name}")
        print(f"saved_entries={len(entries)}")
        print("activated=false")
        return

    persistence_service.activate_knowledge_overlay_version(version.overlay_id)
    metadata_knowledge_service.refresh()
    current_active = persistence_service.get_active_knowledge_overlay_version()

    print(f"previous_active_id={previous_active.overlay_id if previous_active else 'none'}")
    print(f"previous_active_name={previous_active.name if previous_active else 'none'}")
    print(f"overlay_id={version.overlay_id}")
    print(f"overlay_name={version.name}")
    print(f"saved_entries={len(entries)}")
    print("activated=true")
    print(f"active_id={current_active.overlay_id if current_active else 'none'}")
    print(f"active_name={current_active.name if current_active else 'none'}")


if __name__ == "__main__":
    main()
