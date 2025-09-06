import * as XLSX from "xlsx";

export async function parseExcel(file: File): Promise<Record<string, any>[]> {
  // Step 1: Read file as ArrayBuffer (Excel is binary, not plain text)
  const data = await file.arrayBuffer();

  // Step 2: Load workbook
  const workbook = XLSX.read(data, { type: "array" });

  // Step 3: Pick the first sheet (you could make this user-selectable later)
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];

  // Step 4: Convert sheet into JSON (array of objects)
  const rows: Record<string, any>[] = XLSX.utils.sheet_to_json(sheet, {
    defval: "", // fill empty cells with ""
    raw: false, // format numbers/dates as text
    blankrows: false, // skip empty rows
  });

  return rows;
}
