CREATE TABLE product_dim (
    material_id VARCHAR(40),
    engineering_part_number VARCHAR(40),
    material_type_code VARCHAR(10),
    material_group_id VARCHAR(20),
    material_description VARCHAR(120),
    base_uom_code VARCHAR(10),
    gross_weight DECIMAL(10,3),
    net_weight DECIMAL(10,3),
    weight_unit_code VARCHAR(5),
    created_date DATE,
    batch_managed_flag BOOLEAN,
    deletion_mark BOOLEAN
);

CREATE TABLE product_text (
    material_id VARCHAR(40),
    language_code VARCHAR(2),
    short_description VARCHAR(120),
    long_description VARCHAR(255),
    search_keywords VARCHAR(255)
);
