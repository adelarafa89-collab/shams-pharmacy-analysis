
import pandas as pd
from .core import build_core
from .parsers import (
    clean_target, clean_cawsa, clean_staff, build_staff_outputs,
    clean_offers, build_offers_performance, clean_promoted, build_promoted_performance,
    clean_wasfaty_list, build_wasfaty_control
)
from .analytics import build_availability_risk, build_root_cause, build_priority_items
from .legacy_reports import (
    build_abc_qty_legacy, build_abc_amount_legacy, build_abc_nupco_qty, build_abc_nupco_amount,
    build_top_customers_legacy, build_top_categories_legacy, build_item_summary_legacy
)

def build_action_plan(core, availability_df, target_monthly=None, cawsa_df=None, staff_impact=None, promoted_perf=None, offers_perf=None, golden_df=None, active_df=None):
    item_summary = core["item_summary"].copy()
    actions = []

    for _, r in item_summary[(item_summary["ABC Class (Qty 70%)"] == "A") & (item_summary["Need"] > 0)].sort_values("Need", ascending=False).head(20).iterrows():
        actions.append({"Priority":"High","Type":"Critical","Category":r["Grp Name"],"Item":r["Item Name"],"Issue":"High demand item needs replenishment","Reason":"ABC A + Need > 0","Action":"Order now","Impact":"Prevent sales loss"})
    for _, r in item_summary[(item_summary["Total Sales Qty (Period)"] == 0) & (item_summary["Stock Qty"] > 0)].sort_values("Retail Value", ascending=False).head(20).iterrows():
        actions.append({"Priority":"Medium","Type":"Dead Stock","Category":r["Grp Name"],"Item":r["Item Name"],"Issue":"Stock exists with no sales","Reason":"No sales + positive stock","Action":"Promote / bundle / transfer","Impact":"Free cash"})

    if availability_df is not None and not availability_df.empty:
        for _, r in availability_df[availability_df["Risk"]=="High"].head(25).iterrows():
            actions.append({"Priority":"High","Type":"Availability Risk","Category":r["Grp Name"],"Item":r["Item Name"],"Issue":"Low days of cover","Reason":"Less than 7 days","Action":"Urgent reorder","Impact":"Prevent stockout"})
        for _, r in availability_df[availability_df["Risk"]=="Medium"].head(25).iterrows():
            actions.append({"Priority":"Medium","Type":"Availability Risk","Category":r["Grp Name"],"Item":r["Item Name"],"Issue":"Medium days of cover","Reason":"Less than 15 days","Action":"Monitor and reorder soon","Impact":"Reduce risk"})

    if target_monthly is not None and not target_monthly.empty:
        latest = target_monthly.iloc[-1]
        latest_sales = float(latest.get("Total Sales Without VAT", 0))
        latest_basket = float(latest.get("Avg Basket", 0))
        latest_wasfaty = float(latest.get("Wasfaty %", 0))
        if latest_basket > 0 and latest_basket < float(target_monthly["Avg Basket"].median()):
            actions.append({"Priority":"Medium","Type":"Performance","Category":"Branch","Item":"-","Issue":"Average basket is below normal","Reason":"Low basket size versus historical level","Action":"Increase upsell / cross-sell","Impact":"Raise sales per customer"})
        if latest_wasfaty > 0.35:
            actions.append({"Priority":"Low","Type":"Mix","Category":"Branch","Item":"-","Issue":"High reliance on Wasfaty","Reason":"Wasfaty contribution is high","Action":"Grow OTC and front store sales","Impact":"Improve balance"})
        if latest_sales <= float(target_monthly["Total Sales Without VAT"].median()):
            actions.append({"Priority":"Medium","Type":"Performance","Category":"Branch","Item":"-","Issue":"Sales momentum is not strong","Reason":"Latest month below typical level","Action":"Focus on key opportunities","Impact":"Support target achievement"})

    if cawsa_df is not None and not cawsa_df.empty:
        grp_stock = item_summary.groupby("Grp Name", as_index=False).agg({"Stock Qty":"sum","Need":"sum"})
        below = cawsa_df[cawsa_df["Status"].astype(str).str.contains("Below", case=False, na=False)].copy()
        above = cawsa_df[cawsa_df["Status"].astype(str).str.contains("Above", case=False, na=False)].copy()
        for _, r in below.sort_values("Gap").head(12).iterrows():
            g = grp_stock[grp_stock["Grp Name"] == r["Grp Name"]]
            stock_qty = float(g["Stock Qty"].sum()) if not g.empty else 0
            if stock_qty > 0:
                actions.append({"Priority":"Medium","Type":"Opportunity","Category":r["Grp Name"],"Item":"-","Issue":"Category is below region share","Reason":"CAWSA Below + stock available","Action":"Push sales / visibility / recommendation","Impact":"Capture growth"})
            else:
                actions.append({"Priority":"High","Type":"Supply Issue","Category":r["Grp Name"],"Item":"-","Issue":"Category is below region and stock is weak","Reason":"CAWSA Below + low stock","Action":"Order category depth","Impact":"Fix lost opportunity"})
        for _, r in above.sort_values("Gap", ascending=False).head(8).iterrows():
            actions.append({"Priority":"Low","Type":"Strength","Category":r["Grp Name"],"Item":"-","Issue":"Category is above region share","Reason":"CAWSA Above","Action":"Maintain and expand winners","Impact":"Protect strength"})

    if staff_impact is not None and not staff_impact.empty:
        low_staff = float(staff_impact.loc[staff_impact["Metric"]=="Low Staff Count (<60 BS)", "Value"].iloc[0]) if (staff_impact["Metric"]=="Low Staff Count (<60 BS)").any() else 0
        if low_staff > 0:
            actions.append({"Priority":"Medium","Type":"Staff Issue","Category":"Branch","Item":"-","Issue":"Some pharmacists have low BS score","Reason":"Monthly review","Action":"Coaching / training","Impact":"Improve execution"})

    if promoted_perf is not None and not promoted_perf.empty and "Promoted Status" in promoted_perf.columns:
        for _, r in promoted_perf[promoted_perf["Promoted Status"]=="No Stock"].head(15).iterrows():
            actions.append({"Priority":"High","Type":"Promoted Issue","Category":r.get("Grp Name",""),"Item":r["Item Name"],"Issue":"Promoted item has no stock","Reason":"Promoted + No Stock","Action":"Order promoted item","Impact":"Support execution"})
        for _, r in promoted_perf[promoted_perf["Promoted Status"]=="Weak Sales"].head(15).iterrows():
            actions.append({"Priority":"Medium","Type":"Promoted Issue","Category":r.get("Grp Name",""),"Item":r["Item Name"],"Issue":"Promoted item has weak sales","Reason":"Promoted + Weak Sales","Action":"Push by staff","Impact":"Increase promoted mix"})

    if offers_perf is not None and not offers_perf.empty and "Offer Status" in offers_perf.columns:
        for _, r in offers_perf[offers_perf["Offer Status"]=="No Stock"].head(15).iterrows():
            actions.append({"Priority":"High","Type":"Offer Issue","Category":r.get("CAT",""),"Item":r["Item Name"],"Issue":"Offer item has no stock","Reason":"Offer + No Stock","Action":"Stock the offer item","Impact":"Protect promotion"})
        for _, r in offers_perf[offers_perf["Offer Status"]=="Weak Sales"].head(15).iterrows():
            actions.append({"Priority":"Medium","Type":"Offer Issue","Category":r.get("CAT",""),"Item":r["Item Name"],"Issue":"Offer item sales are weak","Reason":"Offer + Weak Sales","Action":"Check display / execution","Impact":"Improve offer ROI"})

    if golden_df is not None and not golden_df.empty and "Golden Status" in golden_df.columns:
        for _, r in golden_df[golden_df["Golden Status"]=="Missing"].head(15).iterrows():
            actions.append({"Priority":"High","Type":"Golden Risk","Category":r.get("SC",""),"Item":r["Item Name"],"Issue":"Golden item missing","Reason":"Golden + No Stock","Action":"Order immediately","Impact":"Protect Wasfaty priority"})

    if active_df is not None and not active_df.empty and "Active Status" in active_df.columns:
        for _, r in active_df[active_df["Active Status"]=="Missing"].head(15).iterrows():
            actions.append({"Priority":"High","Type":"Wasfaty Risk","Category":r.get("SC",""),"Item":r["Item Name"],"Issue":"Active Wasfaty item missing","Reason":"Active + No Stock","Action":"Replenish","Impact":"Prevent lost scripts"})

    action_df = pd.DataFrame(actions) if actions else pd.DataFrame(columns=["Priority","Type","Category","Item","Issue","Reason","Action","Impact"])
    if not action_df.empty:
        priority_order = pd.CategoricalDtype(categories=["High","Medium","Low"], ordered=True)
        action_df["Priority"] = action_df["Priority"].astype(priority_order)
        action_df = action_df.drop_duplicates().sort_values(["Priority","Type","Category","Item"]).reset_index(drop=True)
    return action_df

