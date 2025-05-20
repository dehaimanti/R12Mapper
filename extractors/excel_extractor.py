import pandas as pd
import streamlit as st
from utils.filters import is_excluded_line

def extract_text_from_excel(uploaded_file):
    excel = pd.ExcelFile(uploaded_file, engine="xlrd")  # For .xls files
    sheet_names = [s for s in excel.sheet_names if s.lower() not in ["sheet1", "xdo_metadata"]]

    if not sheet_names:
        return None, None, "No usable sheets found in this Excel file."

    # unique key for selectbox
    selected_sheet = st.selectbox(
        "📑 Select Excel Sheet",
        sheet_names,
        key="sheet_selector"
    )

    df = pd.read_excel(excel, sheet_name=selected_sheet, header=None)
    df = df.fillna("").astype(str)

    st.write("📊 Excel Preview (first 40 rows):")
    st.dataframe(df.head(40))

    scanned_block = df.iloc[:100, :20]
    seen = set()
    ordered_lines = []

    for row in scanned_block.values.tolist():
        for cell in row:
            clean = cell.strip()
            if clean and not is_excluded_line(clean) and clean not in seen:
                seen.add(clean)
                ordered_lines.append(clean)

    text = "\n".join(ordered_lines)

    # unique key for text_area
    st.text_area(
        "📄 Filtered Excel Text for Header Extraction",
        text,
        height=300,
        key="excel_text_area"
    )

    return df, selected_sheet, text
