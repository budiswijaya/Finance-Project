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

app = FastAPI(title="Data Parser API", version="1.0.0")

# CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Normalize date fields in the data"""
    date_patterns = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m-%d-%Y',
        '%m/%d/%Y',
        '%d-%m-%Y',
    ]

    def looks_like_date(value: str) -> bool:
        return bool(re.match(r'[0-9]{1,4}[\/\-][0-9]{1,2}[\/\-][0-9]{1,4}', value))

    def try_parse_date(value: str) -> str:
        for pattern in date_patterns:
            try:
                dt = datetime.strptime(value, pattern)
                # Fix 2-digit years
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
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
    uvicorn.run(app, host="0.0.0.0", port=8001)