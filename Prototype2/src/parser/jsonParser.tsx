export async function parseJson(file: File): Promise<Record<string, any>[]> {
  // Read file content
  const text = await file.text();

  // Parse JSON
  let data: any;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error("Invalid JSON");
  }

  // Handle different shapes
  if (Array.isArray(data)) {
    return data; // Already an array
  } else if (Array.isArray(data?.transactions)) {
    return data.transactions; // Inside { transactions: [...] }
  } else if (typeof data === "object" && data !== null) {
    return [data]; // Single object
  } else {
    throw new Error("Unexpected JSON structure");
  }
}
