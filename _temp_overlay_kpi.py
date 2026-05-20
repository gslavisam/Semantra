import subprocess, sys, csv, os
from datetime import datetime

# Adjust working directory to ensures we are in Semantra folder if needed, 
# but the shell should already be there.

def read_summary(path):
    if not os.path.exists(path):
        return {}
    res = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                res[row[0]] = row[1]
    return res

try:
    # 1. Run baseline audit
    subprocess.run([sys.executable, "support/sap/run_sap_full_coverage_exercise.py", "--mode", "audit"], check=True, capture_output=True)
    baseline = read_summary("knowledge_sources/generated/runtime/sap/sap_full_coverage_exercise_summary.csv")

    # 2. Load overlay payload
    payload_path = "knowledge_sources/generated/runtime/sap/sap_unmapped_auto_enrichment_aggressive_fi_mm_overlay.csv"
    with open(payload_path, "rb") as f:
        payload = f.read()

    # 3. Backend operations
    from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
    from app.services.persistence_service import persistence_service
    from app.services.metadata_knowledge_service import metadata_knowledge_service

    validation = knowledge_overlay_validation_service.validate_csv_payload(payload, "sap_unmapped_auto_enrichment_aggressive_fi_mm_overlay.csv")
    if validation.invalid_rows > 0:
        print(f"Validation failed: {validation.invalid_rows} invalid rows")
        sys.exit(1)

    prev_overlay = persistence_service.get_active_knowledge_overlay_version()
    prev_id = prev_overlay.id if prev_overlay else "none"
    prev_name = prev_overlay.name if prev_overlay else "none"

    new_name = f"sap-auto-aggressive-fi-mm-{datetime.utcnow():%Y%m%d%H%M%S}"
    new_version = persistence_service.create_knowledge_overlay_version(name=new_name, created_by="copilot")
    new_id = new_version.id

    entries = [r for r in validation.normalized_preview if r.get("status") == "valid"]
    persistence_service.save_knowledge_overlay_entries(new_id, entries)
    persistence_service.activate_knowledge_overlay_version(new_id)

    metadata_knowledge_service.refresh()

    # 4. Run post audit
    subprocess.run([sys.executable, "support/sap/run_sap_full_coverage_exercise.py", "--mode", "audit"], check=True, capture_output=True)
    post = read_summary("knowledge_sources/generated/runtime/sap/sap_full_coverage_exercise_summary.csv")

    # 5. Print results
    def get_val(d, k):
        v = d.get(k, "0")
        try:
            return float(v) if "." in v else int(v)
        except:
            return 0

    metrics = ["mapped_strict", "mapped_strong", "mapped_with_review", "coverage_any_path", "knowledge_only", "unmapped"]

    print(f"PREVIOUS_ACTIVE_OVERLAY_ID={prev_id}")
    print(f"PREVIOUS_ACTIVE_OVERLAY_NAME={prev_name}")
    print(f"NEW_OVERLAY_ID={new_id}")
    print(f"NEW_OVERLAY_NAME={new_name}")
    print(f"NEW_OVERLAY_ENTRIES={len(entries)}")

    for m in metrics:
        print(f"BASELINE_{m}={baseline.get(m, '0')}")
    for m in metrics:
        print(f"POST_{m}={post.get(m, '0')}")
    for m in metrics:
        b = get_val(baseline, m)
        p = get_val(post, m)
        diff = p - b
        if isinstance(diff, float):
            print(f"DELTA_{m}={diff:.4f}")
        else:
            print(f"DELTA_{m}={diff}")

    curr_overlay = persistence_service.get_active_knowledge_overlay_version()
    print(f"CURRENT_ACTIVE_OVERLAY_ID={curr_overlay.id if curr_overlay else 'none'}")
    print(f"CURRENT_ACTIVE_OVERLAY_NAME={curr_overlay.name if curr_overlay else 'none'}")

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
