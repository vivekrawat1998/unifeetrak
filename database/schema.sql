-- =============================================================================
-- University Fee Tracking System — Database Schema
-- =============================================================================
-- Tables
--   1. students  — master student registry
--   2. fees      — one payment row per (student × month × year)
--
-- Relationship: fees.student_id  →  students.student_id  (many-to-one)
-- =============================================================================


-- ---------------------------------------------------------------------------
-- TABLE 1: students
-- Basic details as required by the assignment.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    student_id   SERIAL        PRIMARY KEY,                -- auto-increment PK
    name         VARCHAR(150)  NOT NULL,                   -- full name
    roll_number  VARCHAR(50)   NOT NULL UNIQUE,            -- unique roll number
    batch_name   VARCHAR(100)  NOT NULL,                   -- e.g. "2025 – Aug - B.Tech CSE"
    semester     VARCHAR(50)   NOT NULL,                   -- e.g. "B.Tech CSE – Sem 1"
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_students_batch    ON students(batch_name);
CREATE INDEX IF NOT EXISTS idx_students_semester ON students(semester);
CREATE INDEX IF NOT EXISTS idx_students_roll     ON students(roll_number);


-- ---------------------------------------------------------------------------
-- TABLE 2: fees
-- Tracks monthly payments. One row per student per month/year.
-- Missing row = Unpaid. Existing row = Paid.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fees (
    fee_id        SERIAL          PRIMARY KEY,
    student_id    INT             NOT NULL
                      REFERENCES students(student_id)
                      ON DELETE CASCADE,                   -- cascade delete if student removed
    month         SMALLINT        NOT NULL CHECK (month BETWEEN 1 AND 12),
    year          SMALLINT        NOT NULL CHECK (year  BETWEEN 2000 AND 2100),
    amount_paid   NUMERIC(10, 2)  NOT NULL DEFAULT 0.00,
    payment_date  DATE,                                    -- NULL until received
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Enforce one fee record per student per calendar month
    CONSTRAINT uq_fee_per_student_month UNIQUE (student_id, month, year)
);

CREATE INDEX IF NOT EXISTS idx_fees_month_year    ON fees(month, year);
CREATE INDEX IF NOT EXISTS idx_fees_student_month ON fees(student_id, month, year);


-- ---------------------------------------------------------------------------
-- Migration: safely add updated_at if this DB was created before it existed.
-- Uses a DO block so it is fully idempotent — safe on every app restart.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE  table_name = 'fees' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE fees
            ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        RAISE NOTICE 'fees.updated_at column added.';
    END IF;
END$$;


-- ---------------------------------------------------------------------------
-- Trigger: auto-stamp updated_at on every UPDATE to fees
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fees_updated_at ON fees;
CREATE TRIGGER trg_fees_updated_at
    BEFORE UPDATE ON fees
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
