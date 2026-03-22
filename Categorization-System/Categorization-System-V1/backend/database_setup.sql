-- Database setup script for Finance Data Normalization and Categorization System
-- Run this in PostgreSQL to create the required tables

-- Create database (run this as postgres superuser)
-- CREATE DATABASE finance_dashboard;

-- Connect to finance_dashboard database and run the following:

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(50),
    type VARCHAR(20) CHECK (type IN ('income', 'expense')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'categories_name_unique'
    ) THEN
        ALTER TABLE categories
            ADD CONSTRAINT categories_name_unique UNIQUE(name);
    END IF;
END $$;

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    note TEXT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert some sample categories
INSERT INTO categories (name, type) VALUES
('Salary', 'income'),
('Freelance', 'income'),
('Investments', 'income'),
('Food & Dining', 'expense'),
('Transportation', 'expense'),
('Entertainment', 'expense'),
('Utilities', 'expense'),
('Healthcare', 'expense')
ON CONFLICT (name) DO NOTHING;

-- Categories keywords rules
CREATE TABLE IF NOT EXISTS category_keywords (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    keyword VARCHAR(100) NOT NULL,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 2: extend keyword rules for mixed matching and soft-delete lifecycle
ALTER TABLE category_keywords
    ADD COLUMN IF NOT EXISTS match_type VARCHAR(20) DEFAULT 'substring',
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'category_keywords_match_type_check'
    ) THEN
        ALTER TABLE category_keywords
            ADD CONSTRAINT category_keywords_match_type_check
            CHECK (match_type IN ('substring', 'word_boundary', 'exact'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_category_keywords_active_priority
ON category_keywords (category_id, is_active, priority, id);

CREATE INDEX IF NOT EXISTS idx_category_keywords_keyword_lower
ON category_keywords (LOWER(keyword));

-- Add partial unique index to enforce uniqueness only on active keywords
-- This enables soft-delete semantics: deleted keywords can be recreated
DO $$
BEGIN
    -- Drop old constraint if it exists (for migration)
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'category_keyword_unique'
    ) THEN
        ALTER TABLE category_keywords
            DROP CONSTRAINT category_keyword_unique;
    END IF;
    
    -- Create partial unique index (only active keywords)
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE indexname = 'idx_active_keywords'
    ) THEN
        CREATE UNIQUE INDEX idx_active_keywords
        ON category_keywords(category_id, keyword)
        WHERE is_active = TRUE;
    END IF;
END $$;

-- Seed rule defaults for old rows
UPDATE category_keywords
SET match_type = COALESCE(match_type, 'substring'),
    is_active = COALESCE(is_active, TRUE),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP);

-- Insert sample keywords using dynamic category lookup (stable, name-based)
-- This approach is safer than hard-coded category IDs: if categories are reordered or new ones added,
-- keywords will still point to the correct categories by name
-- Idempotency: wrapped in a transaction that only inserts if the keyword is not already active
INSERT INTO category_keywords (category_id, keyword, priority, match_type, is_active)
SELECT c.id, 'restaurant', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Food & Dining' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'restaurant' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'coffee', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Food & Dining' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'coffee' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'cafe', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Food & Dining' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'cafe' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'indomaret', 2, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Food & Dining' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'indomaret' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'alfamart', 2, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Food & Dining' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'alfamart' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'grab', 2, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Transportation' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'grab' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'uber', 2, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Transportation' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'uber' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'taxi', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Transportation' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'taxi' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'fuel', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Transportation' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'fuel' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'bus', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Transportation' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'bus' AND ckw.is_active = TRUE
  )
UNION ALL
SELECT c.id, 'bpjs', 1, 'substring', TRUE 
FROM categories c 
WHERE c.name = 'Healthcare' AND c.type = 'expense'
  AND NOT EXISTS (
    SELECT 1 FROM category_keywords ckw 
    WHERE ckw.category_id = c.id AND LOWER(TRIM(ckw.keyword)) = 'bpjs' AND ckw.is_active = TRUE
  );

-- Phase 2 observability table for import-time classifier outcomes
CREATE TABLE IF NOT EXISTS transaction_classification_log (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    note_hash VARCHAR(64),
    amount DECIMAL(10,2),
    transaction_type VARCHAR(10) CHECK (transaction_type IN ('income', 'expense')) NOT NULL,
    phase_matched INTEGER CHECK (phase_matched IN (1, 2, 3)) NOT NULL,
    resolution_path VARCHAR(50) CHECK (
        resolution_path IN ('keyword_match', 'category_name_match', 'error_no_match')
    ) NOT NULL,
    matched_keyword VARCHAR(100),
    matched_category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    matched_category_name VARCHAR(100),
    match_type VARCHAR(20),
    priority INTEGER,
    tie_break_info TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'classification_log_match_type_check'
    ) THEN
        ALTER TABLE transaction_classification_log
            ADD CONSTRAINT classification_log_match_type_check
            CHECK (match_type IS NULL OR match_type IN ('substring', 'word_boundary', 'exact'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_classification_log_transaction_id
ON transaction_classification_log (transaction_id);

CREATE INDEX IF NOT EXISTS idx_classification_log_created_at
ON transaction_classification_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_classification_log_category_created
ON transaction_classification_log (matched_category_id, created_at DESC);

-- Phase 3: classification context versioning for immediate in-memory cache invalidation
CREATE TABLE IF NOT EXISTS classification_context_version (
  id SERIAL PRIMARY KEY,
  version_number INTEGER NOT NULL,
  reason VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_classification_context_version_number
ON classification_context_version (version_number);

INSERT INTO classification_context_version (version_number, reason)
SELECT 0, 'bootstrap'
WHERE NOT EXISTS (SELECT 1 FROM classification_context_version);

-- Phase 3: global merchant normalization rules (feature-flagged)
CREATE TABLE IF NOT EXISTS merchant_normalization_rules (
  id SERIAL PRIMARY KEY,
  pattern VARCHAR(200) NOT NULL,
  replacement VARCHAR(200) NOT NULL DEFAULT '',
  match_type VARCHAR(20) NOT NULL DEFAULT 'substring',
  priority INTEGER NOT NULL DEFAULT 1,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'merchant_normalization_rules_match_type_check'
  ) THEN
    ALTER TABLE merchant_normalization_rules
      ADD CONSTRAINT merchant_normalization_rules_match_type_check
      CHECK (match_type IN ('substring', 'word_boundary', 'exact'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_merchant_normalization_rules_active_priority
ON merchant_normalization_rules (is_active, priority, id);

CREATE INDEX IF NOT EXISTS idx_merchant_normalization_rules_pattern_lower
ON merchant_normalization_rules (LOWER(pattern));