
import pandas as pd
from .helpers import normalize_text, normalize_code, to_num, read_excel_any, find_col, parse_branch_list, parse_negative_number, standardize_item_code_column

def ensure_item_code_df(df, cols=None):
    cols = cols or ["Item Code"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    if "Item Code" not in df.columns:
        df = df.copy()
        df["Item Code"] = ""
    df["Item Code"] = df["Item Code"].apply(normalize_code)
    return df


def clean_target(uploaded_file):
    xl = read_excel_any(uploaded_file, header=0, sheet_name=None)
    daily_rows, monthly_rows = [], []
    for sheet_name, df in xl.items():
        if df is None or df.empty:
            continue
        work = df.copy()
        work.columns = [normalize_text(c) for c in work.columns]
        date_col = find_col(work, ["date"], exact=True)
        sales_col = find_col(work, ["daily sales without vat"], exact=True)
        cust_col = find_col(work, ["customer count"], exact=True)
        if date_col and sales_col and cust_col:
            daily = work.copy()
            numeric_map = {
                "Daily Sales Without VAT": sales_col,
                "Customer Count": cust_col,
                "Total Sales With VAT": find_col(work, ["total sales with vat"]),
                "Home Delivery Sales": find_col(work, ["home delivery sales"]),
                "Wasfaty Sales": find_col(work, ["wasfaty sales"]),
                "Vat": find_col(work, ["vat"], exact=True),
                "Private Label Sales": find_col(work, ["private label"]),
                "Cash Sales": find_col(work, ["cash"]),
            }
            out = pd.DataFrame()
            out["Date"] = pd.to_datetime(daily[date_col], errors="coerce")
            for name, col in numeric_map.items():
                out[name] = to_num(daily[col]) if col else 0
            out["Month"] = sheet_name
            daily_rows.append(out)
            monthly_rows.append({
                "Month": sheet_name,
                "Sales Days": int(out["Date"].notna().sum()),
                "Total Sales Without VAT": float(out["Daily Sales Without VAT"].sum()),
                "Total Sales With VAT": float(out["Total Sales With VAT"].sum()),
                "Customer Count": float(out["Customer Count"].sum()),
                "Home Delivery Sales": float(out["Home Delivery Sales"].sum()),
                "Wasfaty Sales": float(out["Wasfaty Sales"].sum()),
                "Private Label Sales": float(out["Private Label Sales"].sum()),
                "Cash Sales": float(out["Cash Sales"].sum()),
            })
    daily_df = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
    monthly_df = pd.DataFrame(monthly_rows)
    if not monthly_df.empty:
        max_sales = monthly_df["Total Sales Without VAT"].max()
        monthly_df["Achievement %"] = monthly_df["Total Sales Without VAT"] / max_sales if max_sales else 0
        monthly_df["Avg Basket"] = monthly_df.apply(lambda r: r["Total Sales Without VAT"] / r["Customer Count"] if r["Customer Count"] else 0, axis=1)
        monthly_df["Wasfaty %"] = monthly_df.apply(lambda r: r["Wasfaty Sales"] / r["Total Sales Without VAT"] if r["Total Sales Without VAT"] else 0, axis=1)
        monthly_df["Home Delivery %"] = monthly_df.apply(lambda r: r["Home Delivery Sales"] / r["Total Sales Without VAT"] if r["Total Sales Without VAT"] else 0, axis=1)
        monthly_df["Private Label %"] = monthly_df.apply(lambda r: r["Private Label Sales"] / r["Total Sales Without VAT"] if r["Total Sales Without VAT"] else 0, axis=1)
    return daily_df, monthly_df

def clean_cawsa(uploaded_file):
    df = read_excel_any(uploaded_file, header=0)
    df.columns = [normalize_text(c) for c in df.columns]
    store_col = find_col(df, ["store"], exact=True)
    region_col = find_col(df, ["region"], exact=True)
    grp_col = find_col(df, ["grp name"], exact=True)
    branch_share_col = find_col(df, ["branch_share", "branch share"])
    region_share_col = find_col(df, ["region_share", "region share"])
    gap_col = find_col(df, ["gap"], exact=True)
    status_col = find_col(df, ["status"], exact=True)
    out = pd.DataFrame()
    out["Store"] = df[store_col].apply(normalize_text) if store_col else ""
    out["Region"] = df[region_col].apply(normalize_text) if region_col else ""
    out["Grp Name"] = df[grp_col].apply(normalize_text) if grp_col else ""
    out["Branch_Share"] = to_num(df[branch_share_col]) if branch_share_col else 0
    out["Region_Share"] = to_num(df[region_share_col]) if region_share_col else 0
    out["Gap"] = to_num(df[gap_col]) if gap_col else 0
    out["Status"] = df[status_col].apply(normalize_text) if status_col else ""
    return out

def clean_staff(uploaded_file):
    df = read_excel_any(uploaded_file, header=0)
    df.columns = [normalize_text(c) for c in df.columns]
    out = pd.DataFrame()
    out["BrCd"] = df[find_col(df, ["brcd", "branch code", "branch"], exact=False)].apply(normalize_text) if find_col(df, ["brcd", "branch code", "branch"], exact=False) else ""
    out["usr_id"] = df[find_col(df, ["usr_id", "user id"], exact=False)] if find_col(df, ["usr_id", "user id"], exact=False) else ""
    out["usr_name"] = df[find_col(df, ["usr_name", "user name", "name"], exact=False)].apply(normalize_text) if find_col(df, ["usr_name", "user name", "name"], exact=False) else ""
    sreturn_col = find_col(df, ["sreturn"])
    out["SReturn"] = df[sreturn_col].apply(parse_negative_number) if sreturn_col else 0
    for src, dst in [("bs","BS"), ("pl_mix","PL_Mix"), ("promoted sales mix","Promoted Sales Mix"), ("nemix","NEMix")]:
        col = find_col(df, [src], exact=False)
        out[dst] = to_num(df[col]) if col else 0
    return out

def build_staff_outputs(staff_df, branch_code):
    if staff_df is None or staff_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    branch_staff = staff_df[staff_df["BrCd"].astype(str).str.upper() == str(branch_code).upper()].copy()
    if branch_staff.empty:
        return pd.DataFrame(), pd.DataFrame()
    perf = branch_staff.sort_values(["BS","Promoted Sales Mix"], ascending=[False, False]).reset_index(drop=True)
    avg_bs = float(perf["BS"].mean()) if "BS" in perf.columns else 0
    avg_promoted = float(perf["Promoted Sales Mix"].mean()) if "Promoted Sales Mix" in perf.columns else 0
    impact = pd.DataFrame([
        {"Metric":"Avg Staff Score", "Value":avg_bs},
        {"Metric":"Avg Promoted Sales Mix", "Value":avg_promoted},
        {"Metric":"Staff Count", "Value":len(perf)},
        {"Metric":"Low Staff Count (<60 BS)", "Value":int((perf["BS"] < 60).sum()) if "BS" in perf.columns else 0},
    ])
    return perf, impact

def clean_offers(uploaded_file):
    df = read_excel_any(uploaded_file, header=0)
    df.columns = [normalize_text(c) for c in df.columns]
    out = pd.DataFrame()
    item_col = find_col(df, ["item code", "itemcode", "item_code", "itm_cd", "item cd", "sku"])
    name_col = find_col(df, ["item name", "description", "name"])
    offer_col = find_col(df, ["offer"])
    rp_col = find_col(df, ["rp"], exact=True)
    applied_col = find_col(df, ["applied offer"])
    drp_col = find_col(df, ["drp"], exact=True)
    cat_col = find_col(df, ["cat"], exact=True)
    from_col = find_col(df, ["from"], exact=True)
    to_col = find_col(df, ["to"], exact=True)
    note_col = find_col(df, ["note"], exact=True)

    out["Item Code"] = df[item_col].apply(normalize_code) if item_col else ""
    out["Item Name"] = df[name_col].apply(normalize_text) if name_col else ""
    out["Offer"] = df[offer_col].apply(normalize_text) if offer_col else ""
    out["RP"] = to_num(df[rp_col]) if rp_col else 0
    out["Applied Offer"] = df[applied_col].apply(normalize_text) if applied_col else ""
    out["DRP"] = to_num(df[drp_col]) if drp_col else 0
    out["CAT"] = df[cat_col].apply(normalize_text) if cat_col else ""
    out["FROM"] = df[from_col] if from_col else ""
    out["TO"] = df[to_col] if to_col else ""
    out["NOTE"] = df[note_col].apply(normalize_text) if note_col else ""
    out["Branch_List"] = out["NOTE"].apply(parse_branch_list)
    out = standardize_item_code_column(out)
    out = out[out["Item Code"] != ""].copy()
    return out

def build_offers_performance(offers_df, item_summary, branch_code):
    offers_df = standardize_item_code_column(offers_df) if offers_df is not None else offers_df
    item_summary = standardize_item_code_column(item_summary) if item_summary is not None else item_summary
    if offers_df is None or offers_df.empty or "Item Code" not in offers_df.columns:
        return pd.DataFrame()
    if item_summary is None or item_summary.empty or "Item Code" not in item_summary.columns:
        return pd.DataFrame()
    branch = str(branch_code).upper()
    offers = offers_df.copy()
    if "Branch_List" not in offers.columns:
        offers["Branch_List"] = [[] for _ in range(len(offers))]
    offers = offers[offers["Branch_List"].apply(lambda lst: (not lst) or (branch in [str(x).upper() for x in lst]))].copy()
    if offers.empty:
        return pd.DataFrame()
    out = offers.merge(item_summary[["Item Code","Item Name","Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)"]], on="Item Code", how="left", suffixes=("","_core"))
    out["Stock Qty"] = to_num(out["Stock Qty"]); out["Total Sales Qty (Period)"] = to_num(out["Total Sales Qty (Period)"]); out["Total Sales Amount (Period)"] = to_num(out["Total Sales Amount (Period)"])
    out["Offer Status"] = out.apply(lambda r: "No Stock" if r["Stock Qty"] == 0 else ("Weak Sales" if r["Total Sales Qty (Period)"] == 0 else "Running"), axis=1)
    return out[["Item Code","Item Name","Offer","Applied Offer","DRP","CAT","Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)","Offer Status"]].sort_values(["Offer Status","Total Sales Qty (Period)"], ascending=[True, False]).reset_index(drop=True)

def clean_promoted(uploaded_file):
    xl = read_excel_any(uploaded_file, header=0, sheet_name=None)
    rows = []
    deleted = set()
    for sheet_name, df in xl.items():
        if df is None or df.empty:
            continue
        work = df.copy()
        work.columns = [normalize_text(c) for c in work.columns]
        if normalize_text(sheet_name).upper() == "DELETED":
            code_col = find_col(work, ["itm_cd", "item code", "itemcode", "item_code", "item cd", "sku"])
            if code_col:
                deleted.update(work[code_col].apply(normalize_code).tolist())
            continue
        code_col = find_col(work, ["itm_cd", "item code", "itemcode", "item_code", "item cd", "sku"])
        name_col = find_col(work, ["itm_name", "item name", "name"])
        comm_col = find_col(work, ["psh_commission", "new comm", "commission"])
        if code_col and name_col:
            tmp = pd.DataFrame({
                "Item Code": work[code_col].apply(normalize_code),
                "Item Name": work[name_col].apply(normalize_text),
                "Commission": to_num(work[comm_col]) if comm_col else 0,
                "Source Sheet": sheet_name,
            })
            rows.append(tmp)
    all_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["Item Code","Item Name","Commission","Source Sheet"])
    all_df = standardize_item_code_column(all_df)
    all_df = all_df[(all_df["Item Code"] != "") & (~all_df["Item Code"].isin(deleted))].copy()
    all_df = all_df.sort_values(["Commission","Item Code"], ascending=[False, True]).drop_duplicates(subset=["Item Code"], keep="first").reset_index(drop=True)
    return all_df

