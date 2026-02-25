-- ============================================================
-- Migration: Create the `users` table for authentication
-- Database:  stripepoc  (MySQL 8+)
-- ============================================================

CREATE DATABASE IF NOT EXISTS stripepoc
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE stripepoc;

CREATE TABLE IF NOT EXISTS users (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    email               VARCHAR(255)  NOT NULL,
    password_hash       VARCHAR(255)  NOT NULL,
    address_name        VARCHAR(255)  NULL,
    address_line1       VARCHAR(255)  NULL,
    address_line2       VARCHAR(255)  NULL,
    address_city        VARCHAR(255)  NULL,
    address_state       VARCHAR(255)  NULL,
    address_postal_code VARCHAR(20)   NULL,
    address_country     VARCHAR(2)    NULL,
    created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE INDEX uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