def build_key_insights(core, action_plan, availability_df, root_cause_df, target_monthly=None, cawsa_df=None, staff_perf=None, promoted_perf=None, offers_perf=None, golden_df=None, active_df=None):
    item_summary = core["item_summary"]
    insights = []
    need_items = int((item_summary["Need"] > 0).sum())
    dead_stock_items = int(((item_summary["Total Sales Qty (Period)"] == 0) & (item_summary["Stock Qty"] > 0)).sum())
    a_need = int(((item_summary["ABC Class (Qty 70%)"] == "A") & (item_summary["Need"] > 0)).sum())
    high_risk_items = int((availability_df["Risk"] == "High").sum()) if availability_df is not None and not availability_df.empty else 0
    insights += [
        {"Area":"Inventory","Insight":f"{need_items} items need replenishment.","Severity":"High" if need_items else "Low"},
        {"Area":"Inventory","Insight":f"{a_need} A-class items need urgent order.","Severity":"High" if a_need else "Low"},
        {"Area":"Inventory","Insight":f"{dead_stock_items} items are dead stock with positive balance.","Severity":"Medium" if dead_stock_items else "Low"},
        {"Area":"Availability","Insight":f"{high_risk_items} items have high availability risk.","Severity":"High" if high_risk_items else "Low"},
        {"Area":"Sales","Insight":f"Branch has {item_summary['Item Code'].nunique()} selling items in the analyzed period.","Severity":"Info"},
    ]
    if root_cause_df is not None and not root_cause_df.empty:
        for cause, count in root_cause_df["Cause"].value_counts().items():
            insights.append({"Area":"Diagnosis","Insight":f"{count} cases classified as {cause}.","Severity":"Info"})
    if target_monthly is not None and not target_monthly.empty:
        latest = target_monthly.iloc[-1]
        insights += [
            {"Area":"Performance","Insight":f"Latest month sales without VAT: {latest['Total Sales Without VAT']:,.2f}.","Severity":"Info"},
            {"Area":"Performance","Insight":f"Latest average basket: {latest['Avg Basket']:,.2f}.","Severity":"Info"},
            {"Area":"Channel Mix","Insight":f"Wasfaty contribution: {latest['Wasfaty %']:.1%}.","Severity":"Info"},
            {"Area":"Channel Mix","Insight":f"Home delivery contribution: {latest['Home Delivery %']:.1%}.","Severity":"Info"},
        ]
    if cawsa_df is not None and not cawsa_df.empty:
        insights += [
            {"Area":"Benchmark","Insight":f"{int(cawsa_df['Status'].astype(str).str.contains('Below', case=False, na=False).sum())} categories are below region benchmark.","Severity":"Medium"},
            {"Area":"Benchmark","Insight":f"{int(cawsa_df['Status'].astype(str).str.contains('Above', case=False, na=False).sum())} categories are above region benchmark.","Severity":"Info"},
        ]
    if staff_perf is not None and not staff_perf.empty:
        insights.append({"Area":"Staff","Insight":f"{len(staff_perf)} pharmacists found for this branch.","Severity":"Info"})
    if promoted_perf is not None and not promoted_perf.empty:
        weak = int((promoted_perf["Promoted Status"]=="Weak Sales").sum())
        insights.append({"Area":"Promoted","Insight":f"{weak} promoted items have weak sales.","Severity":"Medium" if weak else "Low"})
    if offers_perf is not None and not offers_perf.empty:
        weak = int((offers_perf["Offer Status"]=="Weak Sales").sum())
        insights.append({"Area":"Offers","Insight":f"{weak} offer items have weak sales.","Severity":"Medium" if weak else "Low"})
    if golden_df is not None and not golden_df.empty:
        miss = int((golden_df["Golden Status"]=="Missing").sum())
        insights.append({"Area":"Wasfaty Golden","Insight":f"{miss} golden items are missing.","Severity":"High" if miss else "Low"})
    if active_df is not None and not active_df.empty:
        miss = int((active_df["Active Status"]=="Missing").sum())
        insights.append({"Area":"Wasfaty Active","Insight":f"{miss} active items are missing.","Severity":"High" if miss else "Low"})
    if action_plan is not None and not action_plan.empty:
        insights.append({"Area":"Action Plan","Insight":f"{len(action_plan)} recommended actions generated.","Severity":"Info"})
    return pd.DataFrame(insights)

