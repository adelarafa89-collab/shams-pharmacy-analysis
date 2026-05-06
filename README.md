# Shams Pharmacy Analysis v3.2 - Final Fix

## What's fixed
- Removed Excel Tables that caused Excel repair warnings
- Added Module_Status sheet so you can see what loaded and what failed
- Keeps old Sales/Stock cleaning logic
- CUSTOMER NAME follows the last valid value above it
- Flexible column mapping for optional files

## Run locally
pip install -r requirements.txt
streamlit run app.py


## v3.3 Fix
- Fixed optional modules parsing to read real headers (header=0)
- This resolves Module_Status showing Rows=0 for uploaded optional files when the files actually contain headers in row 1.


## v3.4 Dashboard
- Added Dashboard sheet summarizing Core, Inventory, Availability, Target, CAWSA, Staff, Offers, Promoted, Wasfaty Active and Wasfaty Golden.
- Added support for the new direct stock format:
  ITEM CODE, DESCRIPTION, Qty, LzQty, Retail Price, RetailValue.
- LzQty is ignored in all calculations.


## v3.5
- Fixed KeyError: 'Item Code' when optional module parsing returns empty or unmapped data.
- Optional modules now fail gracefully and appear in Module_Status instead of crashing the full report.

## v3.6
- Suppressed noisy OLE2/xlrd warnings from old .xls files.
- Keeps v3.5 Item Code fix and v3.4 Dashboard.

## v3.7
- Hard fix for KeyError: 'Item Code' across Core and optional modules.
- Added universal standardize_item_code_column().
- Core errors now show clearer message if Sales/Stock parsing fails.

## v3.8
- Added support for new direct Sales format with headers in the first row:
  Wh_SubType, Store, Item Code, Item Name, Grp Name, Customer Name, SaleAmt, Tot Trans.
- If SaleQty is missing, Tot Trans is used as Sales Qty proxy.
- Keeps old two-row-header Sales parser as fallback.

## v3.9
- Fixed direct Sales parser: no ffill on Item Code / Item Name.
- Prevents subtotal/total rows from inheriting previous item code and creating fake huge sales.
- Customer/channel ffill remains enabled.

## v4.0 Reference Reports
Added reference-style reports matching 2026.xlsm:
- ABC_NUPCO_Qty
- ABC_NUPCO_Amount
- TopCustomers
- TopCategories
- ITEM_SUMMARY

Existing reports remain unchanged.

## v4.1 Sheet Name Fix
- Fixed Excel sheet name conflict between Item_Summary and ITEM_SUMMARY.
- Legacy reference item report is now named ITEM_SUMMARY_REF.
- Fixed Streamlit session_state crash when report generation fails.

## v4.2 NUPCO Channel Rows Fix
- Direct sales parser now keeps blank Item Code channel rows such as NUPCO rows by inheriting the previous item.
- True Total/Subtotal rows are removed before inheritance.
- Fixes missing NUPCO sales for items like NOVORAPID while avoiding fake huge totals.

## v4.3 Import Fix
- Fixed broken core.py import line that caused: ImportError cannot import name 'f'.
- Keeps v4.2 NUPCO channel-row fix.

## v4.4 Core Cleanup
- Removed corrupted stray variable line `anch_code` from core.py.
- Keeps v4.2/v4.3 fixes.

## v4.5 Stock Header Auto-Detect
- Stock parser now detects the header row automatically.
- Supports stock files with top report/title rows before the real header.
- Supports extra columns such as ITEM PARTNO and UOM.
- LzQty is ignored in all calculations.

## v4.6 dtype fix
- Fixed pandas dtype error in ITEM_SUMMARY_REF Value column:
  Invalid value '3.0' for dtype 'str'.
- Keeps v4.5 stock header auto-detect.

## v4.7 Closed File Fix
- Fixed: I/O operation on closed file.
- Uploaded Excel files are now converted to bytes before reading.
- Keeps v4.6 dtype fix and v4.5 stock header auto-detect.

## v4.8 Safe Upload Fix
- Converts every Streamlit UploadedFile into an immutable bytes copy before analysis.
- Stronger fix for: I/O operation on closed file.
- Especially useful for old .XLS files exported from ERP systems.

## v4.9 Tempfile XLS Fix
- Stronger fix for old .XLS files:
  reads XLS from a real temporary file path instead of BytesIO.
- Targets persistent: I/O operation on closed file.
- Keeps v4.8 safe upload layer.

## v5.0 Calamine Excel Engine
- Added python-calamine to requirements.
- Excel files are read with calamine first, then fallback to xlrd/openpyxl.
- Strongest fix so far for old ERP .XLS files causing:
  I/O operation on closed file.

## v5.1 Sales Header Auto-detect
- Sales parser now auto-detects the header row if there are top/title rows.
- If old parser fails, error message shows why instead of a vague Item Code KeyError.
- Keeps calamine reader from v5.0.

## v5.2 Sales Multiheader Fix
- Sales parser now handles ERP multi-header reports:
  Sale / Srtn / Total row + SaleQty / SaleAmt row.
- Uses Total_SaleQty and Total_SaleAmt when available.
- Keeps NUPCO blank item-code inheritance while removing true totals/subtotals.

## v5.3 find_col priority fix
- Fixed column matching priority.
- Prevents STORE CODE from being selected as Item Code.
- Item Code matching no longer uses the generic candidate 'code' before item-specific labels.
- Keeps v5.2 multi-header Sales parser.

## v5.4 Sales Matrix Parser
- Replaced Sales multi-header parsing with a raw matrix parser.
- Detects column indexes directly from the header row.
- Handles duplicate SaleQty/SaleAmt headers under Sale/Srtn/Total.
- Prefers the Total block; falls back safely.
- Keeps NUPCO channel row inheritance.

## v5.5 Sales Positional Fallback
- Adds a direct positional parser for known ERP sales layouts:
  16-column flat report and 19-column multiheader report.
- Keeps NUPCO/online channel row inheritance.
- Adds diagnostic first rows if sales header cannot be recognized.

## v5.6 Mojibake XLS Text Fix
- Fixed old XLS corrupted text containing replacement/null characters, e.g.:
  I�t�e�m� C�o�d�e� -> Item Code
- This allows Sales header detection to work on badly encoded ERP XLS exports.
