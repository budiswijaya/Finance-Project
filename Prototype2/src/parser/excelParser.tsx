import * as XLSX from "xlsx";

export async function parseExcel(file: File): Promise<Record<string, any>[]> {
  const data = await file.arrayBuffer(); // Read file as ArrayBuffer (Excel is binary, not plain text)

  const workbook = XLSX.read(data, { type: "array" });

  // Pick the first sheet
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];

  // Convert Sheet into JSON(array of objects)
  const rows: Record<string, any>[] = XLSX.utils.sheet_to_json(sheet, {
    defval: "", // fill empty cells with ""
    raw: false, // format numbers/dates as text
    blankrows: false, // skip empty rows
  });

  return rows;
}
