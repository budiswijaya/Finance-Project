export async function parseText(file: File): Promise<Record<string, any>[]> {
  const text = await file.text();

  const splitByLine = text
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  // Take the first line as headers
  const headers = splitByLine[0].split(/\t|,/).map((h) => h.trim()); // handle tab or comma
  const dataLines = splitByLine.slice(1); // skip header row

  const result = dataLines.map((line) => {
    const values = line.split(/\t|,/).map((v) => v.trim());
    const obj: Record<string, any> = {};
    headers.forEach((header, index) => {
      obj[header] = values[index] || "";
    });
    return obj;
  });

  return result;
}
