
import pandas as pd
from .helpers import classify_abc, to_num

def _abc_class_from_sorted(df, value_col, share_name="Share%", cum_name="Cum%"):
    total = float(df[value_col].sum()) if value_col in df.columns else 0
    if total:
        df[share_name] = df[value_col] / total
        df[cum_name] = df[share_name].cumsum()
    else:
        df[share_name] = 0
        df[cum_name] = 0
    df["Class"] = df[cum_name].apply(classify_abc)
    return df

def build_abc_qty_legacy(item_summary):
    df = item_summary[["Item Code","Item Name","Total Sales Qty (Period)","Grp Name"]].copy()
    df = df.rename(columns={"Total Sales Qty (Period)":"Total Qty","Grp Name":"Group"})
    df["NUPCO?"] = "No"
    df = df.sort_values(["Total Qty","Item Code"], ascending=[False, True]).reset_index(drop=True)
    df = _abc_class_from_sorted(df, "Total Qty")
    return df[["Item Code","Item Name","Total Qty","Group","NUPCO?","Share%","Cum%","Class"]]

def build_abc_amount_legacy(item_summary):
    df = item_summary[["Item Code","Item Name","Total Sales Amount (Period)","Grp Name"]].copy()
    df = df.rename(columns={"Total Sales Amount (Period)":"Total Amount","Grp Name":"Group"})
    df["NUPCO?"] = "No"
    df = df.sort_values(["Total Amount","Item Code"], ascending=[False, True]).reset_index(drop=True)
    df = _abc_class_from_sorted(df, "Total Amount")
    return df[["Item Code","Item Name","Total Amount","Group","NUPCO?","Share%","Cum%","Class"]]

def _nupco_sales(sales_df):
    if sales_df is None or sales_df.empty or "CUSTOMER NAME" not in sales_df.columns:
        return pd.DataFrame()
    mask = sales_df["CUSTOMER NAME"].astype(str).str.contains("NUPCO|نوبكو|الوطنية للشراء", case=False, na=False)
    return sales_df[mask].copy()

def build_abc_nupco_qty(sales_df):
    nupco = _nupco_sales(sales_df)
    if nupco.empty:
        return pd.DataFrame(columns=["Item Code","Item Name","NUPCO Qty","Share%","Cum%","Class"])
    df = nupco.groupby(["Item Code","Item Name"], as_index=False).agg({"SaleQty":"sum"})
    df = df.rename(columns={"SaleQty":"NUPCO Qty"})
    df = df.sort_values(["NUPCO Qty","Item Code"], ascending=[False, True]).reset_index(drop=True)
    df = _abc_class_from_sorted(df, "NUPCO Qty")
    return df[["Item Code","Item Name","NUPCO Qty","Share%","Cum%","Class"]]

def build_abc_nupco_amount(sales_df):
    nupco = _nupco_sales(sales_df)
    if nupco.empty:
        return pd.DataFrame(columns=["Item Code","Item Name","NUPCO Amount","Share%","Cum%","Class"])
    df = nupco.groupby(["Item Code","Item Name"], as_index=False).agg({"SaleAmt":"sum"})
    df = df.rename(columns={"SaleAmt":"NUPCO Amount"})
    df = df.sort_values(["NUPCO Amount","Item Code"], ascending=[False, True]).reset_index(drop=True)
    df = _abc_class_from_sorted(df, "NUPCO Amount")
    return df[["Item Code","Item Name","NUPCO Amount","Share%","Cum%","Class"]]

def build_top_customers_legacy(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame(columns=["Customer Name","Total Amount"])
    out = sales_df.groupby("CUSTOMER NAME", as_index=False).agg({"SaleAmt":"sum"})
    out = out.rename(columns={"CUSTOMER NAME":"Customer Name","SaleAmt":"Total Amount"})
    return out.sort_values("Total Amount", ascending=False).reset_index(drop=True)

def build_top_categories_legacy(item_summary):
    df = item_summary.groupby("Grp Name", as_index=False).agg({
        "Total Sales Qty (Period)":"sum",
        "Total Sales Amount (Period)":"sum",
    })
    df = df.rename(columns={
        "Grp Name":"Category (GrpName)",
        "Total Sales Qty (Period)":"Total Qty",
        "Total Sales Amount (Period)":"Total Amount",
    })
    df = df.sort_values(["Total Amount","Category (GrpName)"], ascending=[False, True]).reset_index(drop=True)
    df = _abc_class_from_sorted(df, "Total Amount")
    return df[["Category (GrpName)","Total Qty","Total Amount","Share%","Cum%","Class"]]

def build_item_summary_legacy(item_summary, months_count):
    df = item_summary.copy()
    out = df[[
        "Item Code","Item Name","Grp Name","Total Sales Qty (Period)","Total Sales Amount (Period)",
        "Avg 2 Months (Qty)","Stock Qty","Retail Value","Need","ABC Class (Qty 70%)"
    ]].copy()

    def status(r):
        if r["Need"] > 0:
            return "NEED"
        if r["Total Sales Qty (Period)"] == 0 and r["Stock Qty"] > 0:
            return "OVERSTOCK"
        return "ENOUGH"

    out["Status"] = out.apply(status, axis=1)

    # Add metadata columns similar to the reference report.
    out[""] = ""
    out["Months Basis"] = ""
    out["Value"] = ""
    out["Value"] = out["Value"].astype("object")
    if len(out) > 0:
        out.loc[out.index[0], "Months Basis"] = "Months Basis"
        out.loc[out.index[0], "Value"] = str(months_count)
    if len(out) > 1:
        out.loc[out.index[1], "Months Basis"] = "Rate Window"
        out.loc[out.index[1], "Value"] = "2 months"
    if len(out) > 3:
        counts = out["Status"].value_counts()
        out.loc[out.index[3], "Months Basis"] = "Status"
        out.loc[out.index[3], "Value"] = "Count"
        row = 4
        for k in ["NEED","ENOUGH","OVERSTOCK"]:
            if row < len(out):
                out.loc[out.index[row], "Months Basis"] = k
                out.loc[out.index[row], "Value"] = str(int(counts.get(k, 0)))
                row += 1

    return out
