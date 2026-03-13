import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import { ReactGrid } from "@silevis/reactgrid";
import type { Column, Row, CellChange } from "@silevis/reactgrid";
import "@silevis/reactgrid/styles.css";

// ---------- Types ----------
interface ParsedData {
  filename: string;
  fileType: "csv" | "excel" | "json" | "text" | "unknown";
  rows: Record<string, any>[];
}

interface HistoryState {
  originalGridRows: Row[];
  normalizedGridRows: Row[];
  normalizedRows: any[];
  normalizedGridCols: Column[];
}

interface SavedState {
  normalizedGridRows: Row[];
  normalizedRows: any[];
  normalizedGridCols: Column[];
  timestamp: number;
}

// ---------- Constants ----------
const TARGET_COLUMNS = ["Date", "Description", "Amount"] as const;
const MAX_HISTORY_SIZE = 100;
const COLUMN_WIDTHS = {
  rowIndex: 40,
  Description: 260,
  default: 140,
} as const;

// ---------- Utils ----------

const getColumnWidth = (
  header: string,
  rows: Record<string, any>[]
): number => {
  const charWidth = 8;
  const padding = 20;
  const maxLen = Math.max(
    header.length,
    ...rows.map((row) => {
      const val = row[header];
      return val !== undefined && val !== null ? String(val).length : 0;
    })
  );
  return Math.min(300, Math.max(80, maxLen * charWidth + padding));
};

const safeText = (newCell: any): string =>
  newCell?.text ?? String(newCell?.value ?? "");

const formatCurrencyNumber = (num: number): string =>
  new Intl.NumberFormat("id-ID").format(num);

const parseAmount = (text: string): number =>
  Number(String(text).replace(/[^0-9.\-]/g, "")) || 0;

// ---------- Custom Hooks ----------
const useHistory = () => {
  const historyRef = useRef<HistoryState[]>([]);
  const indexRef = useRef(-1);
  const isProcessingRef = useRef(false);

  const pushState = useCallback((state: HistoryState) => {
    if (isProcessingRef.current) return;

    const newState = JSON.parse(JSON.stringify(state));

    // Check if state is different from current
    const current = historyRef.current[indexRef.current];
    if (current && JSON.stringify(current) === JSON.stringify(newState)) {
      return;
    }

    // Trim future states if we're not at the end
    const newHistory = historyRef.current.slice(0, indexRef.current + 1);
    newHistory.push(newState);

    // Limit history size
    if (newHistory.length > MAX_HISTORY_SIZE) {
      newHistory.shift();
    } else {
      indexRef.current++;
    }

    historyRef.current = newHistory;
  }, []);

  const undo = useCallback((): HistoryState | null => {
    if (indexRef.current > 0) {
      isProcessingRef.current = true;
      indexRef.current--;
      const state = historyRef.current[indexRef.current];
      setTimeout(() => {
        isProcessingRef.current = false;
      }, 0);
      return JSON.parse(JSON.stringify(state));
    }
    return null;
  }, []);

  const redo = useCallback((): HistoryState | null => {
    if (indexRef.current < historyRef.current.length - 1) {
      isProcessingRef.current = true;
      indexRef.current++;
      const state = historyRef.current[indexRef.current];
      setTimeout(() => {
        isProcessingRef.current = false;
      }, 0);
      return JSON.parse(JSON.stringify(state));
    }
    return null;
  }, []);

  const reset = useCallback(() => {
    historyRef.current = [];
    indexRef.current = -1;
    isProcessingRef.current = false;
  }, []);

  const canUndo = indexRef.current > 0;
  const canRedo = indexRef.current < historyRef.current.length - 1;

  return { pushState, undo, redo, reset, canUndo, canRedo };
};

