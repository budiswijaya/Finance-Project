export async function parseText(file: File): Promise<Record<string, any>[]> {
  const text = await file.text();

  const splitByLine = text
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0); // Handle Windows \r\n endings

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
