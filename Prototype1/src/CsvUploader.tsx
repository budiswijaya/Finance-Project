import React, { useState } from "react";
import { parseCsv } from "./parsers/csvParser";
import { parseExcel } from "./parsers/excelParser";
import { parseJson } from "./parsers/jsonParser";
import { parseText } from "./parsers/textParser";

// Common structure for parsed data
interface ParsedData {
  filename: string;
  fileType: "csv" | "excel" | "json" | "text";
  rows: Record<string, any>[];
}

// Helper function to detect file type
function detectFileType(
  file: File
): "csv" | "excel" | "json" | "text" | "unknown" {
  const ext = file.name.split(".").pop()?.toLowerCase();

  if (ext === "csv") return "csv";
  if (ext === "xlsx" || ext === "xls") return "excel";
  if (ext === "json") return "json";
  if (ext === "txt") return "text";

  return "unknown";
}

export default function FileUploader() {
  const [data, setData] = useState<ParsedData | null>(null);

  // Event handler for file upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

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

      setData({
        filename: file.name,
        fileType,
        rows,
      });
    } catch (error) {
      console.error("Parsing error:", error);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h1>File Uploader</h1>
      <input type="file" onChange={handleFileChange} />

      {/* If there is parsed data, render a table */}
      {data && data.rows.length > 0 && (
        <>
          <table
            border={1}
            style={{
              marginTop: "1rem",
              borderCollapse: "collapse",
              width: "100%",
            }}
          >
            <thead>
              <tr>
                {Object.keys(data.rows[0]).map((key) => (
                  <th key={key} style={{ padding: "6px 12px" }}>
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, idx) => (
                <tr key={idx}>
                  {Object.values(row).map((value, i) => (
                    <td
                      key={i}
                      style={{ padding: "6px 12px", textAlign: "center" }}
                    >
                      {String(value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