def build_executive_summary(core, action_plan, availability_df, module_status, target_monthly=None, cawsa_df=None, staff_impact=None, promoted_perf=None, offers_perf=None, golden_df=None, active_df=None, level_name="Core"):
    item_summary = core["item_summary"]
    dead_stock_value = float(item_summary.loc[(item_summary["Total Sales Qty (Period)"] == 0) & (item_summary["Stock Qty"] > 0), "Retail Value"].sum())
    dead_stock_pct = dead_stock_value / core["total_stock"] if core["total_stock"] else 0
    high_risk_items = int((availability_df["Risk"] == "High").sum()) if availability_df is not None and not availability_df.empty else 0
    rows = [
        {"KPI":"Analysis Level","Value":level_name},
        {"KPI":"Branch","Value":core["branch"] or "-"},
        {"KPI":"Total Sales","Value":core["total_sales"]},
        {"KPI":"Stock Value","Value":core["total_stock"]},
        {"KPI":"Dead Stock %","Value":dead_stock_pct},
        {"KPI":"High Risk Items","Value":high_risk_items},
        {"KPI":"Critical Actions","Value":int((action_plan["Priority"] == "High").sum()) if action_plan is not None and not action_plan.empty else 0},
        {"KPI":"Opportunities","Value":int((action_plan["Type"] == "Opportunity").sum()) if action_plan is not None and not action_plan.empty else 0},
        {"KPI":"Top Category","Value":str(core["top_categories"].iloc[0]["Category (GrpName)"]) if not core["top_categories"].empty else ""},
        {"KPI":"Modules Loaded","Value":int((module_status["Loaded"]=="Yes").sum()) if not module_status.empty else 0},
    ]
    if target_monthly is not None and not target_monthly.empty:
        latest = target_monthly.iloc[-1]
        rows.append({"KPI":"Target Achievement","Value":float(latest.get("Achievement %", 0))})
        rows.append({"KPI":"Avg Basket","Value":float(latest.get("Avg Basket", 0))})
    if cawsa_df is not None and not cawsa_df.empty:
        rows.append({"KPI":"Below Region Categories","Value":int(cawsa_df["Status"].astype(str).str.contains("Below", case=False, na=False).sum())})
    if staff_impact is not None and not staff_impact.empty:
        rows.extend(staff_impact.rename(columns={"Metric":"KPI","Value":"Value"}).to_dict(orient="records"))
    if promoted_perf is not None and not promoted_perf.empty and "Promoted Status" in promoted_perf.columns:
        rows.append({"KPI":"Promoted Weak Items","Value":int((promoted_perf["Promoted Status"]=="Weak Sales").sum())})
    if offers_perf is not None and not offers_perf.empty and "Offer Status" in offers_perf.columns:
        rows.append({"KPI":"Offers Weak Items","Value":int((offers_perf["Offer Status"]=="Weak Sales").sum())})
    if golden_df is not None and not golden_df.empty and "Golden Status" in golden_df.columns:
        rows.append({"KPI":"Golden Missing","Value":int((golden_df["Golden Status"]=="Missing").sum())})
    if active_df is not None and not active_df.empty and "Active Status" in active_df.columns:
        rows.append({"KPI":"Active Missing","Value":int((active_df["Active Status"]=="Missing").sum())})
    return pd.DataFrame(rows)


