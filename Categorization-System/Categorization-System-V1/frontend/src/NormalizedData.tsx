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
  rows: Array<Record<string, unknown>>;
}

interface HistoryState {
  originalGridRows: Row[];
  normalizedGridRows: Row[];
  normalizedRows: NormalizedRow[];
  normalizedGridCols: Column[];
}

interface SavedState {
  normalizedGridRows: Row[];
  normalizedRows: NormalizedRow[];
  normalizedGridCols: Column[];
  timestamp: number;
}

interface FocusLocation {
  rowId: string | number;
  columnId: string | number;
}

interface ActionButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  activeColor: string;
}

interface GridPanelProps {
  title: string;
  rowCount: number;
  width: string;
  flex: string;
  rows: Row[];
  columns: Column[];
  onCellsChanged: (changes: CellChange[]) => void;
  onFocusLocationChanged: (loc: FocusLocation) => void;
  actions: React.ReactNode;
}

interface CategoryOption {
  id: number;
  name: string;
  icon?: string | null;
  type: string;
}

interface CategoriesResponse {
  categories: CategoryOption[];
}

interface EditableCategory extends CategoryOption {
  isDirty?: boolean;
}

interface CategoryUsageResponse {
  id: number;
  name: string;
  transaction_count: number;
  keyword_count: number;
  requires_force: boolean;
}

// Shape of every row stored in normalizedRows state.
// Fields are optional because the user may map only a subset of columns.
interface NormalizedRow {
  date?: string;
  note?: string;
  amount?: number;
}

// ---------- Constants ----------
const TARGET_COLUMNS = ["Date", "Note", "Amount"] as const;
const MAX_HISTORY_SIZE = 100;
const HEADER_ROW_ID = "header";
const ROW_INDEX_COLUMN_ID = "rowIndex";
const NORMALIZED_DATA_STORAGE_KEY = "normalizedDataState";
const API_BASE_URL = "http://localhost:8003";
const DEBUG_LOGGING = true;
const COLUMN_WIDTHS = {
  rowIndex: 40,
  Note: 260,
  default: 140,
} as const;

const GRID_PANEL_HEIGHT = "800px";

const panelHeaderStyle: React.CSSProperties = {
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
};

const panelBodyStyle: React.CSSProperties = {
  height: "calc(100% - 60px)",
  overflowX: "auto",
  overflowY: "auto",
};

const actionGroupStyle: React.CSSProperties = {
  display: "flex",
  gap: "0.5rem",
};

const getActionButtonStyle = (
  disabled: boolean,
  activeColor: string
): React.CSSProperties => ({
  fontSize: "12px",
  padding: "4px 8px",
  backgroundColor: disabled ? "#ccc" : activeColor,
  color: "white",
  border: "none",
  borderRadius: "3px",
  cursor: disabled ? "not-allowed" : "pointer",
});

const ActionButton = ({
  label,
  onClick,
  disabled = false,
  activeColor,
}: ActionButtonProps) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={getActionButtonStyle(disabled, activeColor)}
    >
      {label}
    </button>
  );
};

const GridPanel = ({
  title,
  rowCount,
  width,
  flex,
  rows,
  columns,
  onCellsChanged,
  onFocusLocationChanged,
  actions,
}: GridPanelProps) => {
  return (
    <div
      className="grid-wrapper"
      style={{
        flex,
        width,
        height: GRID_PANEL_HEIGHT,
        maxWidth: width,
        maxHeight: GRID_PANEL_HEIGHT,
        border: "1px solid #444",
        position: "relative",
      }}
    >
      <div style={panelHeaderStyle}>
        <h3 style={{ color: "black", margin: 0 }}>
          {title} ({rowCount} rows)
        </h3>
        <div style={actionGroupStyle}>{actions}</div>
      </div>
      <div style={panelBodyStyle}>
        <ReactGrid
          rows={rows}
          columns={columns}
          onCellsChanged={onCellsChanged}
          onFocusLocationChanged={onFocusLocationChanged}
          enableRowSelection
          enableColumnSelection
          stickyTopRows={1}
          stickyLeftColumns={1}
        />
      </div>
    </div>
  );
};

// ---------- Utils ----------

const getColumnWidth = (
  header: string,
  rows: Array<Record<string, unknown>>
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

const toDisplayText = (value: unknown): string =>
  value === null || value === undefined ? "" : String(value);

const getCellText = (cell: unknown): string =>
  cell?.text ?? toDisplayText(cell?.value);

const debugLog = (...args: unknown[]) => {
  if (DEBUG_LOGGING) {
    console.log("[NormalizedData]", ...args);
  }
};

const formatCurrencyNumber = (num: number): string =>
  new Intl.NumberFormat("id-ID").format(num);

class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const isApiError = (error: unknown): error is ApiError => error instanceof ApiError;

const formatApiDetail = (detail: unknown): string => {
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const maybeMessage = (detail as { message?: unknown }).message;
    if (typeof maybeMessage === "string" && maybeMessage.trim()) {
      return maybeMessage;
    }
    return JSON.stringify(detail);
  }
  return "Unexpected API error";
};

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `HTTP error! status: ${response.status}`;
    let detail: unknown = null;
    try {
      const errorData = await response.json();
      detail = errorData?.detail ?? errorData;
      message = formatApiDetail(detail) || message;
    } catch {
      // Ignore JSON parse failures and keep the default message.
    }
    throw new ApiError(message, response.status, detail);
  }
  return response.json() as Promise<T>;
}

