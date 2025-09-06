export async function parseText(file: File): Promise<Record<string, any>[]> {
  // Read file content
  const text = await file.text();

  // Parse Text / Convert each line into an object
  const splitByLine = text
    .replace(/\r/g, "") // Handle Windows \r\n endings
    .split("\n")
    .map((line) => line.trim()) // Trim spaces
    .filter((line) => line.length > 0); // Remove empty/whitespace-only lines
  const result = splitByLine.map((line) => {
    const [date, description, amount] = line.split(",");
    return {
      date: date.trim(),
      description: description.trim(),
      amount: Number(amount.trim()),
    };
  });

  return result;
}