// ---------- Component ----------
export function NormalizedData() {
  // State
  const [data, setData] = useState<ParsedData | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [normalizedRows, setNormalizedRows] = useState<any[]>([]);
  const [submitMessage, setSubmitMessage] = useState<string>("");
  const [originalGridCols, setOriginalGridCols] = useState<Column[]>([]);
  const [originalGridRows, setOriginalGridRows] = useState<Row[]>([]);
  const [normalizedGridCols, setNormalizedGridCols] = useState<Column[]>([]);
  const [normalizedGridRows, setNormalizedGridRows] = useState<Row[]>([]);
  const [originalFocus, setOriginalFocus] = useState<any>(null);
  const [normalizedFocus, setNormalizedFocus] = useState<any>(null);

  // Debug focus state
  useEffect(() => {
    console.log("Original Focus:", originalFocus);
  }, [originalFocus]);

  useEffect(() => {
    console.log("Normalized Focus:", normalizedFocus);
  }, [normalizedFocus]);

  // History management
  const { pushState, undo, redo, reset: resetHistory } = useHistory();

  // Memorized values
  const originalHeaders = useMemo(
    () => (data ? Object.keys(data.rows[0] || {}) : []),
    [data]
  );

  const normalizedSummary = useMemo(() => {
    const count = normalizedRows.length;
    const sum = normalizedRows.reduce(
      (acc, r) => acc + Number(r.amount || 0),
      0
    );
    return { count, sum };
  }, [normalizedRows]);

  // ---------- Helper Functions ----------
  const rowsToObjects = useCallback((rows: Row[], cols: Column[]): any[] => {
    const dataCols = cols.filter((c) => c.columnId !== "rowIndex");
    return rows
      .filter((r) => r.rowId !== "header")
      .map((r) => {
        const obj: any = {};
        dataCols.forEach((col, idx) => {
          const cellIndex = idx + 1; // +1 to skip rowIndex column
          let val = r.cells[cellIndex]?.text ?? "";

          if (col.columnId === "Amount") {
            val = parseAmount(val);
          }
          obj[col.columnId.toLowerCase()] = val;
        });
        return obj;
      });
  }, []);

  const buildGridRows = useCallback(
    (dataRows: Record<string, any>[], columns: Column[]): Row[] => {
      const headerRow: Row = {
        rowId: "header",
        cells: [
          { type: "header", text: "" },
          ...columns
            .slice(1)
            .map((c) => ({ type: "header", text: c.columnId })),
        ],
      };

      const dataRowsGrid: Row[] = dataRows.map((row, idx) => ({
        rowId: `nrow-${idx}`,
        cells: [
          { type: "header", text: String(idx + 1) },
          ...columns.slice(1).map((col) => {
            const key = Object.keys(row).find(
              (k) => k.toLowerCase() === col.columnId.toLowerCase()
            );
            return { type: "text", text: String(row[key] || "") };
          }),
        ],
      }));

      return [headerRow, ...dataRowsGrid];
    },
    []
  );

  // ---------- Event Handlers ----------
  const handleUndo = useCallback(() => {
    const prevState = undo();
    if (prevState) {
      setOriginalGridRows(prevState.originalGridRows);
      setNormalizedGridRows(prevState.normalizedGridRows);
      setNormalizedRows(prevState.normalizedRows);
      if (prevState.normalizedGridCols) {
        setNormalizedGridCols(prevState.normalizedGridCols);
      }
    }
  }, [undo]);

  const handleRedo = useCallback(() => {
    const nextState = redo();
    if (nextState) {
      setOriginalGridRows(nextState.originalGridRows);
      setNormalizedGridRows(nextState.normalizedGridRows);
      setNormalizedRows(nextState.normalizedRows);
      if (nextState.normalizedGridCols) {
        setNormalizedGridCols(nextState.normalizedGridCols);
      }
    }
  }, [redo]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = /Mac|iPod|iPhone|iPad/.test(navigator.platform);
      const modKey = isMac ? e.metaKey : e.ctrlKey;

      if (!modKey) return;

      const key = e.key.toLowerCase();

      if (key === "z") {
        e.preventDefault();
        e.stopPropagation();
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
      } else if (key === "y") {
        e.preventDefault();
        e.stopPropagation();
        handleRedo();
      }
    };

    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [handleUndo, handleRedo]);

  // File handling - Modified to preserve normalized data
  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("http://localhost:8001/parse", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result: ParsedData = await response.json();

        setData(result);

        const keys = Object.keys(result.rows[0] || {});
        const columns: Column[] = [
          {
            columnId: "rowIndex",
            width: COLUMN_WIDTHS.rowIndex,
            resizable: false,
          },
          ...keys.map((header) => ({
            columnId: header,
            width: getColumnWidth(header, result.rows),
            resizable: true,
          })),
        ];

        const gridRows = buildGridRows(result.rows, [
          {
            columnId: "rowIndex",
            width: COLUMN_WIDTHS.rowIndex,
            resizable: false,
          },
          ...keys.map((k) => ({ columnId: k, width: 100, resizable: true })),
        ]);

        setOriginalGridCols(columns);
        setOriginalGridRows(gridRows);
        // DON'T reset normalized data - preserve it when uploading new files
        // setNormalizedGridCols([]);
        // setNormalizedGridRows([]);
        // setNormalizedRows([]);
        setSubmitMessage("");
        setMapping({});
        // Only reset history for original data operations
        // resetHistory();
      } catch (err) {
        console.error("Parsing error:", err);
      }
    },
    [buildGridRows]
  );

  // Normalization
  const handleNormalize = useCallback(() => {
    if (!originalGridRows.length) return;

    const selectedTargets = Object.values(mapping).filter(Boolean);
    if (!selectedTargets.length) {
      setSubmitMessage("Please map at least one column before normalizing.");
      return;
    }

    const usedTargets = TARGET_COLUMNS.filter((t) =>
      selectedTargets.includes(t)
    );

    // Set up columns if this is the first normalization
    let columns: Column[] = normalizedGridCols;
    if (!normalizedGridCols.length) {
      columns = [
        {
          columnId: "rowIndex",
          width: COLUMN_WIDTHS.rowIndex,
          resizable: false,
        },
        ...usedTargets.map((t) => ({
          columnId: t,
          width:
            COLUMN_WIDTHS[t as keyof typeof COLUMN_WIDTHS] ||
            COLUMN_WIDTHS.default,
          resizable: true,
        })),
      ];
      setNormalizedGridCols(columns);
    }

    const dataRows = originalGridRows.filter((r) => r.rowId !== "header");
    const newNormalizedObjects: any[] = [];
    const newNormalizedGridRowsData: Row[] = [];

    // Get the current count of normalized rows to continue row numbering
    const currentRowCount = normalizedRows.length;

    dataRows.forEach((origRow, idx) => {
      const obj: any = {};
      const cells = [
        { type: "header", text: String(currentRowCount + idx + 1) },
      ];

      usedTargets.forEach((targetField) => {
        const origColIndex = originalGridCols.findIndex(
          (col) => mapping[col.columnId] === targetField
        );

        let text = "";
        if (origColIndex >= 0) {
          text = origRow.cells[origColIndex]?.text ?? "";
        }

        if (targetField === "Amount") {
          obj.amount = parseAmount(text);
        } else {
          obj[targetField.toLowerCase()] = text;
        }

        cells.push({ type: "text", text });
      });

      newNormalizedObjects.push(obj);
      newNormalizedGridRowsData.push({
        rowId: `nrow-${currentRowCount + idx}`,
        cells,
      });
    });

    // Append to existing normalized data instead of replacing
    const updatedNormalizedObjects = [
      ...normalizedRows,
      ...newNormalizedObjects,
    ];

    // Create header row if needed
    const headerRow: Row = {
      rowId: "header",
      cells: [
        { type: "header", text: "" },
        ...usedTargets.map((t) => ({ type: "header", text: t })),
      ],
    };

    // Append new rows to existing normalized grid rows
    const existingDataRows = normalizedGridRows.filter(
      (r) => r.rowId !== "header"
    );
    const allRows = [
      headerRow,
      ...existingDataRows,
      ...newNormalizedGridRowsData,
    ];

    setNormalizedRows(updatedNormalizedObjects);
    setNormalizedGridRows(allRows);
    setSubmitMessage("");

    // Update history
    pushState({
      originalGridRows,
      normalizedGridRows: allRows,
      normalizedRows: updatedNormalizedObjects,
      normalizedGridCols: columns,
    });
  }, [
    originalGridRows,
    originalGridCols,
    mapping,
    pushState,
    normalizedRows,
    normalizedGridRows,
    normalizedGridCols,
  ]);

  // Grid change handlers
  const handleOriginalChanges = useCallback(
    (changes: CellChange[]) => {
      if (!changes?.length) return;

      const updatedRows = originalGridRows.map((row) => {
        const rowChanges = changes.filter((c) => c.rowId === row.rowId);
        if (!rowChanges.length) return row;

        return {
          ...row,
          cells: row.cells.map((cell, idx) => {
            const colId = originalGridCols[idx]?.columnId;
            const change = rowChanges.find((c) => c.columnId === colId);
            return change ? { ...cell, text: safeText(change.newCell) } : cell;
          }),
        };
      });

      // Check if anything actually changed
      if (JSON.stringify(updatedRows) === JSON.stringify(originalGridRows)) {
        return;
      }

      setOriginalGridRows(updatedRows);
      pushState({
        originalGridRows: updatedRows,
        normalizedGridRows,
        normalizedRows,
        normalizedGridCols,
      });
    },
    [
      originalGridCols,
      originalGridRows,
      normalizedGridRows,
      normalizedRows,
      pushState,
    ]
  );

  const handleNormalizedChanges = useCallback(
    (changes: CellChange[]) => {
      if (!changes?.length) return;

      const updatedRows = normalizedGridRows.map((row) => {
        const rowChanges = changes.filter((c) => c.rowId === row.rowId);
        if (!rowChanges.length) return row;

        return {
          ...row,
          cells: row.cells.map((cell, idx) => {
            const colId = normalizedGridCols[idx]?.columnId;
            const change = rowChanges.find((c) => c.columnId === colId);
            return change ? { ...cell, text: safeText(change.newCell) } : cell;
          }),
        };
      });

      // Check if anything actually changed
      if (JSON.stringify(updatedRows) === JSON.stringify(normalizedGridRows)) {
        return;
      }

      const newObjects = rowsToObjects(updatedRows, normalizedGridCols);

      setNormalizedGridRows(updatedRows);
      setNormalizedRows(newObjects);
      pushState({
        originalGridRows,
        normalizedGridRows: updatedRows,
        normalizedRows: newObjects,
        normalizedGridCols,
      });
    },
    [normalizedGridRows, normalizedGridCols, rowsToObjects, pushState]
  );

  // Note: column resize events require paid grid version
  const handleColumnsChanged = useCallback(
    (changes: { columnId: string; width: number }[]) => {
      setOriginalGridCols((prev) =>
        prev.map((col) => {
          const change = changes.find((c) => c.columnId === col.columnId);
          return change ? { ...col, width: change.width } : col;
        })
      );
    },
    []
  );

  // Download and submit
  const handleDownload = useCallback(() => {
    if (!normalizedRows.length) return;

    const headers = ["Date", "Description", "Amount"];
    const csvContent = [
      headers.join(","),
      ...normalizedRows.map(
        (r) => `${r.date ?? ""},${r.description ?? ""},${r.amount ?? 0}`
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "normalized.csv";
    link.click();
    URL.revokeObjectURL(url);
  }, [normalizedRows]);

  const handleSubmit = useCallback(() => {
    const { count, sum } = normalizedSummary;
    setSubmitMessage(
      `Adding ${count} items with sum amount ${formatCurrencyNumber(
        sum
      )}, please confirm.`
    );
    console.log("Submitting normalized rows:", normalizedRows);
  }, [normalizedSummary, normalizedRows]);

  // Save/Load functionality
  const handleSave = useCallback(() => {
    if (!normalizedRows.length) {
      alert("No normalized data to save!");
      return;
    }

    const savedState: SavedState = {
      normalizedGridRows,
      normalizedRows,
      normalizedGridCols,
      timestamp: Date.now(),
    };

    try {
      localStorage.setItem("normalizedDataState", JSON.stringify(savedState));
      alert("Normalized data saved successfully!");
    } catch (error) {
      console.error("Error saving data:", error);
      alert("Failed to save data. Please try again.");
    }
  }, [normalizedGridRows, normalizedRows, normalizedGridCols]);

  const handleLoad = useCallback(() => {
    try {
      const savedData = localStorage.getItem("normalizedDataState");
      if (!savedData) {
        alert("No saved data found!");
        return;
      }

      const parsedData: SavedState = JSON.parse(savedData);

      // Validate the saved data structure
      if (
        !parsedData.normalizedGridRows ||
        !parsedData.normalizedRows ||
        !parsedData.normalizedGridCols
      ) {
        alert("Invalid saved data format!");
        return;
      }

      setNormalizedGridRows(parsedData.normalizedGridRows);
      setNormalizedRows(parsedData.normalizedRows);
      setNormalizedGridCols(parsedData.normalizedGridCols);

      const saveDate = new Date(parsedData.timestamp).toLocaleString();
      alert(`Normalized data loaded successfully!\nSaved on: ${saveDate}`);
    } catch (error) {
      console.error("Error loading data:", error);
      alert("Failed to load data. The saved data might be corrupted.");
    }
  }, []);

  // Delete functions with enhanced debugging
  const deleteSelectedOriginalRow = useCallback(() => {
    console.log("🔴 DELETE ROW CLICKED - Original");
    console.log("originalFocus:", originalFocus);
    console.log("originalGridRows.length:", originalGridRows.length);

    if (!originalGridRows.length) {
      console.log("❌ No rows to delete");
      return;
    }

    if (!originalFocus) {
      console.log("❌ No focus - try clicking on a row number first");
      return;
    }

    const { rowId, columnId } = originalFocus;
    console.log("Focus details - rowId:", rowId, "columnId:", columnId);

    // More flexible row deletion - allow if we have a valid rowId that's not header
    if (rowId === "header") {
      console.log("❌ Cannot delete header row");
      return;
    }

    if (!rowId || rowId === "") {
      console.log("❌ Invalid rowId");
      return;
    }

    console.log("✅ Deleting row:", rowId);
    const updatedRows = originalGridRows.filter((r) => r.rowId !== rowId);
    console.log(
      "Rows before:",
      originalGridRows.length,
      "after:",
      updatedRows.length
    );

    // Update the data state as well to keep it in sync
    if (data) {
      const rowIndex = originalGridRows.findIndex((r) => r.rowId === rowId) - 1; // -1 because header is at index 0
      if (rowIndex >= 0 && rowIndex < data.rows.length) {
        const updatedDataRows = data.rows.filter((_, idx) => idx !== rowIndex);
        setData({ ...data, rows: updatedDataRows });
      }
    }

    setOriginalGridRows(updatedRows);

    // Maintain focus after deletion - find next available row
    const remainingDataRows = updatedRows.filter((r) => r.rowId !== "header");
    if (remainingDataRows.length > 0) {
      // Try to focus on the same position, or the last row if we deleted the last one
      const deletedIndex =
        originalGridRows.findIndex((r) => r.rowId === rowId) - 1; // -1 for header
      const nextRowIndex = Math.min(deletedIndex, remainingDataRows.length - 1);
      const nextRow = remainingDataRows[nextRowIndex];
      if (nextRow) {
        setOriginalFocus({
          rowId: nextRow.rowId,
          columnId: originalFocus.columnId || "rowIndex",
        });
      }
    } else {
      setOriginalFocus(null);
    }

    pushState({
      originalGridRows: updatedRows,
      normalizedGridRows,
      normalizedRows,
      normalizedGridCols,
    });
  }, [
    originalGridRows,
    originalFocus,
    normalizedGridRows,
    normalizedRows,
    pushState,
    data,
  ]);

  const deleteSelectedOriginalColumn = useCallback(() => {
    console.log("🔴 DELETE COLUMN CLICKED - Original");
    console.log("originalFocus:", originalFocus);
    console.log(
      "originalGridCols:",
      originalGridCols.map((c) => c.columnId)
    );

    if (!originalGridRows.length) {
      console.log("❌ No data to delete from");
      return;
    }

    if (!originalFocus) {
      console.log("❌ No focus - try clicking on a column header first");
      return;
    }

    const { rowId, columnId } = originalFocus;
    console.log("Focus details - rowId:", rowId, "columnId:", columnId);

    // More flexible column deletion
    if (columnId === "rowIndex") {
      console.log("❌ Cannot delete row index column");
      return;
    }

    if (!columnId || columnId === "") {
      console.log("❌ Invalid columnId");
      return;
    }

    const colIndex = originalGridCols.findIndex((c) => c.columnId === columnId);
    console.log("Column index:", colIndex);

    if (colIndex < 0) {
      console.log("❌ Column not found");
      return;
    }

    console.log("✅ Deleting column:", columnId);
    const newCols = originalGridCols.filter((c) => c.columnId !== columnId);
    console.log(
      "Columns before:",
      originalGridCols.length,
      "after:",
      newCols.length
    );

    const updatedRows = originalGridRows.map((row) => ({
      ...row,
      cells: row.cells.filter((_, idx) => idx !== colIndex),
    }));

    setOriginalGridCols(newCols);
    setOriginalGridRows(updatedRows);

    // Maintain focus after column deletion - find next available column
    const remainingCols = newCols.filter((c) => c.columnId !== "rowIndex");
    if (remainingCols.length > 0) {
      // Try to focus on the same position, or the last column if we deleted the last one
      const deletedIndex =
        originalGridCols.findIndex((c) => c.columnId === columnId) - 1; // -1 for rowIndex
      const nextColIndex = Math.min(deletedIndex, remainingCols.length - 1);
      const nextCol = remainingCols[nextColIndex];
      if (nextCol) {
        // Use setTimeout to ensure the grid updates before setting focus
        setTimeout(() => {
          setOriginalFocus({
            rowId: originalFocus.rowId || "header",
            columnId: nextCol.columnId,
          });
        }, 10);
      }
    } else {
      setTimeout(() => {
        setOriginalFocus({
          rowId: originalFocus.rowId || "header",
          columnId: "rowIndex",
        });
      }, 10);
    }

    pushState({
      originalGridRows: updatedRows,
      normalizedGridRows,
      normalizedRows,
      normalizedGridCols,
    });
  }, [
    originalGridRows,
    originalGridCols,
    originalFocus,
    normalizedGridRows,
    normalizedRows,
    pushState,
  ]);

  const deleteSelectedNormalizedRow = useCallback(() => {
    console.log("🔴 DELETE ROW CLICKED - Normalized");
    console.log("normalizedFocus:", normalizedFocus);
    console.log("normalizedGridRows.length:", normalizedGridRows.length);

    if (!normalizedGridRows.length) {
      console.log("❌ No rows to delete");
      return;
    }

    if (!normalizedFocus) {
      console.log("❌ No focus - try clicking on a row number first");
      return;
    }

    const { rowId, columnId } = normalizedFocus;
    console.log("Focus details - rowId:", rowId, "columnId:", columnId);

    // More flexible row deletion
    if (rowId === "header") {
      console.log("❌ Cannot delete header row");
      return;
    }

    if (!rowId || rowId === "") {
      console.log("❌ Invalid rowId");
      return;
    }

    console.log("✅ Deleting row:", rowId);
    const updatedRows = normalizedGridRows.filter((r) => r.rowId !== rowId);
    console.log(
      "Rows before:",
      normalizedGridRows.length,
      "after:",
      updatedRows.length
    );

    const newObjects = rowsToObjects(updatedRows, normalizedGridCols);

    setNormalizedGridRows(updatedRows);
    setNormalizedRows(newObjects);

    // Maintain focus after deletion - find next available row
    const remainingDataRows = updatedRows.filter((r) => r.rowId !== "header");
    if (remainingDataRows.length > 0) {
      // Try to focus on the same position, or the last row if we deleted the last one
      const deletedIndex =
        normalizedGridRows.findIndex((r) => r.rowId === rowId) - 1; // -1 for header
      const nextRowIndex = Math.min(deletedIndex, remainingDataRows.length - 1);
      const nextRow = remainingDataRows[nextRowIndex];
      if (nextRow) {
        setTimeout(() => {
          setNormalizedFocus({
            rowId: nextRow.rowId,
            columnId: normalizedFocus.columnId || "rowIndex",
          });
        }, 10);
      }
    } else {
      setNormalizedFocus(null);
    }

    pushState({
      originalGridRows,
      normalizedGridRows: updatedRows,
      normalizedRows: newObjects,
    });
  }, [
    normalizedGridRows,
    normalizedFocus,
    normalizedGridCols,
    originalGridRows,
    rowsToObjects,
    pushState,
  ]);

  const deleteSelectedNormalizedColumn = useCallback(() => {
    console.log("🔴 DELETE COLUMN CLICKED - Normalized");
    console.log("normalizedFocus:", normalizedFocus);
    console.log(
      "normalizedGridCols:",
      normalizedGridCols.map((c) => c.columnId)
    );

    if (!normalizedGridRows.length) {
      console.log("❌ No data to delete from");
      return;
    }

    if (!normalizedFocus) {
      console.log("❌ No focus - try clicking on a column header first");
      return;
    }

    const { rowId, columnId } = normalizedFocus;
    console.log("Focus details - rowId:", rowId, "columnId:", columnId);

    // More flexible column deletion
    if (columnId === "rowIndex") {
      console.log("❌ Cannot delete row index column");
      return;
    }

    if (!columnId || columnId === "") {
      console.log("❌ Invalid columnId");
      return;
    }

    const colIndex = normalizedGridCols.findIndex(
      (c) => c.columnId === columnId
    );
    console.log("Column index:", colIndex);

    if (colIndex < 0) {
      console.log("❌ Column not found");
      return;
    }

    console.log("✅ Deleting column:", columnId);
    const newCols = normalizedGridCols.filter((c) => c.columnId !== columnId);
    console.log(
      "Columns before:",
      normalizedGridCols.length,
      "after:",
      newCols.length
    );

    const updatedRows = normalizedGridRows.map((row) => ({
      ...row,
      cells: row.cells.filter((_, idx) => idx !== colIndex),
    }));

    const newObjects = rowsToObjects(updatedRows, newCols);

    setNormalizedGridCols(newCols);
    setNormalizedGridRows(updatedRows);
    setNormalizedRows(newObjects);

    // Maintain focus after column deletion - find next available column
    const remainingCols = newCols.filter((c) => c.columnId !== "rowIndex");
    if (remainingCols.length > 0) {
      // Try to focus on the same position, or the last column if we deleted the last one
      const deletedIndex =
        normalizedGridCols.findIndex((c) => c.columnId === columnId) - 1; // -1 for rowIndex
      const nextColIndex = Math.min(deletedIndex, remainingCols.length - 1);
      const nextCol = remainingCols[nextColIndex];
      if (nextCol) {
        setTimeout(() => {
          setNormalizedFocus({
            rowId: normalizedFocus.rowId || "header",
            columnId: nextCol.columnId,
          });
        }, 10);
      }
    } else {
      setTimeout(() => {
        setNormalizedFocus({
          rowId: normalizedFocus.rowId || "header",
          columnId: "rowIndex",
        });
      }, 10);
    }

    pushState({
      originalGridRows,
      normalizedGridRows: updatedRows,
      normalizedRows: newObjects,
    });
  }, [
    normalizedGridRows,
    normalizedGridCols,
    normalizedFocus,
    originalGridRows,
    rowsToObjects,
    pushState,
  ]);

  // ---------- Render ----------
  return (
    <div
      style={{
        display: "flex",
        gap: "2rem",
        justifyContent: "center",
        marginTop: "2rem",
      }}
    >
      <title>Data Normalization</title>
      {/* Original Data Grid */}
      {data && (
        <div
          className="grid-wrapper"
          style={{
            flex: "0 0 800px",
            width: "800px",
            height: "800px",
            maxWidth: "800px",
            maxHeight: "800px",
            border: "1px solid #444",
            position: "relative",
          }}
        >
          <div
            style={{
              position: "sticky",
              top: 0,
              left: 0,
              right: 0,
              zIndex: 10,
              backgroundColor: "white",
              borderBottom: "1px solid #ddd",
              padding: "8px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h3 style={{ color: "black", margin: 0 }}>
              Original Data ({data.rows.length} rows)
            </h3>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={deleteSelectedOriginalRow}
                disabled={
                  !originalFocus ||
                  originalFocus.rowId === "header" ||
                  !originalFocus.rowId
                }
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor:
                    originalFocus &&
                    originalFocus.rowId !== "header" &&
                    originalFocus.rowId
                      ? "#ff6b6b"
                      : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor:
                    originalFocus &&
                    originalFocus.rowId !== "header" &&
                    originalFocus.rowId
                      ? "pointer"
                      : "not-allowed",
                }}
              >
                Delete Row
              </button>
              <button
                onClick={deleteSelectedOriginalColumn}
                disabled={
                  !originalFocus ||
                  originalFocus.columnId === "rowIndex" ||
                  !originalFocus.columnId
                }
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor:
                    originalFocus &&
                    originalFocus.columnId !== "rowIndex" &&
                    originalFocus.columnId
                      ? "#ff6b6b"
                      : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor:
                    originalFocus &&
                    originalFocus.columnId !== "rowIndex" &&
                    originalFocus.columnId
                      ? "pointer"
                      : "not-allowed",
                }}
              >
                Delete Column
              </button>
            </div>
          </div>
          <div
            style={{
              height: "calc(100% - 60px)",
              overflowX: "auto",
              overflowY: "auto",
            }}
          >
            <ReactGrid
              rows={originalGridRows}
              columns={originalGridCols}
              onCellsChanged={handleOriginalChanges}
              onColumnsChanged={handleColumnsChanged}
              onFocusLocationChanged={(loc) => setOriginalFocus(loc)}
              enableRowSelection
              enableColumnSelection
              stickyTopRows={1}
              stickyLeftColumns={1}
            />
          </div>
        </div>
      )}

      {/* Control Panel */}
      <div style={{ flex: "0 0 auto", minWidth: "250px" }}>
        <div className="file-input-wrapper">
          <input
            type="file"
            id="file-upload"
            accept=".json,.txt,.xlsx,.csv"
            onChange={handleFileChange}
          />
          <label htmlFor="file-upload" className="file-upload-label">
            Choose File
          </label>
        </div>
        <p className="file-note">Only .xlsx .csv .txt .json files</p>

        {data && (
          <>
            <h4>Column mapping</h4>
            {originalHeaders.map((header) => (
              <div key={header} style={{ marginBottom: "0.5rem" }}>
                <label style={{ marginRight: "0.5rem" }}>{header}</label>
                <select
                  value={mapping[header] || ""}
                  onChange={(e) =>
                    setMapping((prev) => ({
                      ...prev,
                      [header]: e.target.value,
                    }))
                  }
                >
                  <option value="">Select field</option>
                  <option value="Date">Date</option>
                  <option value="Description">Description</option>
                  <option value="Amount">Amount</option>
                  <option value="Ignore">Ignore</option>
                </select>
              </div>
            ))}

            <div
              style={{
                display: "flex",
                gap: "0.5rem",
                flexWrap: "wrap",
                marginTop: "1rem",
              }}
            >
              <button onClick={handleNormalize}>Add Data</button>
              <button
                onClick={handleDownload}
                disabled={!normalizedRows.length}
              >
                Download
              </button>
              <button onClick={handleSubmit} disabled={!normalizedRows.length}>
                Submit
              </button>
            </div>

            {submitMessage && (
              <p style={{ marginTop: "0.5rem", fontStyle: "italic" }}>
                {submitMessage}
              </p>
            )}
          </>
        )}
      </div>

      {/* Normalized Data Grid */}
      {data && normalizedGridRows.length > 0 && (
        <div
          className="grid-wrapper"
          style={{
            flex: "0 0 650px",
            width: "600px",
            height: "800px",
            maxWidth: "600px",
            maxHeight: "800px",
            border: "1px solid #444",
            position: "relative",
          }}
        >
          <div
            style={{
              position: "sticky",
              top: 0,
              left: 0,
              right: 0,
              zIndex: 10,
              backgroundColor: "white",
              borderBottom: "1px solid #ddd",
              padding: "8px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h3 style={{ color: "black", margin: 0 }}>
              Normalized Data ({normalizedRows.length} rows)
            </h3>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={handleSave}
                disabled={!normalizedRows.length}
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor: normalizedRows.length ? "#4CAF50" : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor: normalizedRows.length ? "pointer" : "not-allowed",
                }}
              >
                Save
              </button>
              <button
                onClick={handleLoad}
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor: "#2196F3",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
              >
                Load
              </button>
              <button
                onClick={deleteSelectedNormalizedRow}
                disabled={
                  !normalizedFocus ||
                  normalizedFocus.rowId === "header" ||
                  !normalizedFocus.rowId
                }
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor:
                    normalizedFocus &&
                    normalizedFocus.rowId !== "header" &&
                    normalizedFocus.rowId
                      ? "#ff6b6b"
                      : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor:
                    normalizedFocus &&
                    normalizedFocus.rowId !== "header" &&
                    normalizedFocus.rowId
                      ? "pointer"
                      : "not-allowed",
                }}
              >
                Delete Row
              </button>
              <button
                onClick={deleteSelectedNormalizedColumn}
                disabled={
                  !normalizedFocus ||
                  normalizedFocus.columnId === "rowIndex" ||
                  !normalizedFocus.columnId
                }
                style={{
                  fontSize: "12px",
                  padding: "4px 8px",
                  backgroundColor:
                    normalizedFocus &&
                    normalizedFocus.columnId !== "rowIndex" &&
                    normalizedFocus.columnId
                      ? "#ff6b6b"
                      : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor:
                    normalizedFocus &&
                    normalizedFocus.columnId !== "rowIndex" &&
                    normalizedFocus.columnId
                      ? "pointer"
                      : "not-allowed",
                }}
              >
                Delete Column
              </button>
            </div>
          </div>
          <div
            style={{
              height: "calc(100% - 60px)",
              overflowX: "auto",
              overflowY: "auto",
            }}
          >
            <ReactGrid
              rows={normalizedGridRows}
              columns={normalizedGridCols}
              onCellsChanged={handleNormalizedChanges}
              onFocusLocationChanged={(loc) => setNormalizedFocus(loc)}
              enableRowSelection
              enableColumnSelection
              stickyTopRows={1}
              stickyLeftColumns={1}
            />
          </div>
        </div>
      )}
    </div>
  );
}
