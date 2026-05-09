CREATE TABLE customer_dim (
    customer_id VARCHAR(20),
    customer_name VARCHAR(120),
    country_code VARCHAR(5),
    city_name VARCHAR(80),
    phone_number VARCHAR(40)
);

CREATE TABLE customer_sales_area_dim (
    customer_id VARCHAR(20),
    sales_organization_id VARCHAR(10),
    distribution_channel_id VARCHAR(10),
    division_id VARCHAR(10),
    customer_group_id VARCHAR(10),
    sales_district_id VARCHAR(10),
    shipping_condition_code VARCHAR(10),
    incoterm_code VARCHAR(10),
    incoterm_location VARCHAR(80),
    document_currency_code VARCHAR(5),
    payment_terms_id VARCHAR(10),
    customer_pricing_procedure_code VARCHAR(10),
    price_list_type_id VARCHAR(10)
);
