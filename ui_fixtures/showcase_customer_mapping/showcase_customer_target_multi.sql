CREATE TABLE customer_dim (
    account_id VARCHAR(32),
    customer_name VARCHAR(120),
    country_iso CHAR(2),
    created_date DATE,
    customer_segment VARCHAR(40),
    annual_revenue_usd DECIMAL(14,2)
);

CREATE TABLE customer_contact (
    account_id VARCHAR(32),
    email_address VARCHAR(255),
    phone_number VARCHAR(32),
    support_contact_name VARCHAR(120),
    language_code CHAR(2),
    marketing_opt_in BOOLEAN
);
