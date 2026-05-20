import sys
import os
import csv

# Add backend to path
sys.path.append('backend')

from app.services.mapping_service import generate_mapping_candidates

target_header = "purchasing_info_record_id,supplier_id,material_id,purchasing_organization_id,plant_id,info_category_code,net_price_amount,currency_code,price_unit_quantity,minimum_order_quantity,planned_delivery_days,incoterm_code,incoterm_location,order_unit_code"
target_schema = target_header.split(',')

source_fields = ["INFNR", "ESOKZ", "PEINH", "MINBM", "APLFZ", "BPRME", "NETPR"]

# Dummy schema for generation
source_schema = source_fields

results = generate_mapping_candidates(source_schema, target_schema)

print("source,expected,predicted,confidence,label")
# Map of expected manually based on knowledge of the fields
expected_map = {
    "INFNR": "purchasing_info_record_id",
    "ESOKZ": "info_category_code",
    "PEINH": "price_unit_quantity",
    "MINBM": "minimum_order_quantity",
    "APLFZ": "planned_delivery_days",
    "BPRME": "order_unit_code",
    "NETPR": "net_price_amount"
}

for match in results.get('matches', []):
    src = match.get('source_field')
    if src in source_fields:
        predicted = match.get('target_field')
        confidence = match.get('confidence', 0)
        expected = expected_map.get(src, '')
        label = "MATCH" if predicted == expected else "MISS"
        print(f"{src},{expected},{predicted},{confidence},{label}")
