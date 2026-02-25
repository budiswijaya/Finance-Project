import Papa from "papaparse";

export async function parseCsv(file: File): Promise<Record<string, any>[]> {
  const text = await file.text();

  const result = Papa.parse<Record<String, any>>(text, {
    header: true, // first row = headers
    skipEmptyLines: true, // ignore blank rows
    dynamicTyping: true, // auto-convert numbers/booleans
    trimHeaders: true, // clean up header whitespace
  });

  if (result.errors.length > 0) {
    console.error("CSV parse errors:", result.errors);
    throw new Error("Failed to parse CSV");
  }

  return result.data;
}
