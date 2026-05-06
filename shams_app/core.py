
import pandas as pd
from .helpers import normalize_text, normalize_code, to_num, make_display_name, classify_abc, read_excel_any, find_col, standardize_item_code_column




def clean_sales(uploaded_file):
    """
    v5.5 Sales parser:
    - Tries raw positional ERP parsing first.
    - Supports 16-column flat ERP sales files:
      Wh_SubType, Store, Item Code, Item Name, Grp Name, Customer Name, SaleAmt, ..., Tot Trans
    - Supports 19-column multi-header ERP sales files:
      WHSubType, STORE CODE, STORE/BRANCH, Item Code, Item Name, Grp Name, CUSTOMER NAME,
      SaleQty/SaleAmt under Sale/Srtn/Total. Uses Total columns if present.
    - Keeps NUPCO/online rows with blank Item Code by inheriting previous item.
    - Removes true Total/Subtotal rows.
    """

    def _compact(x):
        return normalize_text(x).lower().replace(" ", "").replace("_", "").replace("-", "")

    def _is_total_text(*vals):
        txt = " ".join(normalize_text(v).lower() for v in vals)
        if not txt.strip():
            return False
        return (
            txt.strip() in {"total", "subtotal", "grand total"}
            or "subtotal" in txt
            or "grand total" in txt
            or "page total" in txt
        )

    def _num(v):
        return pd.to_numeric(pd.Series([v]), errors="coerce").fillna(0).iloc[0]

    def _parse_rows_by_positions(raw, header_idx, layout):
        if layout == "flat16":
            idx = {
                "subtype": 0,
                "store": 1,
                "item": 2,
                "name": 3,
                "grp": 4,
                "customer": 5,
                "amount": 6,
                "qty": 12,   # Tot Trans used as quantity proxy
            }
        elif layout == "multi19":
            idx = {
                "subtype": 0,
                "store": 1,
                "branch": 2,
                "item": 3,
                "name": 4,
                "grp": 5,
                "customer": 6,
                "qty": 15,      # Total SaleQty
                "amount": 16,   # Total SaleAmt
            }
        else:
            return None

        rows = []
        last_code = ""
        last_name = ""
        last_grp = ""
        branch_code = ""

        data = raw.iloc[header_idx + 1:].copy()

        for _, row in data.iterrows():
            subtype = row.iloc[idx["subtype"]] if idx["subtype"] < len(row) else ""
            store = row.iloc[idx["store"]] if idx["store"] < len(row) else ""
            item = row.iloc[idx["item"]] if idx["item"] < len(row) else ""
            name = row.iloc[idx["name"]] if idx["name"] < len(row) else ""
            grp = row.iloc[idx["grp"]] if idx["grp"] < len(row) else ""
            customer = row.iloc[idx["customer"]] if idx["customer"] < len(row) else ""
            qty_val = row.iloc[idx["qty"]] if idx["qty"] < len(row) else 0
            amt_val = row.iloc[idx["amount"]] if idx["amount"] < len(row) else 0

            code_raw = normalize_code(item)
            name_raw = normalize_text(name)
            grp_raw = normalize_text(grp)
            customer_raw = normalize_text(customer)

            if _is_total_text(subtype, store, code_raw, name_raw, customer_raw):
                continue

            if normalize_text(store) and not branch_code:
                branch_code = normalize_text(store)

            has_code = code_raw != ""
            has_customer = customer_raw != ""

            if has_code:
                last_code = code_raw
                if name_raw:
                    last_name = name_raw
                if grp_raw:
                    last_grp = grp_raw
            else:
                # Channel rows such as NUPCO / HUNGER / TOYOU inherit previous item.
                if has_customer and last_code:
                    code_raw = last_code
                    name_raw = last_name
                    grp_raw = last_grp
                else:
                    continue

            customer_out = customer_raw if customer_raw else "CASH IN BOX"
            qty = float(_num(qty_val))
            amt = float(_num(amt_val))

            if code_raw and amt != 0:
                rows.append({
                    "Item Code": normalize_code(code_raw),
                    "Item Name": make_display_name(name_raw or last_name),
                    "Grp Name": normalize_text(grp_raw or last_grp),
                    "CUSTOMER NAME": customer_out,
                    "SaleQty": qty,
                    "SaleAmt": amt,
                })

        if not rows:
            return None

        cleaned = pd.DataFrame(rows)
        cleaned = cleaned[~cleaned["Item Code"].astype(str).str.contains("total|subtotal|page|grand", case=False, na=False)].copy()
        if cleaned.empty:
            return None
        return cleaned[["Item Code", "Item Name", "Grp Name", "CUSTOMER NAME", "SaleQty", "SaleAmt"]], branch_code

    def _detect_and_parse_positional(raw):
        # Detect flat16 header row.
        for i in range(min(len(raw), 120)):
            vals = [_compact(v) for v in raw.iloc[i].tolist()]
            joined = "|".join(vals)

            # Flat 16 ERP sales.
            if (
                len(vals) >= 13
                and ("whsubtype" in joined or "wh_subtype" in joined)
                and "itemcode" in joined
                and ("customername" in joined or "customer" in joined)
                and "saleamt" in joined
                and ("tottrans" in joined or "totaltrans" in joined)
            ):
                return _parse_rows_by_positions(raw, i, "flat16")

            # Multiheader 19 ERP sales lower header row.
            if (
                len(vals) >= 17
                and ("whsubtype" in joined or "wh_subtype" in joined)
                and ("storecode" in joined or "store" in joined)
                and "itemcode" in joined
                and "customername" in joined
                and "saleqty" in joined
                and "saleamt" in joined
            ):
                return _parse_rows_by_positions(raw, i, "multi19")

        return None

    def _parse_generic_flat(raw):
        # Last fallback: use first row that contains Item Code and SaleAmt, then column-name parsing.
        for i in range(min(len(raw), 120)):
            vals = [_compact(v) for v in raw.iloc[i].tolist()]
            joined = "|".join(vals)
            if "itemcode" in joined and "saleamt" in joined:
                df = raw.iloc[i + 1:].copy()
                df.columns = [normalize_text(c) for c in raw.iloc[i].tolist()]
                df = df.loc[:, [c != "" for c in df.columns]].copy()

                item_col = find_col(df, ["item code", "itemcode", "item_code", "itm_cd", "item cd", "sku"])
                name_col = find_col(df, ["item name", "description", "name"])
                grp_col = find_col(df, ["grp name", "group", "category"])
                customer_col = find_col(df, ["customer name", "customer"])
                store_col = find_col(df, ["store"], exact=True) or find_col(df, ["store code", "branch"])
                saleamt_col = find_col(df, ["saleamt", "sale amt", "sales amount", "net sales"])
                qty_col = find_col(df, ["tot trans", "total trans", "transactions"]) or find_col(df, ["saleqty", "sale qty", "qty"])

                if not (item_col and name_col and saleamt_col):
                    continue

                rows = []
                last_code = ""
                last_name = ""
                last_grp = ""
                branch_code = ""

                for _, row in df.iterrows():
                    code_raw = normalize_code(row[item_col])
                    name_raw = normalize_text(row[name_col])
                    grp_raw = normalize_text(row[grp_col]) if grp_col else ""
                    customer_raw = normalize_text(row[customer_col]) if customer_col else ""
                    store_raw = normalize_text(row[store_col]) if store_col else ""

                    if _is_total_text(store_raw, code_raw, name_raw, customer_raw):
                        continue
                    if store_raw and not branch_code:
                        branch_code = store_raw

                    if code_raw:
                        last_code = code_raw
                        if name_raw:
                            last_name = name_raw
                        if grp_raw:
                            last_grp = grp_raw
                    elif customer_raw and last_code:
                        code_raw = last_code
                        name_raw = last_name
                        grp_raw = last_grp
                    else:
                        continue

                    qty = float(_num(row[qty_col])) if qty_col else 0
                    amt = float(_num(row[saleamt_col]))
                    if code_raw and amt != 0:
                        rows.append({
                            "Item Code": code_raw,
                            "Item Name": make_display_name(name_raw or last_name),
                            "Grp Name": normalize_text(grp_raw or last_grp),
                            "CUSTOMER NAME": customer_raw if customer_raw else "CASH IN BOX",
                            "SaleQty": qty,
                            "SaleAmt": amt,
                        })

                if rows:
                    cleaned = pd.DataFrame(rows)
                    return cleaned[["Item Code", "Item Name", "Grp Name", "CUSTOMER NAME", "SaleQty", "SaleAmt"]], branch_code
        return None

    errors = []
    try:
        raw = read_excel_any(uploaded_file, header=None)
        result = _detect_and_parse_positional(raw)
        if result is not None:
            return result

        result = _parse_generic_flat(raw)
        if result is not None:
            return result

        # Build a small diagnostic to help later if still fails.
        sample = []
        for i in range(min(8, len(raw))):
            sample.append(" | ".join(normalize_text(v) for v in raw.iloc[i].tolist()[:10]))
        raise ValueError("Header not recognized. First rows: " + " || ".join(sample))
    except Exception as e:
        errors.append(str(e))

    raise ValueError("Could not parse Sales file. Positional and generic parsers failed. Details: " + " | ".join(errors))

