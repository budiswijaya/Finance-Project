import React, { useState } from "react";
import { parseJson } from "./parser/jsonParser";
import { parseText } from "./parser/textParser";
import { parseCsv } from "./parser/csvParser";
import { parseExcel } from "./parser/excelParser";
import { parseDate } from "./parser/dateParser";

interface ParsedData {
  filename: string;
  fileType: "csv" | "excel" | "json" | "text" | "unknown";
  rows: Record<string, any>[];
}

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
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [normalizedRows, setNormalizedRows] = useState<any[]>([]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files?.[0]) return;

    const file = e.target.files[0];
    const fileType = detectFileType(file);

    try {
      let rows: Record<string, any>[] = [];

      if (fileType === "csv") {
        rows = await parseCsv(file);
      } else if (fileType === "excel") {
        rows = await parseExcel(file);
      } else if (fileType === "json") {
        rows = await parseJson(file);
      } else if (fileType === "text") {
        rows = await parseText(file);
      } else {
        console.error("Unsupported file type:", file.name);
        return;
      }

      rows = parseDate(rows);

      setData({
        filename: file.name,
        fileType,
        rows,
      });
    } catch (error) {
      console.error("Parsing error:", error);
    }
  }

  function handleNormalize() {
    if (!data) return;
    const tempRows: any[] = [];

    for (const row of data.rows) {
      const newRow: any = {};
      for (const header in row) {
        const targetField = mapping[header];
        if (targetField && targetField !== "Ignore") {
          newRow[targetField.toLowerCase()] = row[header];
        }
      }
      tempRows.push(newRow);
    }

    setNormalizedRows(tempRows);
  }

  return (
    <div
      style={{
        display: "flex",
        gap: "2rem",
        justifyContent: "center",
        marginTop: "2rem",
      }}
    >
      {/* Left side = Original Data (only if data exists) */}
      {data && (
        <div style={{ flex: 1 }}>
          <h3>Original Data</h3>
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

      {/* Middle = Input + Mapping UI (always visible) */}
      <div style={{ flex: 0.7 }}>
        <div className="file-input-wrapper">
          <input
            id="file-upload"
            type="file"
            accept=".json,.txt,.xlsx,.csv"
            onChange={handleFileChange}
          />
          <label htmlFor="file-upload" className="file-upload-label">
            Choose File
          </label>
        </div>
        <p className="file-note">Only .xlsx .csv .txt .json files</p>

        {data && (
          <>
            {Object.keys(data.rows[0]).map((header) => (
              <div key={header} style={{ marginBottom: "0.5rem" }}>
                <label style={{ marginRight: "0.5rem" }}>{header}</label>
                <select
                  value={mapping[header] || ""}
                  onChange={(e) =>
                    setMapping({ ...mapping, [header]: e.target.value })
                  }
                >
                  <option value="">Select field</option>
                  <option value="Date">Date</option>
                  <option value="Description">Description</option>
                  <option value="Amount">Amount</option>
                  <option value="Ignore">Ignore</option>
                </select>
              </div>
            ))}

            <button onClick={handleNormalize} style={{ marginTop: "1rem" }}>
              Normalize Data
            </button>
          </>
        )}
      </div>

      {/* Right side = Normalized Data (only if data exists) */}
      {data && (
        <div style={{ flex: 1 }}>
          <h3>Normalized Data</h3>
          {normalizedRows.length > 0 ? (
            <table border={1} cellPadding={5}>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {normalizedRows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    <td>{row.date}</td>
                    <td>{row.description}</td>
                    <td>{row.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No normalized data yet</p>
          )}
        </div>
      )}
    </div>
  );
}