async function fetchCategoryEndpointWithFallback<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const primaryUrl = `${API_BASE_URL}${path}`;
  const adminUrl = `${API_BASE_URL}/admin${path}`;

  try {
    return await fetchJson<T>(primaryUrl, options);
  } catch (primaryError) {
    const shouldRetryWithAdminPath =
      isApiError(primaryError) && [404, 405].includes(primaryError.status);

    if (!shouldRetryWithAdminPath) {
      throw primaryError;
    }

    try {
      return await fetchJson<T>(adminUrl, options);
    } catch (adminError) {
      const bothMissing =
        isApiError(adminError) && [404, 405].includes(adminError.status);

      if (bothMissing) {
        throw new Error(
          "Category write endpoints are unavailable on the running backend. Please restart Categorization-System-V1 backend/main.py, then retry."
        );
      }
      throw adminError;
    }
  }
}

const parseAmount = (text: string): number => {
  if (!text || typeof text !== 'string') return 0;

  const str = text.trim();

  // Handle parentheses for negative amounts (200.00) -> -200.00
  if (str.startsWith('(') && str.endsWith(')')) {
    const inner = str.slice(1, -1);
    const num = Number(inner.replace(/[^0-9.-]/g, ""));
    return num ? -Math.abs(num) : 0;
  }

  // Handle regular negative amounts and currency symbols
  const cleaned = str.replace(/[^0-9.\s-]/g, "").trim();
  const num = Number(cleaned) || 0;

  return num;
};

const convertGridRowsToNormalizedObjects = (
  gridRows: Row[],
  gridColumns: Column[]
): NormalizedRow[] => {
  const valueColumns = gridColumns.filter(
    (column) => column.columnId !== ROW_INDEX_COLUMN_ID
  );

  return gridRows
    .filter((gridRow) => gridRow.rowId !== HEADER_ROW_ID)
    .map((gridRow) => {
      const normalizedRow: NormalizedRow = {};
      valueColumns.forEach((column, idx) => {
        const cellIndex = idx + 1; // +1 to skip rowIndex column
        let cellValue: string | number = getCellText(gridRow.cells[cellIndex]);

        if (column.columnId === "Amount") {
          cellValue = parseAmount(cellValue);
        }

        const normalizedKey = String(column.columnId).toLowerCase() as keyof NormalizedRow;
        normalizedRow[normalizedKey] = cellValue as never;
      });

      return normalizedRow;
    });
};

const createGridRowsFromSourceData = (
  sourceRows: Array<Record<string, unknown>>,
  columns: Column[]
): Row[] => {
  const headerRow: Row = {
    rowId: HEADER_ROW_ID,
    cells: [
      { type: "header", text: "" },
      ...columns
        .slice(1)
        .map((c) => ({ type: "header" as const, text: String(c.columnId) })),
    ],
  };

  const gridDataRows: Row[] = sourceRows.map((sourceRow, idx) => ({
    rowId: `nrow-${idx}`,
    cells: [
      { type: "header", text: String(idx + 1) },
      ...columns.slice(1).map((col) => {
        const matchingKey = Object.keys(sourceRow).find(
          (k) => k.toLowerCase() === String(col.columnId).toLowerCase()
        );
        return {
          type: "text" as const,
          text: toDisplayText(matchingKey ? sourceRow[matchingKey] : ""),
        };
      }),
    ],
  }));

  return [headerRow, ...gridDataRows];
};

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

  return { pushState, undo, redo };
};

