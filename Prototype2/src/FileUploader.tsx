import React, { useState } from "react";
import { parseJson } from "./parser/jsonParser";
import { parseText } from "./parser/textParser";
// Placeholder functions for CSV and Excel until implemented
import { parseCsv } from "./parser/csvParser";
import { parseExcel } from "./parser/excelParser";
import { parseDate } from "./parser/dateParser";

interface ParsedData {
  filename: string;
  fileType: "csv" | "excel" | "json" | "text" | "unknown";
  rows: Record<string, any>[];
}

// Detect file type based on extension
function detectFileType(file: File): ParsedData["fileType"] {
  const ext = file.name.split(".").pop()?.toLowerCase();

  if (ext === "csv") return "csv";
  if (ext === "xlsx") return "excel";
  if (ext === "json") return "json";
  if (ext === "txt") return "text";
  return "unknown";
}

export function FileUploader() {
  const [data, setData] = useState<ParsedData | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files?.[0]) return;

    const file = e.target.files[0];
    const fileType = detectFileType(file);

    try {
      let rows: Record<string, any>[] = [];

      // Decide which parser to use
      if (fileType === "csv") {
        rows = await parseCsv(file);
        rows = parseDate(rows);
      } else if (fileType === "excel") {
        rows = await parseExcel(file);
        rows = parseDate(rows);
      } else if (fileType === "json") {
        rows = await parseJson(file);
        rows = parseDate(rows);
      } else if (fileType === "text") {
        rows = await parseText(file);
        rows = parseDate(rows);
      } else {
        console.error("Unsupported file type:", file.name);
        return;
      }

      // Save parsed data to state
      setData({
        filename: file.name,
        fileType,
        rows,
      });
    } catch (error) {
      console.error("Parsing error:", error);
    }
  }

  return (
    <div>
      <title>Data Normalization</title>
      <p>Only accept .txt .xlsx .json .csv files</p>

      <input
        type="file"
        accept=".json,.txt,.xlsx ,.csv"
        onChange={handleFileChange}
      />

      {/* Render table only when data exists and has rows */}
      {data && data.rows.length > 0 && (
        <div>
          <p>Preview: {data.filename}</p>
          <table border={1} cellPadding={5}>
            <thead>
              <tr>
                {Object.keys(data.rows[0]).map((head) => (
                  <th key={head}>{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {Object.values(row).map((value, colIndex) => (
                    <td key={colIndex}>{String(value)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
