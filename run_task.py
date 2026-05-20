import os
import sys
import pandas as pd
import datetime as dt
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
from app.services.persistence_service import persistence_service
from app.services.metadata_knowledge_service import metadata_knowledge_service

SUMMARY_PATH = 'knowledge_sources/generated/runtime/sap/sap_full_coverage_exercise_summary.csv'
OVERLAY_PATH = 'knowledge_sources/generated/runtime/sap/sap_unmapped_auto_enrichment_aggressive_sd_pp_overlay.csv'
KEYS = ['mapped_strict', 'mapped_strong', 'mapped_with_review', 'coverage_any_path', 'knowledge_only', 'unmapped']

def read_summary():
    df = pd.read_csv(SUMMARY_PATH)
    d = df.set_index('metric')['value'].to_dict()
    return {k: int(float(d.get(k, 0))) for k in KEYS}

def build_entry(row):
    # Mapping KnowledgeOverlayValidationPreviewRow fields to KnowledgeOverlayEntry fields
    # As defined in KnowledgeOverlayEntry(BaseModel)
    return {
        'entry_type': row.entry_type or 'field_alias',
        'canonical_term': row.canonical_term,
        'canonical_concept_id': row.canonical_concept_id,
        'alias': row.alias,
        'domain': row.domain,
        'source_system': row.source_system,
        'note': row.note,
        'normalized_canonical_term': row.normalized_canonical_term or row.canonical_term.lower() if row.canonical_term else '',
        'normalized_alias': row.normalized_alias or row.alias.lower() if row.alias else ''
    }

# 2) Read PRE
pre = read_summary()
for k, v in pre.items():
    print(f'PRE_{k}={v}')

# 3) Activate Overlay
with open(OVERLAY_PATH, 'rb') as f:
    payload = f.read()

validation = knowledge_overlay_validation_service.validate_csv_payload(payload, 'sap_unmapped_auto_enrichment_aggressive_sd_pp_overlay.csv')
if validation.invalid_rows > 0:
    print(f'ERROR: {validation.invalid_rows} invalid rows found.')
    sys.exit(1)

prev_version = persistence_service.get_active_knowledge_overlay_version()
if prev_version:
    print(f'PREV_ACTIVE_ID={prev_version.overlay_id}')
    print(f'PREV_ACTIVE_NAME={prev_version.name}')
else:
    print('PREV_ACTIVE_ID=None')
    print('PREV_ACTIVE_NAME=None')

timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
new_name = f'sap-auto-aggressive-sd-pp-{timestamp}'
# persistence_service.save_knowledge_overlay_version returns the created object or id? 
# Usually save_* returns something with id. 
# In KnowledgeOverlayVersion it is 'overlay_id'.
new_version = persistence_service.save_knowledge_overlay_version(
    name=new_name,
    status='validated',
    created_by='copilot',
    source_filename='sap_unmapped_auto_enrichment_aggressive_sd_pp_overlay.csv'
)

# If it returns the model instance/dict:
new_id = getattr(new_version, 'overlay_id', new_version)

valid_entries = 0
for row in validation.normalized_preview:
    if row.status == 'valid':
        entry_dict = build_entry(row)
        persistence_service.save_knowledge_overlay_entry(new_id, entry_dict)
        valid_entries += 1

persistence_service.activate_knowledge_overlay_version(new_id)
metadata_knowledge_service.refresh_metadata()

active_version = persistence_service.get_active_knowledge_overlay_version()
print(f'NEW_ID={new_id}')
print(f'NEW_NAME={new_name}')
print(f'NEW_ENTRIES={valid_entries}')
print(f'ACTIVE_ID={active_version.overlay_id}')
print(f'ACTIVE_NAME={active_version.name}')

# 4) Run Audit
import subprocess
print('Running audit...')
subprocess.run([sys.executable, 'support/sap/run_sap_full_coverage_exercise.py', '--mode', 'audit'], check=True)

# 5) Read POST
post = read_summary()
for k, v in post.items():
    print(f'POST_{k}={v}')

# 6) Print DELTA
for k in KEYS:
    print(f'DELTA_{k}={post[k] - pre[k]}')
