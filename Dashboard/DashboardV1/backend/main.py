from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Dict, Any
import pandas as pd
import json
import csv
import io
from datetime import datetime
import re

import psycopg2

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")  # Keep fallback for now
)

app = FastAPI(title="Data Parser API", version="1.0.0")

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/categories")
async def get_categories():
    """Get all categories from database"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon, type FROM categories ORDER BY name")
        rows = cursor.fetchall()

        categories = []
        for row in rows:
            categories.append({
                "id": row[0],
                "name": row[1],
                "icon": row[2],
                "type": row[3]
            })

        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@app.get("/categories/types")
async def get_category_types():
    """Get distinct category types (income, expense)"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type FROM categories WHERE type IS NOT NULL")
        rows = cursor.fetchall()

        types = [row[0] for row in rows]
        return {"types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category types: {str(e)}")

@app.post("/transactions/import")
async def import_transactions(rows: List[Dict[str, Any]]):
    """Import transactions with validation"""
    try:
        cursor = conn.cursor()

        # First check if we have categories for income and expense types
        cursor.execute("SELECT DISTINCT type FROM categories WHERE type IN ('income', 'expense')")
        existing_types = [row[0] for row in cursor.fetchall()]

        if 'income' not in existing_types or 'expense' not in existing_types:
            raise HTTPException(
                status_code=400,
                detail="You should define category types that do not exist in database first to submit data. Missing: " +
                ", ".join([t for t in ['income', 'expense'] if t not in existing_types])
            )

        # Get all categories for automatic assignment
        cursor.execute("SELECT id, name, type FROM categories ORDER BY name")
        categories = cursor.fetchall()

        # Create lookup dictionaries
        income_categories = {row[0]: row[1] for row in categories if row[2] == 'income'}
        expense_categories = {row[0]: row[1] for row in categories if row[2] == 'expense'}
        category_names = {row[1].lower(): row[0] for row in categories}

        def determine_category_id(amount: float, note: str) -> int:
            """Automatically determine category_id based on amount and note"""
            note_lower = note.lower()

            # Try to match category names in the note
            for cat_name, cat_id in category_names.items():
                if cat_name in note_lower:
                    return cat_id

            # If no keyword match found, raise an error asking user to be more specific
            transaction_type = "income" if amount > 0 else "expense"
            available_cats = list(income_categories.values()) if amount > 0 else list(expense_categories.values())
            raise HTTPException(
                status_code=400,
                detail=f"Cannot automatically determine category for transaction: '{note}' (amount: {amount}). " +
                f"Please include one of these {transaction_type} category names in your transaction note: {', '.join(available_cats)}. " +
                f"Available categories: {', '.join([f'{name} (ID: {id})' for id, name in (income_categories.items() if amount > 0 else expense_categories.items())])}"
            )

        inserted_count = 0
        for r in rows:
            # Validate required fields
            if not r.get("date"):
                raise HTTPException(status_code=400, detail=f"Date is required for transaction: {r}")
            if not r.get("amount") or not isinstance(r.get("amount"), (int, float)):
                raise HTTPException(status_code=400, detail=f"Valid amount is required for transaction: {r}")

            # Use note instead of description
            note = r.get("note") or r.get("description") or ""

            # Automatically determine category_id
            category_id = determine_category_id(r["amount"], note)

            cursor.execute(
                """
                INSERT INTO transactions (date, amount, note, category_id, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    r["date"],
                    r["amount"],
                    note,
                    category_id
                )
            )
            inserted_count += 1

        conn.commit()
        return {"inserted": inserted_count}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to import transactions: {str(e)}")

def parse_csv(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV file using pandas"""
    try:
        df = pd.read_csv(io.BytesIO(file_content), dtype=str)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

def parse_excel(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse Excel file using pandas"""
    try:
        df = pd.read_excel(io.BytesIO(file_content), dtype=str)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {str(e)}")

def parse_json(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse JSON file"""
    try:
        text = file_content.decode('utf-8')
        data = json.loads(text)

        # Handle different JSON structures
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if 'transactions' in data and isinstance(data['transactions'], list):
                return data['transactions']
            else:
                return [data]
        else:
            raise ValueError("Unexpected JSON structure")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON: {str(e)}")

def parse_text(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse text file (tab or comma separated)"""
    try:
        text = file_content.decode('utf-8')
        lines = [line.strip() for line in text.replace('\r', '').split('\n') if line.strip()]

        if not lines:
            return []

        # Detect delimiter
        first_line = lines[0]
        if '\t' in first_line:
            delimiter = '\t'
        else:
            delimiter = ','

        # Parse headers
        headers = [h.strip() for h in first_line.split(delimiter)]
        data_lines = lines[1:]

        result = []
        for line in data_lines:
            values = [v.strip() for v in line.split(delimiter)]
            row = {}
            for i, header in enumerate(headers):
                row[header] = values[i] if i < len(values) else ""
            result.append(row)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse text: {str(e)}")

def parse_date(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize date fields in the data - handle both date and datetime formats"""
    date_patterns = [
        '%Y-%m-%d %H:%M:%S.%f',  # datetime with microseconds
        '%Y-%m-%d %H:%M:%S',     # datetime with seconds
        '%Y-%m-%d %H:%M',        # datetime without seconds
        '%Y-%m-%dT%H:%M:%S.%fZ', # ISO datetime with microseconds UTC
        '%Y-%m-%dT%H:%M:%S.%f',  # ISO datetime with microseconds
        '%Y-%m-%dT%H:%M:%SZ',    # ISO datetime UTC
        '%Y-%m-%dT%H:%M:%S',     # ISO datetime
        '%Y-%m-%dT%H:%M',        # ISO datetime without seconds
        '%Y-%m-%d',              # date only
        '%d/%m/%Y %H:%M:%S',     # dd/mm/yyyy hh:mm:ss
        '%d/%m/%Y %I:%M:%S %p',  # dd/mm/yyyy hh:mm:ss AM/PM
        '%d/%m/%Y',              # dd/mm/yyyy
        '%m-%d-%Y',              # mm-dd-yyyy
        '%m/%d/%Y',              # mm/dd/yyyy
        '%d-%m-%Y',              # dd-mm-yyyy
        '%m/%d/%Y %H:%M:%S',     # mm/dd/yyyy hh:mm:ss
        '%m/%d/%Y %I:%M:%S %p',  # mm/dd/yyyy hh:mm:ss AM/PM
        '%B %d, %Y',             # Month dd, yyyy
        '%b %d, %Y',             # Mon dd, yyyy
        '%d %B %Y',              # dd Month yyyy
        '%d %b %Y',              # dd Mon yyyy
    ]

    def looks_like_date(value: str) -> bool:
        if not isinstance(value, str):
            return False
        # Check for various date/datetime patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',  # ISO with milliseconds UTC
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}',   # ISO with microseconds
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',        # ISO UTC
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',          # ISO datetime
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',                # ISO datetime no seconds
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',          # datetime with seconds
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',                # datetime no seconds
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',                  # dd/mm/yyyy or mm/dd/yyyy
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',                  # yyyy/mm/dd
            r'\d{4}-\d{2}-\d{2}',                            # date only
            r'\w{3,9} \d{1,2}, \d{4}',                       # Month dd, yyyy
            r'\d{1,2} \w{3,9} \d{4}',                        # dd Month yyyy
        ]
        return any(re.search(pattern, value) for pattern in patterns)

    def try_parse_date(value: str) -> str:
        if not isinstance(value, str):
            return str(value)

        # First try exact matches with known patterns
        for pattern in date_patterns:
            try:
                dt = datetime.strptime(value.strip(), pattern)
                # Fix 2-digit years
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                # Always return date only (no time)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # If no exact match, try to extract date-like substrings
        # Look for patterns like YYYY-MM-DD, MM/DD/YYYY, etc.
        date_extract_patterns = [
            (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d'),              # YYYY-MM-DD
            (r'\d{1,2}/\d{1,2}/\d{4}', '%m/%d/%Y'),         # MM/DD/YYYY
            (r'\d{1,2}-\d{1,2}-\d{4}', '%m-%d-%Y'),         # MM-DD-YYYY
            (r'\d{4}/\d{1,2}/\d{1,2}', '%Y/%m/%d'),         # YYYY/MM/DD
        ]

        for regex, fmt in date_extract_patterns:
            match = re.search(regex, value)
            if match:
                try:
                    dt = datetime.strptime(match.group(), fmt)
                    if dt.year < 100:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

        # If still no match, return original value
        return value

    result = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            if isinstance(value, str) and looks_like_date(value):
                new_row[key] = try_parse_date(value)
            else:
                new_row[key] = value
        result.append(new_row)

    return result

@app.post("/parse")
async def parse_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Parse uploaded file and return normalized data"""
    try:
        # Read file content
        content = await file.read()
        filename = file.filename or "unknown"

        # Detect file type
        if filename.lower().endswith('.csv'):
            file_type = 'csv'
            rows = parse_csv(content)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            file_type = 'excel'
            rows = parse_excel(content)
        elif filename.lower().endswith('.json'):
            file_type = 'json'
            rows = parse_json(content)
        elif filename.lower().endswith('.txt'):
            file_type = 'text'
            rows = parse_text(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Apply date parsing
        normalized_rows = parse_date(rows)

        return {
            "filename": filename,
            "fileType": file_type,
            "rows": normalized_rows
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)