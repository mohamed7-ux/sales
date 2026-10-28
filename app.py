import streamlit as st
import pandas as pd
import mssql_python

st.set_page_config(
    page_title="Sales Dashboard",
    page_icon="📊",
    layout="wide"
)

SERVER = r"DESKTOP-IFO80R1\SQLEXPRESS"
FILTER_KEYS = ["f_products", "f_qty", "f_price", "f_profit", "f_sort"]


@st.cache_data(ttl=30)   # يسحب من القاعدة كل 30 ثانية بدل كل ما تغيّر فلتر
def load_data():
    connection_string = (
        f"Server={SERVER};"
        "Database=project;"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    conn = mssql_python.connect(connection_string)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, Product, Quantity, UnitPrice, UnitCost
            FROM dbo.Sales
            ORDER BY ID DESC
        """)
        rows = cursor.fetchall()
        df = pd.DataFrame(
            [tuple(row) for row in rows],
            columns=["ID", "Product", "Quantity", "UnitPrice", "UnitCost"]
        )
    finally:
        conn.close()

    # SQL Server بيرجّع الأرقام العشرية كـ Decimal، فنحوّلها لأرقام عادية
    for col in ["Quantity", "UnitPrice", "UnitCost"]:
        df[col] = pd.to_numeric(df[col])

    df["Sales"] = df["Quantity"] * df["UnitPrice"]
    df["Cost"] = df["Quantity"] * df["UnitCost"]
    df["Profit"] = df["Sales"] - df["Cost"]
    return df


def refresh():
    st.cache_data.clear()


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def range_slider(label, series, key, step=None):
    lo, hi = series.min(), series.max()
    if lo == hi:                      # السلايدر بيضرب لو الحدين متساويين
        st.caption(f"{label}: {lo}")
        return lo, hi
    return st.slider(label, lo, hi, (lo, hi), step=step, key=key)


st.title("📊 Sales Dashboard")
st.write("Dashboard connected to SQL Server")

try:
    df = load_data()

    if df.empty:
        st.warning("No sales data available.")
        st.stop()

    # ---------------- الفلاتر ----------------
    with st.sidebar:
        st.header("🔎 Filters")

        products = sorted(df["Product"].dropna().unique())
        sel_products = st.multiselect("Product", products, default=products, key="f_products")

        qty_range = range_slider("Quantity", df["Quantity"].astype(int), "f_qty")
        price_range = range_slider("Unit Price", df["UnitPrice"].astype(float), "f_price")

        profit_filter = st.radio(
            "Profit status",
            ["All", "Profitable only", "Loss-making only"],
            key="f_profit"
        )
        sort_by = st.selectbox("Sort products by", ["Sales", "Profit", "Quantity"], key="f_sort")

        st.divider()
        st.button("🔄 Refresh Data", on_click=refresh)
        st.button("↩️ Reset filters", on_click=reset_filters)

    # ---------------- تطبيق الفلاتر ----------------
    mask = (
        df["Product"].isin(sel_products)
        & df["Quantity"].between(*qty_range)
        & df["UnitPrice"].between(*price_range)
    )
    if profit_filter == "Profitable only":
        mask &= df["Profit"] > 0
    elif profit_filter == "Loss-making only":
        mask &= df["Profit"] < 0

    fdf = df[mask]

    if fdf.empty:
        st.warning("No data matches these filters.")
        st.stop()

    st.caption(f"Showing {len(fdf):,} of {len(df):,} records")

    # ---------------- الكروت ----------------
    total_sales = fdf["Sales"].sum()
    total_profit = fdf["Profit"].sum()
    margin = (total_profit / total_sales * 100) if total_sales else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Sales", f"{total_sales:,.2f}")
    c2.metric("Total Cost", f"{fdf['Cost'].sum():,.2f}")
    c3.metric("Total Profit", f"{total_profit:,.2f}")
    c4.metric("Total Quantity", f"{fdf['Quantity'].sum():,}")
    c5.metric("Profit Margin", f"{margin:.1f}%")

    # ---------------- الرسومات ----------------
    by_product = (
        fdf.groupby("Product")[["Sales", "Cost", "Profit", "Quantity"]]
        .sum()
        .sort_values(sort_by, ascending=False)
    )

    left, right = st.columns(2)
    left.subheader("Sales by Product")
    left.bar_chart(by_product["Sales"])
    right.subheader("Profit by Product")
    right.bar_chart(by_product["Profit"])

    # ---------------- ملخص المنتجات ----------------
    st.subheader("Product Summary")
    summary = by_product.copy()
    summary["Margin"] = (summary["Profit"] / summary["Sales"] * 100).fillna(0)
    st.dataframe(
        summary,
        column_config={"Margin": st.column_config.NumberColumn("Margin %", format="%.1f%%")},
    )

    # ---------------- التفاصيل ----------------
    st.subheader("Sales Details")
    st.dataframe(fdf)
    st.download_button(
        "⬇️ Download filtered data (CSV)",
        fdf.to_csv(index=False),
        "sales_filtered.csv",
        "text/csv",
    )

except Exception as e:
    st.error(f"Error loading data: {e}")