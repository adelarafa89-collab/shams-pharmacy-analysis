
import pandas as pd

def build_availability_risk(item_summary):
    df = item_summary.copy()
    df["Daily Usage"] = df["Avg Monthly Qty"] / 30.0
    df["Days of Cover"] = df.apply(lambda r: r["Stock Qty"] / r["Daily Usage"] if r["Daily Usage"] > 0 else (999 if r["Stock Qty"] > 0 else 0), axis=1)
    def risk_level(days):
        if days < 7: return "High"
        if days < 15: return "Medium"
        return "Low"
    df["Risk"] = df["Days of Cover"].apply(risk_level)
    return df[["Item Code","Item Name","Grp Name","Stock Qty","Total Sales Qty (Period)","Daily Usage","Days of Cover","Risk"]].sort_values(["Days of Cover","Stock Qty"], ascending=[True, True]).reset_index(drop=True)

def build_root_cause(item_summary):
    rows = []
    for _, r in item_summary.iterrows():
        stock = float(r["Stock Qty"]); sales = float(r["Total Sales Qty (Period)"]); need = float(r["Need"]); abc = str(r["ABC Class (Qty 70%)"])
        if stock == 0 and sales == 0:
            cause, action = "No Demand / No Availability", "Review demand and availability"
        elif stock == 0 and sales > 0:
            cause, action = "Availability Issue", "Replenish immediately"
        elif stock > 0 and sales == 0:
            cause, action = "Execution Issue", "Promote / review visibility / transfer"
        elif abc == "A" and need > 0:
            cause, action = "High Demand Not Supported", "Urgent reorder"
        elif need > 0:
            cause, action = "Understock", "Planned reorder"
        else:
            continue
        rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Category":r["Grp Name"], "Signal":f"Stock={stock:.0f} / Sales={sales:.0f} / Need={need:.0f}", "Cause":cause, "Suggested Action":action})
    return pd.DataFrame(rows)

def build_priority_items(item_summary, availability_df=None, golden_df=None, active_df=None, promoted_perf=None, offers_perf=None):
    rows = []
    for _, r in item_summary[(item_summary["ABC Class (Qty 70%)"]=="A") & (item_summary["Need"]>0)].sort_values("Need", ascending=False).head(20).iterrows():
        rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"ABC", "Type":"Critical", "Issue":"A class item needs order", "Priority":"High", "Action":"Order now"})
    if availability_df is not None and not availability_df.empty:
        for _, r in availability_df[availability_df["Risk"]=="High"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Availability", "Type":"Stockout Risk", "Issue":"Days of cover below 7", "Priority":"High", "Action":"Urgent reorder"})
    if golden_df is not None and not golden_df.empty and "Golden Status" in golden_df.columns and "Item Code" in golden_df.columns:
        for _, r in golden_df[golden_df["Golden Status"]=="Missing"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Wasfaty Golden", "Type":"Golden Risk", "Issue":"Golden item missing", "Priority":"High", "Action":"Order immediately"})
    if active_df is not None and not active_df.empty and "Active Status" in active_df.columns and "Item Code" in active_df.columns:
        for _, r in active_df[active_df["Active Status"]=="Missing"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Wasfaty Active", "Type":"Wasfaty Risk", "Issue":"Active item missing", "Priority":"High", "Action":"Replenish"})
    if promoted_perf is not None and not promoted_perf.empty and "Promoted Status" in promoted_perf.columns and "Item Code" in promoted_perf.columns:
        for _, r in promoted_perf[promoted_perf["Promoted Status"]=="No Stock"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Promoted", "Type":"Promoted Issue", "Issue":"Promoted item has no stock", "Priority":"High", "Action":"Order promoted item"})
        for _, r in promoted_perf[promoted_perf["Promoted Status"]=="Weak Sales"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Promoted", "Type":"Promoted Issue", "Issue":"Promoted item sales are weak", "Priority":"Medium", "Action":"Coach staff / push item"})
    if offers_perf is not None and not offers_perf.empty and "Offer Status" in offers_perf.columns and "Item Code" in offers_perf.columns:
        for _, r in offers_perf[offers_perf["Offer Status"]=="No Stock"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Offer", "Type":"Offer Issue", "Issue":"Offer item has no stock", "Priority":"High", "Action":"Stock the offer item"})
        for _, r in offers_perf[offers_perf["Offer Status"]=="Weak Sales"].head(20).iterrows():
            rows.append({"Item Code":r["Item Code"], "Item Name":r["Item Name"], "Source":"Offer", "Type":"Offer Issue", "Issue":"Offer item sales are weak", "Priority":"Medium", "Action":"Check display / execution"})
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["Item Code","Item Name","Source","Type","Issue","Priority","Action"])
    priority_order = pd.CategoricalDtype(categories=["High","Medium","Low"], ordered=True)
    out["Priority"] = out["Priority"].astype(priority_order)
    return out.drop_duplicates().sort_values(["Priority","Source","Item Code"]).reset_index(drop=True)
