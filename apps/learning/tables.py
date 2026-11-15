"""Read an uploaded Excel (.xlsx) or CSV file into a list of row dicts (header names are normalised)."""
import csv
import io

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000


class TableError(ValueError):
    """Message is safe to show to the admin."""


def _clean_header(h):
    return str(h or "").strip().lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_table(upload):
    name = (getattr(upload, "name", "") or "").lower()
    if upload.size > MAX_BYTES:
        raise TableError("That file is too large (limit 10 MB). Split it into smaller files.")
    data = upload.read()
    if name.endswith((".xlsx", ".xlsm")):
        grid = _xlsx_rows(data)
    elif name.endswith((".csv", ".txt")):
        grid = _csv_rows(data)
    elif name.endswith(".xls"):
        raise TableError("Old .xls files are not supported. In Excel choose Save As → “Excel Workbook (.xlsx)” and upload that.")
    else:
        raise TableError("Please upload an Excel file (.xlsx) or a CSV file.")
    grid = [r for r in grid if any(_cell(c) for c in r[1])]
    if not grid:
        raise TableError("The file is empty.")
    head_row, head = grid[0]
    headers = [_clean_header(h) for h in head]
    if not any(headers):
        raise TableError("The first row must contain the column names (see the sample file).")
    rows = []
    for rownum, cells in grid[1:MAX_ROWS + 1]:
        d = {h: _cell(c) for h, c in zip(headers, cells) if h}
        d["_row"] = rownum
        rows.append(d)
    if len(grid) - 1 > MAX_ROWS:
        raise TableError(f"Too many rows (limit {MAX_ROWS}). Split the file.")
    return rows


def _xlsx_rows(data):
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise TableError("Couldn't open that Excel file. Is it a real .xlsx file?")
    ws = wb.worksheets[0]
    return [(i, list(row)) for i, row in enumerate(ws.iter_rows(values_only=True), start=1)]


def _csv_rows(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            raise TableError("Couldn't read that file. Save it as “CSV UTF-8” from Excel and try again.")
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [(i, row) for i, row in enumerate(csv.reader(io.StringIO(text), dialect), start=1)]
