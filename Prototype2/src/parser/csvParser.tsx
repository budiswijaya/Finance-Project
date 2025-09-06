import Papa from "papaparse";

export async function parseCsv(file: File): Promise<Record<string, any>[]> {
  // Step 1: Read file content as text
  const text = await file.text();

  // Step 2: Parse using PapaParse
  const result = Papa.parse<Record<string, any>>(text, {
    header: true, // first row = headers
    skipEmptyLines: true, // ignore blank rows
    dynamicTyping: true, // auto-convert numbers/booleans
    trimHeaders: true, // clean up header whitespace
  });

  // Step 3: Check for errors
  if (result.errors.length > 0) {
    console.error("CSV parse errors:", result.errors);
    throw new Error("Failed to parse CSV");
  }

  // Step 4: Return the rows
  return result.data;
}
