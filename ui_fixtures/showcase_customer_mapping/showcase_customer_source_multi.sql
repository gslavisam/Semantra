CREATE TABLE legacy_customer_master (
    legacy_customer_code VARCHAR(32),
    purchaser VARCHAR(120),
    billing_country CHAR(2),
    go_live_date DATE,
    segment_label VARCHAR(40),
    annual_spend_usd DECIMAL(14,2)
);

CREATE TABLE legacy_customer_contact (
    legacy_customer_code VARCHAR(32),
    primary_contact_email VARCHAR(255),
    main_phone VARCHAR(32),
    escalation_contact VARCHAR(120),
    contact_language CHAR(2),
    contact_opt_in BOOLEAN
);