def clean_stock(uploaded_file):
    """
    Supports multiple stock formats.

    New format example:
    Rows above header may exist, then:
    ITEM CODE | ITEM PARTNO | DESCRIPTION | UOM | Qty | LzQty | Retail Price | RetailValue

    Rules:
    - Detect header row automatically.
    - Ignore rows above header.
    - Ignore ITEM PARTNO, UOM, LzQty, and any extra columns.
    - Use Qty only for stock calculations.
    - LzQty is NOT used in any calculation.
    """
    from .helpers import find_col

    # 1) Header auto-detect format
    try:
        raw = read_excel_any(uploaded_file, header=None)

        header_idx = None
        for i in range(min(len(raw), 50)):
            row_vals = [normalize_text(v).lower() for v in raw.iloc[i].tolist()]
            joined = " | ".join(row_vals)
            has_item_code = any(v in {"item code", "itemcode", "item_code"} for v in row_vals) or "item code" in joined
            has_description = "description" in joined or "item name" in joined
            has_qty = any(v == "qty" for v in row_vals) or " qty " in f" {joined} "
            if has_item_code and has_description and has_qty:
                header_idx = i
                break

        if header_idx is not None:
            direct = raw.iloc[header_idx + 1:].copy()
            headers = [normalize_text(c) for c in raw.iloc[header_idx].tolist()]
            direct.columns = headers
            direct = direct.loc[:, [c != "" for c in direct.columns]].copy()

            item_col = find_col(direct, ["item code", "itemcode", "item_code", "itm_cd", "item cd", "sku"])
            desc_col = find_col(direct, ["description", "item name", "name"])
            qty_col = find_col(direct, ["qty"], exact=True)
            retail_price_col = find_col(direct, ["retail price", "retailprice"])
            retail_value_col = find_col(direct, ["retailvalue", "retail value"])

            if item_col and desc_col and qty_col:
                clean = pd.DataFrame()
                clean["ITEM CODE"] = direct[item_col].apply(normalize_code)
                clean["DESCRIPTION"] = direct[desc_col].apply(make_display_name)
                clean["Qty"] = to_num(direct[qty_col])

                # IMPORTANT: LzQty intentionally ignored.
                clean["Retail Price"] = to_num(direct[retail_price_col]) if retail_price_col else 0
                clean["RetailValue"] = to_num(direct[retail_value_col]) if retail_value_col else (clean["Qty"] * clean["Retail Price"])

                clean = clean[
                    (clean["ITEM CODE"] != "")
                    & (~clean["ITEM CODE"].astype(str).str.contains("item code|page|total|subtotal|grand", case=False, na=False))
                ].copy()

                # Drop rows that are not real item rows.
                clean = clean[~clean["DESCRIPTION"].astype(str).str.contains("total|subtotal|grand total", case=False, na=False)].copy()

                clean["Retail Price"] = clean.apply(
                    lambda r: round(r["RetailValue"] / r["Qty"], 4)
                    if ((not r["Retail Price"]) and r["Qty"] not in [0, None]) else r["Retail Price"],
                    axis=1,
                )

                return clean[["ITEM CODE", "DESCRIPTION", "Qty", "Retail Price", "RetailValue"]].copy()
    except Exception:
        pass

    # 2) Direct header at first row fallback
    try:
        direct = read_excel_any(uploaded_file, header=0)
        direct.columns = [normalize_text(c) for c in direct.columns]

        item_col = find_col(direct, ["item code", "itemcode", "item_code", "itm_cd", "item cd", "sku"])
        desc_col = find_col(direct, ["description", "item name", "name"])
        qty_col = find_col(direct, ["qty"], exact=True)
        retail_price_col = find_col(direct, ["retail price", "retailprice"])
        retail_value_col = find_col(direct, ["retailvalue", "retail value"])

        if item_col and desc_col and qty_col:
            clean = pd.DataFrame()
            clean["ITEM CODE"] = direct[item_col].apply(normalize_code)
            clean["DESCRIPTION"] = direct[desc_col].apply(make_display_name)
            clean["Qty"] = to_num(direct[qty_col])

            # IMPORTANT: LzQty intentionally ignored.
            clean["Retail Price"] = to_num(direct[retail_price_col]) if retail_price_col else 0
            clean["RetailValue"] = to_num(direct[retail_value_col]) if retail_value_col else (clean["Qty"] * clean["Retail Price"])

            clean = clean[
                (clean["ITEM CODE"] != "")
                & (~clean["ITEM CODE"].astype(str).str.contains("item code|page|total|subtotal|grand", case=False, na=False))
            ].copy()

            clean["Retail Price"] = clean.apply(
                lambda r: round(r["RetailValue"] / r["Qty"], 4)
                if ((not r["Retail Price"]) and r["Qty"] not in [0, None]) else r["Retail Price"],
                axis=1,
            )

            return clean[["ITEM CODE", "DESCRIPTION", "Qty", "Retail Price", "RetailValue"]].copy()
    except Exception:
        pass

    # 3) Old stock format fallback
    raw = read_excel_any(uploaded_file, header=None)
    df = raw.iloc[3:].copy()
    df.columns = ["ITEM CODE", "DESCRIPTION", "Unit", "Qty", "_x1", "Retail Price", "_x2", "_x3", "RetailValue"]

    rows = []
    for _, row in df.iterrows():
        code = normalize_code(row["ITEM CODE"])
        desc = normalize_text(row["DESCRIPTION"])
        qty = row["Qty"]
        rval = row["RetailValue"]
        if code and "/" not in code and ":" not in code:
            rows.append({"ITEM CODE": code, "DESCRIPTION": desc, "Qty": qty, "RetailValue": rval})
        elif rows and desc:
            rows[-1]["DESCRIPTION"] = normalize_text(f"{rows[-1]['DESCRIPTION']} {desc}")

    clean = pd.DataFrame(rows)
    if clean.empty:
        return pd.DataFrame(columns=["ITEM CODE", "DESCRIPTION", "Qty", "Retail Price", "RetailValue"])

    clean = clean[clean["ITEM CODE"] != ""].copy()
    clean["Qty"] = to_num(clean["Qty"])
    clean["RetailValue"] = to_num(clean["RetailValue"])
    bad_mask = (
        clean["ITEM CODE"].str.contains("item code|page|total|subtotal|grand", case=False, na=False) |
        clean["ITEM CODE"].str.contains(r"^\d{1,2}/\d{1,2}/\d{4}", regex=True, na=False)
    )
    clean = clean[~bad_mask].copy()
    clean["Retail Price"] = clean.apply(lambda r: round(r["RetailValue"] / r["Qty"], 4) if r["Qty"] not in [0, None] else 0, axis=1)
    clean["DESCRIPTION"] = clean["DESCRIPTION"].apply(make_display_name)
    return clean[["ITEM CODE", "DESCRIPTION", "Qty", "Retail Price", "RetailValue"]].copy()

