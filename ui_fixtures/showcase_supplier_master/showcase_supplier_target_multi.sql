CREATE TABLE supplier_dim (
    supplier_id VARCHAR(20),
    supplier_group_id VARCHAR(10),
    supplier_name VARCHAR(120),
    country_code VARCHAR(5),
    region_code VARCHAR(10),
    city_name VARCHAR(80),
    postal_code VARCHAR(20),
    street_address VARCHAR(120),
    tax_id_number VARCHAR(20),
    phone_number VARCHAR(40),
    posting_block_flag BOOLEAN,
    deletion_mark BOOLEAN
);

CREATE TABLE supplier_finance (
    supplier_id VARCHAR(20),
    company_code VARCHAR(10),
    reconciliation_account VARCHAR(20),
    payment_terms_id VARCHAR(10),
    payment_method_code VARCHAR(20),
    evaluated_receipt_settlement BOOLEAN
);
