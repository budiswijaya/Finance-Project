export async function parseJson(file: File): Promise<Record<string, any>[]> {
  const text = await file.text();

  let data: any;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw new Error("Invalid JSON");
  }

  // Hande different shapes
  if (Array.isArray(data)) {
    return data;
  } else if (Array.isArray(data?.transactions)) {
    return data.transactions;
  } else if (typeof data === "object" && data !== null) {
    return [data];
  } else {
    throw new Error("Unexpected JSON structure");
  }
}
