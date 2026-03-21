-- Database setup script for Finance Dashboard
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

-- Add unique constraint to prevent duplicate keyword/category pairs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'category_keyword_unique'
    ) THEN
        ALTER TABLE category_keywords
            ADD CONSTRAINT category_keyword_unique UNIQUE(category_id, keyword);
    END IF;
END $$;

-- Insert sample keywords using dynamic category lookup (stable, name-based)
-- This approach is safer than hard-coded category IDs: if categories are reordered or new ones added,
-- keywords will still point to the correct categories by name
INSERT INTO category_keywords (category_id, keyword, priority)
SELECT c.id, 'restaurant', 1 FROM categories c WHERE c.name = 'Food & Dining' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'coffee', 1 FROM categories c WHERE c.name = 'Food & Dining' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'cafe', 1 FROM categories c WHERE c.name = 'Food & Dining' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'indomaret', 2 FROM categories c WHERE c.name = 'Food & Dining' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'alfamart', 2 FROM categories c WHERE c.name = 'Food & Dining' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'grab', 2 FROM categories c WHERE c.name = 'Transportation' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'uber', 2 FROM categories c WHERE c.name = 'Transportation' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'taxi', 1 FROM categories c WHERE c.name = 'Transportation' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'fuel', 1 FROM categories c WHERE c.name = 'Transportation' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'bus', 1 FROM categories c WHERE c.name = 'Transportation' AND c.type = 'expense'
UNION ALL
SELECT c.id, 'bpjs', 1 FROM categories c WHERE c.name = 'Healthcare' AND c.type = 'expense'
ON CONFLICT (category_id, keyword) DO NOTHING;