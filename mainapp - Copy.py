import streamlit as st
import pandas as pd
import io
import json
import tempfile
import os

from extractors.excel_extractor import extract_text_from_excel
from extractors.pdf_extractor import extract_text_from_pdf
from extractors.image_extractor import extract_text_from_image
from llm_utils.header_extraction import extract_headers_with_llm
from llm_utils.label_mapping import ask_llm_for_mappings
from llm_utils.sql_generator import generate_sql
from clean_metadata_csv import clean_and_load_metadata


st.title("Oracle R12 Label Mapper with GPT + SQL Generator")

st.sidebar.markdown("## Optional Configuration")
metadata_file = st.sidebar.file_uploader("Upload R12 Metadata CSV", type=["csv"])

r12_metadata_df = None
if metadata_file is not None:
    try:
        decoded = metadata_file.read()
        r12_metadata_df = clean_and_load_metadata(decoded)

        if 'table_name' not in r12_metadata_df.columns or 'column_list' not in r12_metadata_df.columns:
            raise ValueError(f"❌ Metadata must contain 'TABLE_NAME' and 'COLUMN_LIST'. Found: {r12_metadata_df.columns.tolist()}")

        st.sidebar.success("R12 Metadata loaded successfully!")
        st.sidebar.write("📋 Columns loaded:", r12_metadata_df.columns.tolist())
        st.sidebar.dataframe(r12_metadata_df.head())
    except Exception as e:
        st.sidebar.error(f"Failed to load metadata CSV: {e}")

uploaded_file = st.file_uploader("Upload a document (Excel, PDF, or Image)", type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    file_type = uploaded_file.name.split('.')[-1].lower()
    text = ""
    df = None

    if file_type in ["xlsx", "xls"]:
        df, selected_sheet, text = extract_text_from_excel(uploaded_file)
        if df is None:
            st.warning(text)
        else:
            st.selectbox("Select Excel Sheet", [selected_sheet])

    elif file_type == "pdf":
        text = extract_text_from_pdf(uploaded_file)

    elif file_type in ["png", "jpg", "jpeg"]:
        text = extract_text_from_image(uploaded_file)
        st.text_area("Extracted Text from Image", text)

    else:
        st.error("Unsupported file format.")

    if text:
        headers = extract_headers_with_llm(text)

        if headers:
            st.markdown("### ✍️ Provide Hints for Each Label")

            header_cols = st.columns([0.5, 2, 2, 2, 3])
            header_cols[0].markdown("**Sr no**")
            header_cols[1].markdown("**Label**")
            header_cols[2].markdown("**Hint R12 Table**")
            header_cols[3].markdown("**Hint R12 Column**")
            header_cols[4].markdown("**Comments**")

            user_table_map = {}
            user_column_map = {}
            user_comment_map = {}

            for idx, label in enumerate(headers):
                cols = st.columns([0.5, 2, 2, 2, 3])
                cols[0].write(str(idx + 1))
                cols[1].code(label, language="")
                user_table_map[label] = cols[2].text_input("Hint R12 Table", key=f"table_{idx}", label_visibility="collapsed")
                user_column_map[label] = cols[3].text_input("Hint R12 Column", key=f"column_{idx}", label_visibility="collapsed")
                user_comment_map[label] = cols[4].text_input("Comments", key=f"comment_{idx}", label_visibility="collapsed")

            if "trigger_mapping" not in st.session_state:
                st.session_state["trigger_mapping"] = False

            if st.button("Map Labels to Oracle R12", key="map_button"):
                st.session_state["trigger_mapping"] = True

            if st.session_state["trigger_mapping"]:
                with st.spinner("Querying LLM for mappings..."):
                    try:
                        mappings, discarded, table_column_map = ask_llm_for_mappings(
                            headers,
                            user_table_map,
                            user_column_map,
                            user_comment_map,
                            metadata_df=r12_metadata_df
                        )
                    except Exception as e:
                        st.error(f"🚨 Error during LLM mapping: {e}")
                        st.stop()

                    st.session_state["mappings"] = mappings

                    st.subheader("🔗 Mapped JSON")
                    st.code(json.dumps(mappings, indent=2), language="json")
                    st.subheader("🔗 Mapped Oracle R12 Table/Column Names")

                    if mappings:
                        for idx, entry in enumerate(mappings):
                            entry["Sr no"] = idx + 1

                        df_display = pd.DataFrame(mappings)[["Sr no", "extracted_label", "oracle_r12_table", "oracle_r12_column"]]
                        st.dataframe(df_display, use_container_width=True)

                        if discarded:
                            st.warning(f"⚠️ {len(discarded)} mapping(s) from LLM were discarded (not found in metadata).")
                            st.expander("See Discarded Mappings").json(discarded)
                    else:
                        st.warning("⚠️ No mapping data available.")

                    sql = generate_sql(mappings, table_column_map=table_column_map)
                    st.subheader("📾 Generated SQL Query")
                    st.code(sql, language="sql")