// ---------- Component ----------
export function NormalizedData() {
  // State
  const [data, setData] = useState<ParsedData | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [normalizedRows, setNormalizedRows] = useState<NormalizedRow[]>([]);
  const [submitMessage, setSubmitMessage] = useState<string>("");
  const [originalGridCols, setOriginalGridCols] = useState<Column[]>([]);
  const [originalGridRows, setOriginalGridRows] = useState<Row[]>([]);
  const [normalizedGridCols, setNormalizedGridCols] = useState<Column[]>([]);
  const [normalizedGridRows, setNormalizedGridRows] = useState<Row[]>([]);
  const [originalFocus, setOriginalFocus] = useState<FocusLocation | null>(null);
  const [normalizedFocus, setNormalizedFocus] = useState<FocusLocation | null>(null);
  const [isCalculated, setIsCalculated] = useState<boolean>(false);
  const [editableCategories, setEditableCategories] = useState<EditableCategory[]>([]);
  const [isCategoryLoading, setIsCategoryLoading] = useState<boolean>(false);
  const [savingCategoryId, setSavingCategoryId] = useState<number | null>(null);
  const [deletingCategoryId, setDeletingCategoryId] = useState<number | null>(null);
  const [isCreatingCategory, setIsCreatingCategory] = useState<boolean>(false);
  const [newCategoryName, setNewCategoryName] = useState<string>("");
  const [newCategoryType, setNewCategoryType] = useState<"expense" | "income">("expense");
  const [categorySearch, setCategorySearch] = useState<string>("");
  const [categoryMessage, setCategoryMessage] = useState<string>("");

  // Reset calculation state when normalized data changes
  useEffect(() => {
    setIsCalculated(false);
  }, [normalizedRows]);

  // History management
  const { pushState, undo, redo } = useHistory();

  // Memoized values
  const sourceHeaders = useMemo(
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

  const groupedCategories = useMemo(() => {
    const query = categorySearch.trim().toLowerCase();
    const filtered = editableCategories.filter((category) => {
      if (!query) return true;
      return category.name.toLowerCase().includes(query);
    });

    const expense = filtered
      .filter((category) => category.type === "expense")
      .sort((a, b) => a.name.localeCompare(b.name));
    const income = filtered
      .filter((category) => category.type === "income")
      .sort((a, b) => a.name.localeCompare(b.name));

    return { expense, income };
  }, [categorySearch, editableCategories]);

  const refreshCategories = useCallback(async () => {
    setIsCategoryLoading(true);
    try {
      const categoriesResponse = await fetchJson<CategoriesResponse>(`${API_BASE_URL}/categories`);
      setEditableCategories(categoriesResponse.categories.map((category) => ({ ...category, isDirty: false })));
      setCategoryMessage("");
    } catch (error) {
      console.error("Category refresh error:", error);
      const message = error instanceof Error ? error.message : "Unknown error";
      setCategoryMessage(`Category error: ${message}`);
    } finally {
      setIsCategoryLoading(false);
    }
  }, []);

  const handleCategoryFieldChange = useCallback(
    (categoryId: number, field: "name" | "type", value: string) => {
      setEditableCategories((prev) =>
        prev.map((category) =>
          category.id === categoryId
            ? {
                ...category,
                [field]: value,
                isDirty: true,
              }
            : category
        )
      );
    },
    []
  );

  const handleSaveCategory = useCallback(
    async (category: EditableCategory) => {
      const trimmedName = category.name.trim();
      if (!trimmedName) {
        setCategoryMessage("Category name cannot be empty.");
        return;
      }
      if (category.type !== "income" && category.type !== "expense") {
        setCategoryMessage("Category type must be income or expense.");
        return;
      }

      setSavingCategoryId(category.id);
      try {
        await fetchCategoryEndpointWithFallback<CategoryOption>(`/categories/${category.id}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: trimmedName,
            type: category.type,
          }),
        });

        setEditableCategories((prev) =>
          prev.map((item) =>
            item.id === category.id
              ? {
                  ...item,
                  name: trimmedName,
                  isDirty: false,
                }
              : item
          )
        );
        setCategoryMessage(`Saved category: ${trimmedName}`);
      } catch (error) {
        console.error("Category save error:", error);
        const message = error instanceof Error ? error.message : "Unknown error";
        setCategoryMessage(`Category save failed: ${message}`);
      } finally {
        setSavingCategoryId(null);
      }
    },
    []
  );

  const handleCreateCategory = useCallback(async () => {
    const trimmedName = newCategoryName.trim();
    if (!trimmedName) {
      setCategoryMessage("Please type a category name before adding.");
      return;
    }

    setIsCreatingCategory(true);
    try {
      const created = await fetchCategoryEndpointWithFallback<CategoryOption>("/categories", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: trimmedName,
          type: newCategoryType,
        }),
      });

      setEditableCategories((prev) => [
        ...prev,
        {
          ...created,
          isDirty: false,
        },
      ]);
      setNewCategoryName("");
      setCategoryMessage(`Added category: ${created.name}`);
    } catch (error) {
      console.error("Category create error:", error);
      const message = error instanceof Error ? error.message : "Unknown error";
      setCategoryMessage(`Category create failed: ${message}`);
    } finally {
      setIsCreatingCategory(false);
    }
  }, [newCategoryName, newCategoryType]);

  const handleDeleteCategory = useCallback(async (category: EditableCategory) => {
    setDeletingCategoryId(category.id);
    try {
      const usage = await fetchCategoryEndpointWithFallback<CategoryUsageResponse>(`/categories/${category.id}/usage`);

      let forceDelete = false;
      if (usage.transaction_count > 0) {
        const confirmToken = `DELETE ${category.name}`;
        const confirmation = window.prompt(
          `This category has ${usage.transaction_count} transactions and ${usage.keyword_count} keyword rules.\n` +
          `Deleting it will also delete those transactions.\n\n` +
          `To confirm, type exactly: ${confirmToken}`
        );
        if (confirmation !== confirmToken) {
          setCategoryMessage("Delete canceled. Confirmation text did not match.");
          return;
        }
        forceDelete = true;
      } else {
        const confirmed = window.confirm(
          `Delete category '${category.name}'? This cannot be undone.`
        );
        if (!confirmed) {
          setCategoryMessage("Delete canceled.");
          return;
        }
      }

      const query = forceDelete ? "?force=true" : "";
      await fetchCategoryEndpointWithFallback<{ deleted: boolean }>(`/categories/${category.id}${query}`, {
        method: "DELETE",
      });

      setEditableCategories((prev) => prev.filter((item) => item.id !== category.id));
      setCategoryMessage(`Deleted category: ${category.name}`);
    } catch (error) {
      console.error("Category delete error:", error);
      const message = error instanceof Error ? error.message : "Unknown error";
      setCategoryMessage(`Category delete failed: ${message}`);
    } finally {
      setDeletingCategoryId(null);
    }
  }, []);

  useEffect(() => {
    refreshCategories();
  }, [refreshCategories]);

  const isInitialState = !data;

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

  // Load a source file into the original grid while preserving normalized data.
  const handleSourceFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${API_BASE_URL}/parse`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const parsedData: ParsedData = await response.json();

        setData(parsedData);

        const sourceColumnIds = Object.keys(parsedData.rows[0] || {});
        const sourceColumns: Column[] = [
          {
            columnId: "rowIndex",
            width: COLUMN_WIDTHS.rowIndex,
            resizable: false,
          },
          ...sourceColumnIds.map((header) => ({
            columnId: header,
            width: getColumnWidth(header, parsedData.rows),
            resizable: true,
          })),
        ];

        const sourceGridRows = createGridRowsFromSourceData(parsedData.rows, [
          {
            columnId: "rowIndex",
            width: COLUMN_WIDTHS.rowIndex,
            resizable: false,
          },
          ...sourceColumnIds.map((columnId) => ({
            columnId,
            width: 100,
            resizable: true,
          })),
        ]);

        setOriginalGridCols(sourceColumns);
        setOriginalGridRows(sourceGridRows);
        setSubmitMessage("");
        setMapping({});
      } catch (err) {
        console.error("Parsing error:", err);
      }
    },
    []
  );

  // Normalize mapped source columns and append them to the normalized grid.
  const handleAppendNormalizedData = useCallback(() => {
    if (!originalGridRows.length) return;

    const selectedMappedTargets = Object.values(mapping).filter(Boolean);
    if (!selectedMappedTargets.length) {
      setSubmitMessage("Please map at least one column before normalizing.");
      return;
    }

    const targetColumnsToInclude = TARGET_COLUMNS.filter((targetColumn) =>
      selectedMappedTargets.includes(targetColumn)
    );

    // Initialize normalized columns on first run only.
    let normalizedColumns: Column[] = normalizedGridCols;
    if (!normalizedGridCols.length) {
      normalizedColumns = [
        {
          columnId: "rowIndex",
          width: COLUMN_WIDTHS.rowIndex,
          resizable: false,
        },
        ...targetColumnsToInclude.map((targetColumn) => ({
          columnId: targetColumn,
          width:
            COLUMN_WIDTHS[targetColumn as keyof typeof COLUMN_WIDTHS] ||
            COLUMN_WIDTHS.default,
          resizable: true,
        })),
      ];
      setNormalizedGridCols(normalizedColumns);
    }

    const sourceDataRows = originalGridRows.filter(
      (row) => row.rowId !== HEADER_ROW_ID
    );
    const normalizedRowsToAppend: NormalizedRow[] = [];
    const normalizedGridRowsToAppend: Row[] = [];

    // Continue row numbering from existing normalized rows.
    const currentRowCount = normalizedRows.length;

    sourceDataRows.forEach((sourceRow, idx) => {
      const normalizedRow: Record<string, string | number> = {};
      const gridCells: Array<{ type: string; text: string }> = [
        { type: "header", text: String(currentRowCount + idx + 1) },
      ];

      targetColumnsToInclude.forEach((targetColumn) => {
        const sourceColumnIndex = originalGridCols.findIndex(
          (column) => mapping[column.columnId] === targetColumn
        );

        let cellText = "";
        if (sourceColumnIndex >= 0) {
          cellText = getCellText(sourceRow.cells[sourceColumnIndex]);
        }

        if (targetColumn === "Amount") {
          normalizedRow.amount = parseAmount(cellText);
        } else {
          normalizedRow[targetColumn.toLowerCase()] = cellText;
        }

        gridCells.push({ type: "text", text: cellText });
      });

      normalizedRowsToAppend.push(normalizedRow);
      normalizedGridRowsToAppend.push({
        rowId: `nrow-${currentRowCount + idx}`,
        cells: gridCells,
      });
    });

    // Append to normalized data instead of replacing it.
    const updatedNormalizedObjects = [
      ...normalizedRows,
      ...normalizedRowsToAppend,
    ];

    // Create header row if needed
    const headerRow: Row = {
      rowId: HEADER_ROW_ID,
      cells: [
        { type: "header", text: "" },
        ...targetColumnsToInclude.map((targetColumn) => ({
          type: "header" as const,
          text: targetColumn,
        })),
      ],
    };

    // Append rows under a single header row.
    const existingDataRows = normalizedGridRows.filter(
      (r) => r.rowId !== HEADER_ROW_ID
    );
    const allRows = [
      headerRow,
      ...existingDataRows,
      ...normalizedGridRowsToAppend,
    ];

    setNormalizedRows(updatedNormalizedObjects);
    setNormalizedGridRows(allRows);
    setSubmitMessage("");

    // Update history
    pushState({
      originalGridRows,
      normalizedGridRows: allRows,
      normalizedRows: updatedNormalizedObjects,
      normalizedGridCols: normalizedColumns,
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

  // Grid edit handlers
  const handleOriginalGridChanges = useCallback(
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
            return change ? { ...cell, text: getCellText(change.newCell) } : cell;
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
      normalizedGridCols,
      pushState,
    ]
  );

  const handleNormalizedGridChanges = useCallback(
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
            return change ? { ...cell, text: getCellText(change.newCell) } : cell;
          }),
        };
      });

      // Check if anything actually changed
      if (JSON.stringify(updatedRows) === JSON.stringify(normalizedGridRows)) {
        return;
      }

      const newObjects = convertGridRowsToNormalizedObjects(updatedRows, normalizedGridCols);

      setNormalizedGridRows(updatedRows);
      setNormalizedRows(newObjects);
      pushState({
        originalGridRows,
        normalizedGridRows: updatedRows,
        normalizedRows: newObjects,
        normalizedGridCols,
      });
    },
    [
      normalizedGridRows,
      normalizedGridCols,
      originalGridRows,
      pushState,
    ]
  );

  // Download and submit
  const handleDownload = useCallback(() => {
    if (!normalizedRows.length) return;

    const headers = ["Date", "Note", "Amount"];
    const csvContent = [
      headers.join(","),
      ...normalizedRows.map(
        (r) => `${r.date ?? ""},${r.note ?? ""},${r.amount ?? 0}`
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

  const handleCalculate = useCallback(() => {
    if (normalizedRows.length === 0) {
      setSubmitMessage("No data to calculate. Please normalize some data first.");
      setIsCalculated(false);
      return;
    }

    // Validate data
    const invalidRows = normalizedRows.filter(row =>
      !row.date || row.amount === undefined || row.amount === null || isNaN(row.amount)
    );

    if (invalidRows.length > 0) {
      setSubmitMessage(`Validation failed: ${invalidRows.length} rows have missing or invalid date/amount fields.`);
      setIsCalculated(false);
      return;
    }

    const { count, sum } = normalizedSummary;
    setSubmitMessage(`Calculated: ${count} transactions with total amount ${formatCurrencyNumber(sum)}. Ready to submit.`);
    setIsCalculated(true);
  }, [normalizedSummary, normalizedRows]);

  const handleSubmit = useCallback(async () => {
    if (!isCalculated) {
      setSubmitMessage("Please calculate first to validate your data before submitting.");
      return;
    }
    try {
      // Re-validate before submission to guard against stale/edited rows after Calculate.
      const invalidRows = normalizedRows.filter(row =>
        !row.date || row.amount === undefined || row.amount === null || isNaN(row.amount)
      );

      if (invalidRows.length > 0) {
        setSubmitMessage(`Validation failed: ${invalidRows.length} rows have missing or invalid date/amount fields.`);
        return;
      }

      // Check category types exist
      const response = await fetch(`${API_BASE_URL}/categories/types`);
      if (!response.ok) {
        throw new Error("Failed to check category types");
      }

      const { types } = await response.json();
      const hasIncome = types.includes('income');
      const hasExpense = types.includes('expense');

      if (!hasIncome || !hasExpense) {
        const missing = [];
        if (!hasIncome) missing.push('income');
        if (!hasExpense) missing.push('expense');
        setSubmitMessage(`You should define category type that does not exist in database first to submit data. Missing: ${missing.join(', ')}`);
        return;
      }

      // Submit the data
      const submitResponse = await fetch(`${API_BASE_URL}/transactions/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(normalizedRows)
      });

      if (!submitResponse.ok) {
        const errorData = await submitResponse.json();
        throw new Error(errorData.detail || "Failed to submit transactions");
      }

      const result = await submitResponse.json();
      const { sum } = normalizedSummary;
      setSubmitMessage(
        `Successfully added ${result.inserted} transactions with sum amount ${formatCurrencyNumber(sum)}.`
      );
      setIsCalculated(false); // Reset calculation state after successful submission
      debugLog("Submitted normalized rows:", normalizedRows);
    } catch (error) {
      console.error("Submit error:", error);
      const message = error instanceof Error ? error.message : "Unknown error";
      setSubmitMessage(`Error: ${message}`);
    }
  }, [normalizedSummary, normalizedRows, isCalculated]);

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
      localStorage.setItem(NORMALIZED_DATA_STORAGE_KEY, JSON.stringify(savedState));
      alert("Normalized data saved successfully!");
    } catch (error) {
      console.error("Error saving data:", error);
      alert("Failed to save data. Please try again.");
    }
  }, [normalizedGridRows, normalizedRows, normalizedGridCols]);

  const handleLoad = useCallback(() => {
    try {
      const savedData = localStorage.getItem(NORMALIZED_DATA_STORAGE_KEY);
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

  // Delete the focused row in the original grid.
  const handleDeleteOriginalRow = useCallback(() => {
    debugLog("Delete row requested on original grid", {
      focus: originalFocus,
      rowCount: originalGridRows.length,
    });

    if (!originalGridRows.length) {
      debugLog("Original grid has no rows to delete.");
      return;
    }

    if (!originalFocus) {
      debugLog("Original grid has no active focus.");
      return;
    }

    const { rowId } = originalFocus;

    if (rowId === HEADER_ROW_ID) {
      debugLog("Header row cannot be deleted on original grid.");
      return;
    }

    if (!rowId || rowId === "") {
      debugLog("Original rowId is invalid.", { rowId });
      return;
    }

    const updatedRows = originalGridRows.filter((r) => r.rowId !== rowId);

    // Keep parsed source data aligned with the visible original grid.
    if (data) {
      const rowIndex = originalGridRows.findIndex((r) => r.rowId === rowId) - 1; // -1 because header is at index 0
      if (rowIndex >= 0 && rowIndex < data.rows.length) {
        const updatedDataRows = data.rows.filter((_, idx) => idx !== rowIndex);
        setData({ ...data, rows: updatedDataRows });
      }
    }

    setOriginalGridRows(updatedRows);

    // Move focus to the nearest available row.
    const remainingDataRows = updatedRows.filter((r) => r.rowId !== HEADER_ROW_ID);
    if (remainingDataRows.length > 0) {
      // Try to focus on the same position, or the last row if we deleted the last one
      const deletedIndex =
        originalGridRows.findIndex((r) => r.rowId === rowId) - 1; // -1 for header
      const nextRowIndex = Math.min(deletedIndex, remainingDataRows.length - 1);
      const nextRow = remainingDataRows[nextRowIndex];
      if (nextRow) {
        setOriginalFocus({
          rowId: nextRow.rowId,
          columnId: originalFocus.columnId || ROW_INDEX_COLUMN_ID,
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
    normalizedGridCols,
    pushState,
    data,
  ]);

  // Delete the focused column in the original grid.
  const handleDeleteOriginalColumn = useCallback(() => {
    debugLog("Delete column requested on original grid", {
      focus: originalFocus,
      columns: originalGridCols.map((c) => c.columnId),
    });

    if (!originalGridRows.length) {
      debugLog("Original grid has no data to delete from.");
      return;
    }

    if (!originalFocus) {
      debugLog("Original grid has no active focus.");
      return;
    }

    const { columnId } = originalFocus;

    if (columnId === ROW_INDEX_COLUMN_ID) {
      debugLog("Row index column cannot be deleted.");
      return;
    }

    if (!columnId || columnId === "") {
      debugLog("Original columnId is invalid.", { columnId });
      return;
    }

    const colIndex = originalGridCols.findIndex((c) => c.columnId === columnId);

    if (colIndex < 0) {
      debugLog("Original column not found.", { columnId });
      return;
    }

    const newCols = originalGridCols.filter((c) => c.columnId !== columnId);

    const updatedRows = originalGridRows.map((row) => ({
      ...row,
      cells: row.cells.filter((_, idx) => idx !== colIndex),
    }));

    setOriginalGridCols(newCols);
    setOriginalGridRows(updatedRows);

    // Move focus to the nearest available column.
    const remainingCols = newCols.filter((c) => c.columnId !== ROW_INDEX_COLUMN_ID);
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
            rowId: originalFocus.rowId || HEADER_ROW_ID,
            columnId: nextCol.columnId,
          });
        }, 10);
      }
    } else {
      setTimeout(() => {
        setOriginalFocus({
          rowId: originalFocus.rowId || HEADER_ROW_ID,
          columnId: ROW_INDEX_COLUMN_ID,
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
    normalizedGridCols,
    pushState,
  ]);

  // Delete the focused row in the normalized grid.
  const handleDeleteNormalizedRow = useCallback(() => {
    debugLog("Delete row requested on normalized grid", {
      focus: normalizedFocus,
      rowCount: normalizedGridRows.length,
    });

    if (!normalizedGridRows.length) {
      debugLog("Normalized grid has no rows to delete.");
      return;
    }

    if (!normalizedFocus) {
      debugLog("Normalized grid has no active focus.");
      return;
    }

    const { rowId } = normalizedFocus;

    if (rowId === HEADER_ROW_ID) {
      debugLog("Header row cannot be deleted on normalized grid.");
      return;
    }

    if (!rowId || rowId === "") {
      debugLog("Normalized rowId is invalid.", { rowId });
      return;
    }

    const updatedRows = normalizedGridRows.filter((r) => r.rowId !== rowId);

    const newObjects = convertGridRowsToNormalizedObjects(updatedRows, normalizedGridCols);

    setNormalizedGridRows(updatedRows);
    setNormalizedRows(newObjects);

    // Move focus to the nearest available row.
    const remainingDataRows = updatedRows.filter((r) => r.rowId !== HEADER_ROW_ID);
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
            columnId: normalizedFocus.columnId || ROW_INDEX_COLUMN_ID,
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
      normalizedGridCols,
    });
  }, [
    normalizedGridRows,
    normalizedFocus,
    normalizedGridCols,
    originalGridRows,
    pushState,
  ]);

  // Delete the focused column in the normalized grid.
  const handleDeleteNormalizedColumn = useCallback(() => {
    debugLog("Delete column requested on normalized grid", {
      focus: normalizedFocus,
      columns: normalizedGridCols.map((c) => c.columnId),
    });

    if (!normalizedGridRows.length) {
      debugLog("Normalized grid has no data to delete from.");
      return;
    }

    if (!normalizedFocus) {
      debugLog("Normalized grid has no active focus.");
      return;
    }

    const { columnId } = normalizedFocus;

    if (columnId === ROW_INDEX_COLUMN_ID) {
      debugLog("Row index column cannot be deleted.");
      return;
    }

    if (!columnId || columnId === "") {
      debugLog("Normalized columnId is invalid.", { columnId });
      return;
    }

    const colIndex = normalizedGridCols.findIndex(
      (c) => c.columnId === columnId
    );

    if (colIndex < 0) {
      debugLog("Normalized column not found.", { columnId });
      return;
    }

    const newCols = normalizedGridCols.filter((c) => c.columnId !== columnId);

    const updatedRows = normalizedGridRows.map((row) => ({
      ...row,
      cells: row.cells.filter((_, idx) => idx !== colIndex),
    }));

    const newObjects = convertGridRowsToNormalizedObjects(updatedRows, newCols);

    setNormalizedGridCols(newCols);
    setNormalizedGridRows(updatedRows);
    setNormalizedRows(newObjects);

    // Move focus to the nearest available column.
    const remainingCols = newCols.filter((c) => c.columnId !== ROW_INDEX_COLUMN_ID);
    if (remainingCols.length > 0) {
      // Try to focus on the same position, or the last column if we deleted the last one
      const deletedIndex =
        normalizedGridCols.findIndex((c) => c.columnId === columnId) - 1; // -1 for rowIndex
      const nextColIndex = Math.min(deletedIndex, remainingCols.length - 1);
      const nextCol = remainingCols[nextColIndex];
      if (nextCol) {
        setTimeout(() => {
          setNormalizedFocus({
            rowId: normalizedFocus.rowId || HEADER_ROW_ID,
            columnId: nextCol.columnId,
          });
        }, 10);
      }
    } else {
      setTimeout(() => {
        setNormalizedFocus({
          rowId: normalizedFocus.rowId || HEADER_ROW_ID,
          columnId: ROW_INDEX_COLUMN_ID,
        });
      }, 10);
    }

    pushState({
      originalGridRows,
      normalizedGridRows: updatedRows,
      normalizedRows: newObjects,
      normalizedGridCols: newCols,
    });
  }, [
    normalizedGridRows,
    normalizedGridCols,
    normalizedFocus,
    originalGridRows,
    pushState,
  ]);

  // ---------- Render ----------
  return (
    <div className={`workspace-scroll${isInitialState ? " initial-state" : ""}`}>
      <div
        style={{
          display: "flex",
          gap: "2rem",
          justifyContent: "center",
          alignItems: isInitialState ? "center" : "flex-start",
          marginTop: isInitialState ? "0" : "2rem",
          minHeight: isInitialState ? "calc(100dvh - 4.5rem)" : "auto",
          width: "max-content",
          minWidth: "100%",
        }}
      >
        {/* Original Data Grid */}
        {data && (
          <GridPanel
            title="Original Data"
            rowCount={data.rows.length}
            width="800px"
            flex="0 0 800px"
            rows={originalGridRows}
            columns={originalGridCols}
            onCellsChanged={handleOriginalGridChanges}
            onFocusLocationChanged={(loc) => setOriginalFocus(loc)}
            actions={
              <>
                <ActionButton
                  label="Delete Row"
                  onClick={handleDeleteOriginalRow}
                  disabled={
                    !originalFocus ||
                    originalFocus.rowId === HEADER_ROW_ID ||
                    !originalFocus.rowId
                  }
                  activeColor="#ff6b6b"
                />
                <ActionButton
                  label="Delete Column"
                  onClick={handleDeleteOriginalColumn}
                  disabled={
                    !originalFocus ||
                    originalFocus.columnId === ROW_INDEX_COLUMN_ID ||
                    !originalFocus.columnId
                  }
                  activeColor="#ff6b6b"
                />
              </>
            }
          />
        )}

      {/* Control Panel */}
      <div style={{ flex: "0 0 auto", minWidth: "300px", textAlign: "center" }}>
        <div className="file-input-wrapper">
          <input
            type="file"
            id="file-upload"
            accept=".json,.txt,.xlsx,.csv"
            onChange={handleSourceFileChange}
          />
          <label htmlFor="file-upload" className="file-upload-label">
            Choose File
          </label>
        </div>
        <p className="file-note">Only .xlsx .csv .txt .json files</p>

        {data && (
          <div className="admin-panel" style={{ marginLeft: "auto", marginRight: "auto" }}>
            <h4 style={{ marginTop: 0, marginBottom: "0.5rem", textAlign: "center" }}>Column Mapping</h4>
            <p className="admin-muted" style={{ marginTop: 0, marginBottom: "0.75rem", textAlign: "center" }}>
              Match your file columns to Date, Note, and Amount.
            </p>

            {sourceHeaders.map((header) => (
              <div key={header} style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <label style={{ minWidth: "96px", textAlign: "left" }}>{header}</label>
                <select
                  value={mapping[header] || ""}
                  onChange={(e) =>
                    setMapping((prev) => ({
                      ...prev,
                      [header]: e.target.value,
                    }))
                  }
                  style={{ flex: 1 }}
                >
                  <option value="">Select field</option>
                  <option value="Date">Date</option>
                  <option value="Note">Note</option>
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
                justifyContent: "center",
              }}
            >
              <button onClick={handleAppendNormalizedData}>Add Data</button>
              <button onClick={handleDownload} disabled={!normalizedRows.length}>
                Download
              </button>
              <button onClick={handleCalculate} disabled={!normalizedRows.length}>
                Calculate
              </button>
              <button onClick={handleSubmit} disabled={!normalizedRows.length || !isCalculated}>
                Submit
              </button>
            </div>

            {submitMessage && (
              <p className="admin-muted" style={{ marginTop: "0.75rem", textAlign: "center" }}>
                {submitMessage}
              </p>
            )}
          </div>
        )}

        <div className="admin-panel" style={{ marginLeft: "auto", marginRight: "auto" }}>
          <h4 style={{ marginTop: 0, marginBottom: "0.5rem", textAlign: "center" }}>Category Manager</h4>
          <p className="admin-muted" style={{ marginTop: 0, marginBottom: "0.75rem", textAlign: "center" }}>
            Search, add, edit, and delete categories in one place.
          </p>
          <p className="admin-muted" style={{ marginTop: 0, marginBottom: "0.75rem", textAlign: "center" }}>
            Categories are grouped by type to make long lists easier to manage.
          </p>

          <div className="category-row">
            <input
              type="text"
              value={categorySearch}
              onChange={(e) => setCategorySearch(e.target.value)}
              placeholder="Search category name"
              style={{ width: "100%" }}
            />
          </div>

          <div className="category-row" style={{ marginTop: "0.5rem" }}>
            <input
              type="text"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="New category name"
              style={{ flex: 1 }}
            />
            <select
              value={newCategoryType}
              onChange={(e) => setNewCategoryType(e.target.value as "expense" | "income")}
              style={{ width: "110px" }}
            >
              <option value="expense">expense</option>
              <option value="income">income</option>
            </select>
            <button onClick={handleCreateCategory} disabled={isCreatingCategory}>
              {isCreatingCategory ? "Adding..." : "Add"}
            </button>
          </div>

          <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.75rem" }}>
            <button onClick={refreshCategories} disabled={isCategoryLoading}>
              {isCategoryLoading ? "Loading categories..." : "Refresh Categories"}
            </button>
          </div>

          <div style={{ maxHeight: "300px", overflowY: "auto" }}>
            {groupedCategories.expense.length === 0 && groupedCategories.income.length === 0 && !isCategoryLoading && (
              <p className="admin-muted" style={{ textAlign: "center" }}>No categories found.</p>
            )}

            {(["expense", "income"] as const).map((groupType) => {
              const groupItems = groupedCategories[groupType];
              if (!groupItems.length) return null;

              return (
                <details key={groupType} className="admin-section">
                  <summary className="category-group-summary">
                    {groupType} ({groupItems.length})
                  </summary>

                  <div style={{ textAlign: "left", marginTop: "0.5rem" }}>
                    {groupItems.map((category) => (
                      <div key={category.id} className="admin-section" style={{ marginTop: "0.5rem" }}>
                        <label style={{ display: "block", marginBottom: "0.25rem" }}>Name</label>
                        <input
                          type="text"
                          value={category.name}
                          onChange={(e) => handleCategoryFieldChange(category.id, "name", e.target.value)}
                          style={{ width: "100%", marginBottom: "0.4rem" }}
                        />
                        <label style={{ display: "block", marginBottom: "0.25rem" }}>Type</label>
                        <select
                          value={category.type}
                          onChange={(e) => handleCategoryFieldChange(category.id, "type", e.target.value)}
                          style={{ width: "100%", marginBottom: "0.4rem" }}
                        >
                          <option value="expense">expense</option>
                          <option value="income">income</option>
                        </select>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.35rem" }}>
                          <span className="admin-muted">ID: {category.id}</span>
                          <div className="category-row" style={{ justifyContent: "flex-end" }}>
                            <button
                              onClick={() => handleSaveCategory(category)}
                              disabled={!category.isDirty || savingCategoryId === category.id}
                            >
                              {savingCategoryId === category.id ? "Saving..." : "Save"}
                            </button>
                            <button
                              onClick={() => handleDeleteCategory(category)}
                              disabled={deletingCategoryId === category.id}
                              style={{ backgroundColor: "#fee2e2", borderColor: "#fecaca" }}
                            >
                              {deletingCategoryId === category.id ? "Deleting..." : "Delete"}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              );
            })}
          </div>

          {categoryMessage && <p className="admin-muted" style={{ marginTop: "0.75rem", textAlign: "center" }}>{categoryMessage}</p>}
        </div>
      </div>

        {/* Normalized Data Grid */}
        {data && normalizedGridRows.length > 0 && (
          <GridPanel
            title="Normalized Data"
            rowCount={normalizedRows.length}
            width="600px"
            flex="0 0 650px"
            rows={normalizedGridRows}
            columns={normalizedGridCols}
            onCellsChanged={handleNormalizedGridChanges}
            onFocusLocationChanged={(loc) => setNormalizedFocus(loc)}
            actions={
              <>
                <ActionButton
                  label="Save"
                  onClick={handleSave}
                  disabled={!normalizedRows.length}
                  activeColor="#4CAF50"
                />
                <ActionButton
                  label="Load"
                  onClick={handleLoad}
                  activeColor="#2196F3"
                />
                <ActionButton
                  label="Delete Row"
                  onClick={handleDeleteNormalizedRow}
                  disabled={
                    !normalizedFocus ||
                    normalizedFocus.rowId === HEADER_ROW_ID ||
                    !normalizedFocus.rowId
                  }
                  activeColor="#ff6b6b"
                />
                <ActionButton
                  label="Delete Column"
                  onClick={handleDeleteNormalizedColumn}
                  disabled={
                    !normalizedFocus ||
                    normalizedFocus.columnId === ROW_INDEX_COLUMN_ID ||
                    !normalizedFocus.columnId
                  }
                  activeColor="#ff6b6b"
                />
              </>
            }
          />
        )}
      </div>
    </div>
  );
}