def build_dashboard_summary(core, action_plan, availability_df, root_cause_df, module_status,
                            target_monthly=None, cawsa_df=None, staff_impact=None,
                            promoted_perf=None, offers_perf=None, golden_df=None, active_df=None,
                            priority_items=None):
    item_summary = core["item_summary"]
    rows = []

    def add(section, metric, value, status="", note=""):
        rows.append({"Section": section, "Metric": metric, "Value": value, "Status": status, "Note": note})

    total_items = int(item_summary["Item Code"].nunique())
    need_items = int((item_summary["Need"] > 0).sum())
    a_need = int(((item_summary["ABC Class (Qty 70%)"] == "A") & (item_summary["Need"] > 0)).sum())
    dead_stock_items = int(((item_summary["Total Sales Qty (Period)"] == 0) & (item_summary["Stock Qty"] > 0)).sum())
    dead_stock_value = float(item_summary.loc[
        (item_summary["Total Sales Qty (Period)"] == 0) & (item_summary["Stock Qty"] > 0), "Retail Value"
    ].sum())
    high_risk = int((availability_df["Risk"] == "High").sum()) if availability_df is not None and not availability_df.empty else 0
    medium_risk = int((availability_df["Risk"] == "Medium").sum()) if availability_df is not None and not availability_df.empty else 0
    critical_actions = int((action_plan["Priority"] == "High").sum()) if action_plan is not None and not action_plan.empty else 0

    add("Core", "Total Sales", core["total_sales"], "Info", "From Sales file")
    add("Core", "Stock Value", core["total_stock"], "Info", "From Stock file; LzQty ignored")
    add("Core", "Total Items", total_items, "Info")
    add("Inventory", "Need Order Items", need_items, "High" if need_items else "OK")
    add("Inventory", "ABC A Items Need Order", a_need, "High" if a_need else "OK")
    add("Inventory", "Dead Stock Items", dead_stock_items, "Medium" if dead_stock_items else "OK")
    add("Inventory", "Dead Stock Value", dead_stock_value, "Medium" if dead_stock_value else "OK")
    add("Availability", "High Risk Items", high_risk, "High" if high_risk else "OK", "Days of Cover < 7")
    add("Availability", "Medium Risk Items", medium_risk, "Medium" if medium_risk else "OK", "Days of Cover < 15")
    add("Actions", "Critical Actions", critical_actions, "High" if critical_actions else "OK")
    add("Actions", "Total Actions", len(action_plan) if action_plan is not None else 0, "Info")
    add("Actions", "Priority Items", len(priority_items) if priority_items is not None else 0, "Info")

    if target_monthly is not None and not target_monthly.empty:
        latest = target_monthly.iloc[-1]
        add("Target", "Latest Sales Without VAT", float(latest.get("Total Sales Without VAT", 0)), "Info")
        add("Target", "Latest Avg Basket", float(latest.get("Avg Basket", 0)), "Info")
        add("Target", "Wasfaty %", float(latest.get("Wasfaty %", 0)), "Info")
        add("Target", "Home Delivery %", float(latest.get("Home Delivery %", 0)), "Info")
    else:
        add("Target", "Target Layer", "Not loaded", "Not Loaded")

    if cawsa_df is not None and not cawsa_df.empty:
        below = int(cawsa_df["Status"].astype(str).str.contains("Below", case=False, na=False).sum())
        above = int(cawsa_df["Status"].astype(str).str.contains("Above", case=False, na=False).sum())
        add("CAWSA", "Below Region Categories", below, "Medium" if below else "OK")
        add("CAWSA", "Above Region Categories", above, "Info")
    else:
        add("CAWSA", "CAWSA Layer", "Not loaded", "Not Loaded")

    if staff_impact is not None and not staff_impact.empty:
        for _, r in staff_impact.iterrows():
            add("Staff", r["Metric"], r["Value"], "Info")
    else:
        add("Staff", "Staff Layer", "Not loaded", "Not Loaded")

    if promoted_perf is not None and not promoted_perf.empty and "Promoted Status" in promoted_perf.columns:
        add("Promoted", "Promoted Items", len(promoted_perf), "Info")
        add("Promoted", "Promoted No Stock", int((promoted_perf["Promoted Status"] == "No Stock").sum()), "High")
        add("Promoted", "Promoted Weak Sales", int((promoted_perf["Promoted Status"] == "Weak Sales").sum()), "Medium")
    else:
        add("Promoted", "Promoted Layer", "Not loaded", "Not Loaded")

    if offers_perf is not None and not offers_perf.empty and "Offer Status" in offers_perf.columns:
        add("Offers", "Offer Items", len(offers_perf), "Info")
        add("Offers", "Offers No Stock", int((offers_perf["Offer Status"] == "No Stock").sum()), "High")
        add("Offers", "Offers Weak Sales", int((offers_perf["Offer Status"] == "Weak Sales").sum()), "Medium")
    else:
        add("Offers", "Offers Layer", "Not loaded", "Not Loaded")

    if active_df is not None and not active_df.empty and "Active Status" in active_df.columns:
        add("Wasfaty Active", "Active Items", len(active_df), "Info")
        add("Wasfaty Active", "Active Missing", int((active_df["Active Status"] == "Missing").sum()), "High")
        add("Wasfaty Active", "Active Weak Sales", int((active_df["Active Status"] == "Weak Sales").sum()), "Medium")
    else:
        add("Wasfaty Active", "Active Layer", "Not loaded", "Not Loaded")

    if golden_df is not None and not golden_df.empty and "Golden Status" in golden_df.columns:
        add("Wasfaty Golden", "Golden Items", len(golden_df), "Info")
        add("Wasfaty Golden", "Golden Missing", int((golden_df["Golden Status"] == "Missing").sum()), "High")
        add("Wasfaty Golden", "Golden Weak Sales", int((golden_df["Golden Status"] == "Weak Sales").sum()), "Medium")
    else:
        add("Wasfaty Golden", "Golden Layer", "Not loaded", "Not Loaded")

    if module_status is not None and not module_status.empty:
        add("Modules", "Uploaded Modules", int((module_status["Uploaded"] == "Yes").sum()), "Info")
        add("Modules", "Loaded Modules", int((module_status["Loaded"] == "Yes").sum()), "Info")

    return pd.DataFrame(rows)