def build_core(stock_file, sales_file, months_count):
    sales_df, branch_code = clean_sales(sales_file)
    stock_df = clean_stock(stock_file)

    sales_df = standardize_item_code_column(sales_df)
    if "Item Name" not in sales_df.columns:
        sales_df["Item Name"] = ""
    if "Grp Name" not in sales_df.columns:
        sales_df["Grp Name"] = ""
    if "SaleQty" not in sales_df.columns:
        sales_df["SaleQty"] = 0
    if "SaleAmt" not in sales_df.columns:
        sales_df["SaleAmt"] = 0

    stock_df = stock_df.copy()
    if "ITEM CODE" in stock_df.columns:
        stock_df["ITEM CODE"] = stock_df["ITEM CODE"].apply(normalize_code)
    elif "Item Code" in stock_df.columns:
        stock_df["ITEM CODE"] = stock_df["Item Code"].apply(normalize_code)
    else:
        stock_df["ITEM CODE"] = ""

    sales_name_map = sales_df.groupby("Item Code", as_index=False)["Item Name"].first().set_index("Item Code")["Item Name"].to_dict()
    if not stock_df.empty:
        stock_df["DESCRIPTION"] = stock_df.apply(lambda r: sales_name_map.get(normalize_code(r["ITEM CODE"]), r["DESCRIPTION"]), axis=1)

    item_sales = sales_df.groupby(["Item Code", "Item Name", "Grp Name"], as_index=False).agg({"SaleQty": "sum", "SaleAmt": "sum"})
    item_sales = item_sales[item_sales["Item Code"] != ""].copy()
    summary = item_sales.merge(
        stock_df[["ITEM CODE", "Qty", "RetailValue"]] if not stock_df.empty else pd.DataFrame(columns=["ITEM CODE", "Qty", "RetailValue"]),
        how="left", left_on="Item Code", right_on="ITEM CODE"
    )
    summary["Qty"] = to_num(summary["Qty"])
    summary["RetailValue"] = to_num(summary["RetailValue"])
    if "ITEM CODE" in summary.columns:
        summary = summary.drop(columns=["ITEM CODE"])

    summary["Avg Monthly Qty"] = summary["SaleQty"] / float(months_count)
    summary["Avg 2 Months (Qty)"] = summary["Avg Monthly Qty"] * 2
    summary["Need"] = (summary["Avg 2 Months (Qty)"] - summary["Qty"]).clip(lower=0)
    summary["Status"] = summary["Need"].apply(lambda x: "NEED ORDER" if x > 0 else "ENOUGH")

    abc_qty = summary[["Item Code", "Item Name", "Grp Name", "SaleQty"]].copy().sort_values(["SaleQty", "Item Code"], ascending=[False, True]).reset_index(drop=True)
    total_qty = abc_qty["SaleQty"].sum()
    abc_qty["Share%"] = abc_qty["SaleQty"] / total_qty if total_qty else 0
    abc_qty["Cum%"] = abc_qty["Share%"].cumsum() if total_qty else 0
    abc_qty["Class"] = abc_qty["Cum%"].apply(classify_abc)
    abc_qty["NUPCO?"] = "No"
    abc_qty = abc_qty[["Item Code", "Item Name", "SaleQty", "Grp Name", "NUPCO?", "Share%", "Cum%", "Class"]]
    abc_qty.columns = ["Item Code", "Item Name", "Total Qty", "Group", "NUPCO?", "Share%", "Cum%", "Class"]

    abc_amt = summary[["Item Code", "Item Name", "Grp Name", "SaleAmt"]].copy().sort_values(["SaleAmt", "Item Code"], ascending=[False, True]).reset_index(drop=True)
    total_amt = abc_amt["SaleAmt"].sum()
    abc_amt["Share%"] = abc_amt["SaleAmt"] / total_amt if total_amt else 0
    abc_amt["Cum%"] = abc_amt["Share%"].cumsum() if total_amt else 0
    abc_amt["Class"] = abc_amt["Cum%"].apply(classify_abc)
    abc_amt["NUPCO?"] = "No"
    abc_amt = abc_amt[["Item Code", "Item Name", "SaleAmt", "Grp Name", "NUPCO?", "Share%", "Cum%", "Class"]]
    abc_amt.columns = ["Item Code", "Item Name", "Total Amount", "Group", "NUPCO?", "Share%", "Cum%", "Class"]

    top_customers = sales_df.groupby("CUSTOMER NAME", as_index=False)["SaleAmt"].sum().sort_values("SaleAmt", ascending=False).reset_index(drop=True)
    total_sales_amount = float(top_customers["SaleAmt"].sum())
    top_customers["Share%"] = top_customers["SaleAmt"] / total_sales_amount if total_sales_amount else 0
    top_customers.columns = ["Customer Name", "Total Amount", "Share%"]
    top_customers = pd.concat([top_customers, pd.DataFrame([{"Customer Name": "TOTAL", "Total Amount": total_sales_amount, "Share%": 1.0 if total_sales_amount else 0}])], ignore_index=True)

    top_categories = summary.groupby("Grp Name", as_index=False).agg({"Avg 2 Months (Qty)": "sum", "SaleAmt": "sum"}).sort_values("SaleAmt", ascending=False).reset_index(drop=True)
    cat_total = float(top_categories["SaleAmt"].sum())
    top_categories["Share%"] = top_categories["SaleAmt"] / cat_total if cat_total else 0
    top_categories["Cum%"] = top_categories["Share%"].cumsum() if cat_total else 0
    top_categories["Class"] = top_categories["Cum%"].apply(classify_abc)
    top_categories.columns = ["Category (GrpName)", "Total Qty", "Total Amount", "Share%", "Cum%", "Class"]

    qty_class_map = abc_qty.set_index("Item Code")["Class"].to_dict()
    item_summary = summary.copy()
    item_summary["ABC Class (Qty 70%)"] = item_summary["Item Code"].map(qty_class_map).fillna("C")
    item_summary = item_summary[[
        "Item Code", "Item Name", "Grp Name", "SaleQty", "SaleAmt", "Avg Monthly Qty", "Avg 2 Months (Qty)",
        "Qty", "RetailValue", "Need", "ABC Class (Qty 70%)", "Status"
    ]].copy()
    item_summary.columns = [
        "Item Code", "Item Name", "Grp Name", "Total Sales Qty (Period)", "Total Sales Amount (Period)",
        "Avg Monthly Qty", "Avg 2 Months (Qty)", "Stock Qty", "Retail Value", "Need",
        "ABC Class (Qty 70%)", "Status"
    ]
    item_summary = item_summary.sort_values("Item Code").reset_index(drop=True)

    return {
        "branch": branch_code, "sales": sales_df, "stock": stock_df, "item_summary": item_summary,
        "abc_qty": abc_qty, "abc_amt": abc_amt, "top_customers": top_customers,
        "top_categories": top_categories, "total_sales": total_sales_amount,
        "total_stock": float(stock_df["RetailValue"].sum()) if not stock_df.empty else 0.0,
    }