def build_promoted_performance(promoted_df, item_summary):
    promoted_df = standardize_item_code_column(promoted_df) if promoted_df is not None else promoted_df
    item_summary = standardize_item_code_column(item_summary) if item_summary is not None else item_summary
    if promoted_df is None or promoted_df.empty or "Item Code" not in promoted_df.columns:
        return pd.DataFrame()
    if item_summary is None or item_summary.empty or "Item Code" not in item_summary.columns:
        return pd.DataFrame()
    out = promoted_df.merge(item_summary[["Item Code","Item Name","Grp Name","Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)"]], on="Item Code", how="left", suffixes=("","_core"))
    out["Stock Qty"] = to_num(out["Stock Qty"]); out["Total Sales Qty (Period)"] = to_num(out["Total Sales Qty (Period)"]); out["Total Sales Amount (Period)"] = to_num(out["Total Sales Amount (Period)"])
    out["Promoted Status"] = out.apply(lambda r: "No Stock" if r["Stock Qty"] == 0 else ("Weak Sales" if r["Total Sales Qty (Period)"] == 0 else "Running"), axis=1)
    return out[["Item Code","Item Name","Commission","Source Sheet","Grp Name","Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)","Promoted Status"]].sort_values(["Promoted Status","Commission"], ascending=[True, False]).reset_index(drop=True)

