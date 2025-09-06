import { parse, format, isValid } from "date-fns";

export function parseDate(rows: Record<string, any>[]): Record<string, any>[] {
  // Only handle a couple of formats for now
  const patterns = [
    "yyyy-MM-dd", // 2025-09-06
    "dd/MM/yyyy", // 06/09/2025
    "MM-dd-yyyy", // 09-06-2025
    "M/d/yyyy", // 8/31/2025
    "MM/dd/yyyy", // 08/31/2025
    "M/d/yy", // 8/31/25
    "MM/dd/yy", // 08/31/25
  ];

  return rows.map((row) => {
    const newRow: Record<string, any> = { ...row };

    Object.keys(newRow).forEach((key) => {
      const value = newRow[key];
      if (typeof value === "string" && looksLikeDate(value)) {
        const normalized = tryPatterns(value, patterns);
        if (normalized) {
          newRow[key] = normalized; // normalized to YYYY-MM-DD
        }
      }
    });

    return newRow;
  });
}

function tryPatterns(value: string, patterns: string[]): string | null {
  for (const p of patterns) {
    const d = parse(value, p, new Date());
    if (isValid(d)) {
      let year = d.getFullYear();
      if (year < 1000) year += 2000; // Fix Excel-style "25" → "2025"
      return format(new Date(year, d.getMonth(), d.getDate()), "yyyy-MM-dd");
    }
  }
  return null;
}

function looksLikeDate(value: string): boolean {
  // Quick and loose regex for numbers, slashes, dashes
  return /[0-9]{1,4}[\/\-][0-9]{1,2}[\/\-][0-9]{1,4}/.test(value);
}
