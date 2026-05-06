
from pathlib import Path
import io
import re
import pandas as pd
import tempfile
import contextlib
import os
import sys


def normalize_text(value):
    if pd.isna(value):
        return ""

    text = str(value)

    # Fix corrupted old XLS text where letters appear as:
    # I�t�e�m� �C�o�d�e�
    # or include null bytes from UTF-16/OLE exports.
    text = (
        text.replace("\x00", "")
            .replace("\ufffd", "")   # replacement character �
            .replace("�", "")
            .replace("\ufeff", "")
            .replace("\xa0", " ")
    )

    text = text.strip()
    text = " ".join(text.split())

    if text.lower() in {"nan", "none", "nat"}:
        return ""

    return text

def normalize_code(value):
    text = normalize_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text

def to_num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

def make_display_name(text):
    text = normalize_text(text)
    if not text:
        return text
    replacements = [
        ("  ", " "), (" ,", ","), ("MG CAP ", "MG CAP, "), ("MG TAB ", "MG TAB, "),
        ("EFF TAB ", "EFF TAB, "), ("EFF. TAB ", "EFF. TAB, "), ("CAPLET TAB ", "CAPLET TAB, "),
        ("CAPLETS ", "CAPLETS, "), ("TAB ", "TAB, "), ("TABS ", "TABS, "), ("SYRUP ", "SYRUP, "),
        ("DROPS ", "DROPS, "), ("CREAM ", "CREAM, "), ("GEL ", "GEL, "), ("LOTION ", "LOTION, "),
        ("SUPP ", "SUPP, "), ("SUSP ", "SUSP, "), ("CAP ", "CAP, "), ("TABS'S", "TAB'S"),
    ]
    for a, b in replacements:
        text = text.replace(a, b)
    return " ".join(text.replace(" ,", ",").split())

def classify_abc(cum_share):
    if cum_share <= 0.70:
        return "A"
    if cum_share <= 0.90:
        return "B"
    return "C"

def safe_sheet_name(name):
    return name[:31]





def _uploaded_file_bytes(uploaded_file):
    """
    Read Streamlit UploadedFile safely.
    """
    if uploaded_file is None:
        return b""
    if isinstance(uploaded_file, (bytes, bytearray)):
        return bytes(uploaded_file)
    if hasattr(uploaded_file, "getvalue"):
        try:
            return uploaded_file.getvalue()
        except Exception:
            pass
    try:
        uploaded_file.seek(0)
        data = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return data
    except Exception:
        raise RuntimeError("Could not read uploaded file bytes. Please re-upload the file.")

def _read_excel_from_tempfile(file_bytes, suffix, header=None, sheet_name=0, engine=None):
    suffix = suffix or ".xls"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                if engine:
                    return pd.read_excel(tmp_path, header=header, sheet_name=sheet_name, engine=engine)
                return pd.read_excel(tmp_path, header=header, sheet_name=sheet_name)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

def _read_excel_with_calamine(file_bytes, suffix, header=None, sheet_name=0):
    """
    Calamine is more stable than xlrd for many old ERP .XLS exports.
    Requires: python-calamine
    """
    data = io.BytesIO(file_bytes)
    return pd.read_excel(data, header=header, sheet_name=sheet_name, engine="calamine")

def read_excel_any(uploaded_file, header=None, sheet_name=0):
    """
    v5.0:
    - For .xls/.xlsx/.xlsm, try calamine first.
    - Fallback to tempfile + xlrd/openpyxl.
    This is designed to fix persistent:
      I/O operation on closed file
    with old ERP .XLS exports.
    """
    suffix = Path(uploaded_file.name).suffix.lower()
    file_bytes = _uploaded_file_bytes(uploaded_file)

    if suffix == ".csv":
        data = io.BytesIO(file_bytes)
        return pd.read_csv(data, header=header, encoding_errors="ignore")

    # First try calamine for Excel files.
    if suffix in {".xls", ".xlsx", ".xlsm", ".xlsb"}:
        try:
            return _read_excel_with_calamine(file_bytes, suffix=suffix, header=header, sheet_name=sheet_name)
        except Exception:
            pass

    # Fallbacks
    if suffix == ".xls":
        return _read_excel_from_tempfile(file_bytes, suffix=".xls", header=header, sheet_name=sheet_name, engine="xlrd")

    if suffix in {".xlsx", ".xlsm"}:
        try:
            data = io.BytesIO(file_bytes)
            return pd.read_excel(data, header=header, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            return _read_excel_from_tempfile(file_bytes, suffix=suffix, header=header, sheet_name=sheet_name, engine="openpyxl")

    return _read_excel_from_tempfile(file_bytes, suffix=suffix or ".xlsx", header=header, sheet_name=sheet_name, engine=None)


def find_col(df, candidates, exact=False):
    """
    Safer column matcher.

    Priority:
    1) exact normalized match
    2) normalized match ignoring spaces/underscores
    3) substring match

    This prevents generic candidate "code" from matching STORE CODE before ITEM CODE.
    """
    cols = list(df.columns)
    normalized = {c: normalize_text(c).lower() for c in cols}

    def compact(x):
        return normalize_text(x).lower().replace(" ", "").replace("_", "").replace("-", "")

    cand_norm = [normalize_text(c).lower() for c in candidates if normalize_text(c)]
    cand_compact = [compact(c) for c in candidates if normalize_text(c)]

    # 1) Exact normalized match
    for cand in cand_norm:
        for c, n in normalized.items():
            if n == cand:
                return c

    # 2) Exact compact match
    for cand in cand_compact:
        for c, n in normalized.items():
            if compact(n) == cand:
                return c

    if exact:
        return None

    # 3) Substring match, but prefer longer/more specific candidates first
    ordered = sorted(cand_norm, key=len, reverse=True)
    for cand in ordered:
        # avoid matching generic "code" against STORE CODE unless no item-specific match exists
        for c, n in normalized.items():
            if cand and cand in n:
                return c

    return None

def parse_branch_list(note_text):
    text = normalize_text(note_text).upper()
    if not text:
        return []
    return sorted(set(re.findall(r'P\d{4}', text)))

def parse_negative_number(value):
    txt = normalize_text(value).replace(",", "")
    if not txt:
        return 0.0
    if txt.startswith("(") and txt.endswith(")"):
        txt = "-" + txt[1:-1]
    try:
        return float(txt)
    except Exception:
        return 0.0


def standardize_item_code_column(df):
    """
    Guarantee an Item Code column if any likely code column exists.
    If no candidate exists, return df with an empty Item Code column instead of crashing.
    """
    if df is None:
        return df
    df = df.copy()
    if "Item Code" in df.columns:
        df["Item Code"] = df["Item Code"].apply(normalize_code)
        return df

    candidates = [
        "item code", "itemcode", "item_code", "itm_cd", "itm cd",
        "code", "item cd", "item no", "item number", "sku"
    ]
    col = find_col(df, candidates)
    if col:
        df["Item Code"] = df[col].apply(normalize_code)
    else:
        df["Item Code"] = ""
    return df
