CREATE TABLE purchasing_info_record_dim (
    purchasing_info_record_id VARCHAR(20),
    supplier_id VARCHAR(20),
    material_id VARCHAR(40),
    purchasing_organization_id VARCHAR(10),
    plant_id VARCHAR(10),
    info_category_code VARCHAR(5),
    net_price_amount DECIMAL(14,2),
    currency_code VARCHAR(5),
    price_unit_quantity DECIMAL(14,2),
    minimum_order_quantity DECIMAL(14,2),
    planned_delivery_days INTEGER,
    incoterm_code VARCHAR(10),
    incoterm_location VARCHAR(80),
    order_unit_code VARCHAR(10)
);

CREATE TABLE purchasing_info_record_status (
    purchasing_info_record_id VARCHAR(20),
    deletion_mark BOOLEAN,
    source_list_required BOOLEAN,
    release_status_code VARCHAR(10)
);