def clean_wasfaty_list(uploaded_file, kind):
    df = read_excel_any(uploaded_file, header=0)
    df.columns = [normalize_text(c) for c in df.columns]
    item_col = find_col(df, ["item code", "itemcode", "item_code", "itm_cd", "item cd", "sku"])
    name_col = find_col(df, ["item name", "name"])
    cat_col = find_col(df, ["cat"], exact=True)
    sc_col = find_col(df, ["sc"], exact=True)
    price_col = find_col(df, ["nupco price", "price"])
    out = pd.DataFrame()
    out["Item Code"] = df[item_col].apply(normalize_code) if item_col else ""
    out["Item Name"] = df[name_col].apply(normalize_text) if name_col else ""
    out["CAT"] = df[cat_col].apply(normalize_text) if cat_col else ""
    out["SC"] = df[sc_col].apply(normalize_text) if sc_col else ""
    out["NUPCO Price"] = to_num(df[price_col]) if price_col else 0
    out["List Type"] = kind
    out = standardize_item_code_column(out)
    out = out[out["Item Code"] != ""].copy()
    return out

def build_wasfaty_control(list_df, item_summary, status_name):
    list_df = standardize_item_code_column(list_df) if list_df is not None else list_df
    item_summary = standardize_item_code_column(item_summary) if item_summary is not None else item_summary
    if list_df is None or list_df.empty or "Item Code" not in list_df.columns:
        return pd.DataFrame()
    if item_summary is None or item_summary.empty or "Item Code" not in item_summary.columns:
        return pd.DataFrame()
    out = list_df.merge(item_summary[["Item Code","Grp Name","Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)","Need"]], on="Item Code", how="left")
    for c in ["Stock Qty","Total Sales Qty (Period)","Total Sales Amount (Period)","Need"]:
        out[c] = to_num(out[c])
    out[status_name] = out.apply(lambda r: "Missing" if r["Stock Qty"] == 0 else ("Weak Sales" if r["Total Sales Qty (Period)"] == 0 else "Covered"), axis=1)
    return out.sort_values([status_name,"Need"], ascending=[True, False]).reset_index(drop=True)
