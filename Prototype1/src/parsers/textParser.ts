export async function parseText(file: File): Promise<Record<string, any>[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      try {
        const content = reader.result as string;

        // Split the text by lines
        const lines = content
          .split(/\r?\n/)
          .filter((line) => line.trim() !== "");

        // Convert each line into an object with "line" as the key
        const rows = lines.map((line, index) => ({
          lineNumber: index + 1,
          text: line,
        }));

        resolve(rows);
      } catch (err) {
        reject(err);
      }
    };

    reader.onerror = (err) => reject(err);
    reader.readAsText(file);
  });
}
