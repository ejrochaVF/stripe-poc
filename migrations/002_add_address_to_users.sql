-- ============================================================
-- Migration: Add billing address columns to the `users` table
-- Database:  stripepoc  (MySQL 8+)
-- ============================================================

USE stripepoc;

ALTER TABLE users
    ADD COLUMN address_name        VARCHAR(255) NULL AFTER password_hash,
    ADD COLUMN address_line1       VARCHAR(255) NULL AFTER address_name,
    ADD COLUMN address_line2       VARCHAR(255) NULL AFTER address_line1,
    ADD COLUMN address_city        VARCHAR(255) NULL AFTER address_line2,
    ADD COLUMN address_state       VARCHAR(255) NULL AFTER address_city,
    ADD COLUMN address_postal_code VARCHAR(20)  NULL AFTER address_state,
    ADD COLUMN address_country     VARCHAR(2)   NULL AFTER address_postal_code;
