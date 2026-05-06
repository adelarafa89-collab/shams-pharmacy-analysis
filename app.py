
import streamlit as st
from shams_app.report_builder import build_report
from shams_app.excel_export import to_excel_bytes

class SafeUploadedFile:
    """Immutable in-memory copy of a Streamlit UploadedFile."""
    def __init__(self, uploaded_file):
        self.name = uploaded_file.name
        self.type = getattr(uploaded_file, "type", None)
        self.size = getattr(uploaded_file, "size", None)
        self._data = uploaded_file.getvalue()

    def getvalue(self):
        return self._data

    def read(self, *args, **kwargs):
        return self._data

    def seek(self, *args, **kwargs):
        return 0

def safe_file(uploaded_file):
    return SafeUploadedFile(uploaded_file) if uploaded_file is not None else None


st.set_page_config(page_title="Shams Pharmacy Analysis v5.6", page_icon="💊", layout="wide")
st.title("💊 Shams Pharmacy Analysis v5.6 - Dashboard")
st.caption("NUPCO channel rows fix + reference reports")

with st.sidebar:
    st.subheader("الإعدادات")
    months_count = st.number_input("عدد الشهور", min_value=0.5, max_value=24.0, value=3.0, step=0.5)
    st.markdown("---")
    st.markdown("""
**الإلزامي**
- Stock
- Sales

**الاختياري**
- Target Achievement
- CAWSA
- Monthly Review
- Offers
- Promoted Items
- Wasfaty Active
- Wasfaty Golden
""")

c1, c2 = st.columns(2)
with c1:
    stock_file = st.file_uploader("ارفع ملف Stock", type=["xls","xlsx","xlsm","csv"])
with c2:
    sales_file = st.file_uploader("ارفع ملف Sales", type=["xls","xlsx","xlsm","csv"])

c3, c4 = st.columns(2)
with c3:
    target_file = st.file_uploader("ارفع ملف Target Achievement (اختياري)", type=["xls","xlsx","xlsm","csv"])
with c4:
    cawsa_file = st.file_uploader("ارفع ملف CAWSA (اختياري)", type=["xls","xlsx","xlsm","csv"])

c5, c6 = st.columns(2)
with c5:
    staff_file = st.file_uploader("ارفع ملف Monthly Review (اختياري)", type=["xls","xlsx","xlsm","csv"])
with c6:
    offers_file = st.file_uploader("ارفع ملف Offers (اختياري)", type=["xls","xlsx","xlsm","csv"])

c7, c8 = st.columns(2)
with c7:
    promoted_file = st.file_uploader("ارفع ملف Promoted Items / PL (اختياري)", type=["xls","xlsx","xlsm","csv"])
with c8:
    active_file = st.file_uploader("ارفع ملف Wasfaty Active (اختياري)", type=["xls","xlsx","xlsm","csv"])

golden_file = st.file_uploader("ارفع ملف Wasfaty Golden (اختياري)", type=["xls","xlsx","xlsm","csv"])

if stock_file is not None and sales_file is not None:
    if st.button("تشغيل التحليل الكامل", type="primary", use_container_width=True):
        with st.spinner("جاري إنشاء التقرير الكامل..."):
            try:
                # Convert every uploaded file to a safe immutable bytes copy before analysis.
                # This prevents "I/O operation on closed file" with old XLS files.
                sheets, meta, info = build_report(
                    safe_file(stock_file), safe_file(sales_file), months_count,
                    target_file=safe_file(target_file),
                    cawsa_file=safe_file(cawsa_file),
                    staff_file=safe_file(staff_file),
                    offers_file=safe_file(offers_file),
                    promoted_file=safe_file(promoted_file),
                    wasfaty_active_file=safe_file(active_file),
                    wasfaty_golden_file=safe_file(golden_file),
                )
                st.session_state["sheets"] = sheets
                st.session_state["meta"] = meta
                st.session_state["info"] = info
                st.session_state["excel"] = to_excel_bytes(sheets, meta)
            except Exception as e:
                for k in ["sheets", "meta", "info", "excel"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.error(f"حدث خطأ أثناء التحليل: {e}")

if "info" in st.session_state and "excel" in st.session_state:
    info = st.session_state["info"]
    sheets = st.session_state["sheets"]
    excel_bytes = st.session_state["excel"]

    cols = st.columns(8)
    metrics = [
        ("Branch", info["branch"] or "-"),
        ("Level", info["level"]),
        ("Sales Rows", f"{info['sales_rows']:,}"),
        ("Stock Rows", f"{info['stock_rows']:,}"),
        ("Items", f"{info['items']:,}"),
        ("Actions", f"{info['actions']:,}"),
        ("High Risk", f"{info['high_risk']:,}"),
        ("Loaded Modules", f"{info['loaded_modules']:,}"),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)

    st.download_button(
        "تحميل التقرير Excel",
        data=excel_bytes,
        file_name=f"Shams_Pharmacy_{info['branch'] or 'Branch'}_v5_6.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.markdown("### Preview")
    selected = st.selectbox("اختر الشيت", list(sheets.keys()))
    st.dataframe(sheets[selected], use_container_width=True, height=520)

st.markdown("---")
st.caption("Developed by Adel Arafa")
