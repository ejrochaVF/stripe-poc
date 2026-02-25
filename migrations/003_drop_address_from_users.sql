-- Migration 003: Drop billing address columns from users table.
-- Billing address is now collected exclusively by Stripe Checkout.

ALTER TABLE users
    DROP COLUMN address_name,
    DROP COLUMN address_line1,
    DROP COLUMN address_line2,
    DROP COLUMN address_city,
    DROP COLUMN address_state,
    DROP COLUMN address_postal_code,
    DROP COLUMN address_country;