def build_report(stock_file, sales_file, months_count, target_file=None, cawsa_file=None, staff_file=None, offers_file=None, promoted_file=None, wasfaty_active_file=None, wasfaty_golden_file=None):
    try:
        core = build_core(stock_file, sales_file, months_count)
    except KeyError as e:
        raise KeyError(f"Core parsing failed. Missing column: {e}. Please check Sales/Stock format.")
    module_rows = []

    def add_status(name, uploaded, loaded, details):
        module_rows.append({"Module":name, "Uploaded":"Yes" if uploaded else "No", "Loaded":"Yes" if loaded else "No", "Details":details})

    target_daily = target_monthly = cawsa_df = None
    staff_perf = staff_impact = None
    offers_perf = promoted_perf = None
    active_control = golden_control = None

    if target_file is not None:
        try:
            target_daily, target_monthly = clean_target(target_file)
            loaded = ((target_daily is not None and not target_daily.empty) or (target_monthly is not None and not target_monthly.empty))
            add_status("Target", True, loaded, f"Daily rows={len(target_daily) if target_daily is not None else 0}, Monthly rows={len(target_monthly) if target_monthly is not None else 0}")
            if target_daily is not None and target_daily.empty: target_daily = None
            if target_monthly is not None and target_monthly.empty: target_monthly = None
        except Exception as e:
            add_status("Target", True, False, str(e))
    else:
        add_status("Target", False, False, "Not uploaded")

    if cawsa_file is not None:
        try:
            cawsa_df = clean_cawsa(cawsa_file)
            loaded = cawsa_df is not None and not cawsa_df.empty
            add_status("CAWSA", True, loaded, f"Rows={len(cawsa_df) if cawsa_df is not None else 0}")
            if cawsa_df is not None and cawsa_df.empty: cawsa_df = None
        except Exception as e:
            add_status("CAWSA", True, False, str(e))
    else:
        add_status("CAWSA", False, False, "Not uploaded")

    if staff_file is not None:
        try:
            staff_raw = clean_staff(staff_file)
            staff_perf, staff_impact = build_staff_outputs(staff_raw, core["branch"])
            loaded = staff_perf is not None and not staff_perf.empty
            add_status("Staff Review", True, loaded, f"Rows={len(staff_perf) if staff_perf is not None else 0}")
            if staff_perf is not None and staff_perf.empty: staff_perf = None
            if staff_impact is not None and staff_impact.empty: staff_impact = None
        except Exception as e:
            add_status("Staff Review", True, False, str(e))
    else:
        add_status("Staff Review", False, False, "Not uploaded")

    if offers_file is not None:
        try:
            offers_raw = clean_offers(offers_file)
            offers_perf = build_offers_performance(offers_raw, core["item_summary"], core["branch"])
            loaded = offers_perf is not None and not offers_perf.empty
            add_status("Offers", True, loaded, f"Rows={len(offers_perf) if offers_perf is not None else 0}")
            if offers_perf is not None and offers_perf.empty: offers_perf = None
        except Exception as e:
            add_status("Offers", True, False, str(e))
    else:
        add_status("Offers", False, False, "Not uploaded")

    if promoted_file is not None:
        try:
            promoted_raw = clean_promoted(promoted_file)
            promoted_perf = build_promoted_performance(promoted_raw, core["item_summary"])
            loaded = promoted_perf is not None and not promoted_perf.empty
            add_status("Promoted Items", True, loaded, f"Rows={len(promoted_perf) if promoted_perf is not None else 0}")
            if promoted_perf is not None and promoted_perf.empty: promoted_perf = None
        except Exception as e:
            add_status("Promoted Items", True, False, str(e))
    else:
        add_status("Promoted Items", False, False, "Not uploaded")

    if wasfaty_active_file is not None:
        try:
            active_raw = clean_wasfaty_list(wasfaty_active_file, "Active")
            active_control = build_wasfaty_control(active_raw, core["item_summary"], "Active Status")
            loaded = active_control is not None and not active_control.empty
            add_status("Wasfaty Active", True, loaded, f"Rows={len(active_control) if active_control is not None else 0}")
            if active_control is not None and active_control.empty: active_control = None
        except Exception as e:
            add_status("Wasfaty Active", True, False, str(e))
    else:
        add_status("Wasfaty Active", False, False, "Not uploaded")

    if wasfaty_golden_file is not None:
        try:
            golden_raw = clean_wasfaty_list(wasfaty_golden_file, "Golden")
            golden_control = build_wasfaty_control(golden_raw, core["item_summary"], "Golden Status")
            loaded = golden_control is not None and not golden_control.empty
            add_status("Wasfaty Golden", True, loaded, f"Rows={len(golden_control) if golden_control is not None else 0}")
            if golden_control is not None and golden_control.empty: golden_control = None
        except Exception as e:
            add_status("Wasfaty Golden", True, False, str(e))
    else:
        add_status("Wasfaty Golden", False, False, "Not uploaded")

    module_status = pd.DataFrame(module_rows)
    level_parts = ["Core"]
    for name in ["Target","CAWSA","Staff Review","Offers","Promoted Items","Wasfaty Active","Wasfaty Golden"]:
        row = module_status[module_status["Module"] == name]
        if not row.empty and row.iloc[0]["Loaded"] == "Yes":
            level_parts.append(name)
    level = " + ".join(level_parts)

    availability_df = build_availability_risk(core["item_summary"])
    root_cause_df = build_root_cause(core["item_summary"])
    priority_items = build_priority_items(core["item_summary"], availability_df, golden_control, active_control, promoted_perf, offers_perf)
    action_plan = build_action_plan(core, availability_df, target_monthly, cawsa_df, staff_impact, promoted_perf, offers_perf, golden_control, active_control)
    dashboard_summary = build_dashboard_summary(core, action_plan, availability_df, root_cause_df, module_status, target_monthly, cawsa_df, staff_impact, promoted_perf, offers_perf, golden_control, active_control, priority_items)
    key_insights = build_key_insights(core, action_plan, availability_df, root_cause_df, target_monthly, cawsa_df, staff_perf, promoted_perf, offers_perf, golden_control, active_control)
    executive = build_executive_summary(core, action_plan, availability_df, module_status, target_monthly, cawsa_df, staff_impact, promoted_perf, offers_perf, golden_control, active_control, level)

    # Reference-style reports matching uploaded 2026.xlsm
    legacy_abc_qty = build_abc_qty_legacy(core["item_summary"])
    legacy_abc_amount = build_abc_amount_legacy(core["item_summary"])
    legacy_abc_nupco_qty = build_abc_nupco_qty(core["sales"])
    legacy_abc_nupco_amount = build_abc_nupco_amount(core["sales"])
    legacy_top_customers = build_top_customers_legacy(core["sales"])
    legacy_top_categories = build_top_categories_legacy(core["item_summary"])
    legacy_item_summary = build_item_summary_legacy(core["item_summary"], months_count)

    sheets = {
        "Executive_Summary": executive,
        "Dashboard": dashboard_summary,
        "Module_Status": module_status,
        "Action_Plan": action_plan,
        "Key_Insights": key_insights,
        "Priority_Items": priority_items,
        "Availability_Risk": availability_df,
        "Root_Cause_Diagnosis": root_cause_df,
        "ABC_NUPCO_Qty": legacy_abc_nupco_qty,
        "ABC_NUPCO_Amount": legacy_abc_nupco_amount,
        "TopCustomers": legacy_top_customers,
        "TopCategories": legacy_top_categories,
        "ITEM_SUMMARY_REF": legacy_item_summary,
        "Sales": core["sales"],
        "Stock": core["stock"],
        "Item_Summary": core["item_summary"],
        "ABC_Qty": core["abc_qty"],
        "ABC_Amount": core["abc_amt"],
        "Top_Customers": core["top_customers"],
        "Top_Categories": core["top_categories"],
    }

    if target_daily is not None: sheets["Target_Daily"] = target_daily
    if target_monthly is not None:
        sheets["Target_Summary"] = target_monthly
        mix_cols = [c for c in ["Month","Wasfaty %","Home Delivery %","Private Label %"] if c in target_monthly.columns]
        if mix_cols: sheets["Channel_Mix"] = target_monthly[mix_cols].copy()

    if cawsa_df is not None:
        sheets["CAWSA_Summary"] = cawsa_df
        opp = cawsa_df[cawsa_df["Status"].astype(str).str.contains("Below", case=False, na=False)].copy()
        if not opp.empty: sheets["CAWSA_Opportunities"] = opp
        strengths = cawsa_df[cawsa_df["Status"].astype(str).str.contains("Above", case=False, na=False)].copy()
        if not strengths.empty: sheets["CAWSA_Strengths"] = strengths

    if staff_perf is not None: sheets["Staff_Performance"] = staff_perf
    if staff_impact is not None: sheets["Staff_Impact"] = staff_impact
    if offers_perf is not None: sheets["Offers_Performance"] = offers_perf
    if promoted_perf is not None: sheets["Promoted_Items_Performance"] = promoted_perf
    if active_control is not None: sheets["Wasfaty_Active_Control"] = active_control
    if golden_control is not None: sheets["Wasfaty_Golden_Control"] = golden_control

    meta = {"branch": core["branch"] or "-", "months": months_count, "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "level": level}
    info = {
        "branch": core["branch"] or "", "level": level, "sales_rows": len(core["sales"]), "stock_rows": len(core["stock"]),
        "items": core["item_summary"]["Item Code"].nunique(), "total_sales": core["total_sales"], "total_stock": core["total_stock"],
        "actions": len(action_plan), "high_risk": int((availability_df["Risk"]=="High").sum()) if not availability_df.empty else 0,
        "loaded_modules": int((module_status["Loaded"]=="Yes").sum()) if not module_status.empty else 0,
    }
    return sheets, meta, info
