import streamlit as st
import pandas as pd
import io
import json
import tempfile
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
import requests

from extractors.excel_extractor import extract_text_from_excel
from extractors.pdf_extractor import extract_text_from_pdf
from extractors.image_extractor import extract_text_from_image
from llm_utils.header_extraction import extract_headers_with_llm
from llm_utils.label_mapping import ask_llm_for_mappings
from llm_utils.sql_generator import generate_sql
from clean_metadata_csv import clean_and_load_metadata

# Load existing .env file
dotenv_path = Path('.env')
load_dotenv(dotenv_path)

def clean_text(text):
    lines = text.split("\n")
    useful = [line.strip() for line in lines if any(
        keyword in line.lower()
        for keyword in ["date", "number", "buyer", "amount", "price", "quantity", "part", "tax"]
    ) and len(line.strip()) > 0]
    return "\n".join(useful)

st.sidebar.markdown("## GROQ Configuration")
st.sidebar.info('🔑 Don\'t have a GROQ API key? [Click here to create one](https://console.groq.com/keys)', icon="🔗")

groq_model = st.sidebar.selectbox("Select GROQ Model", ["llama3-70b-8192","gemma-7b-it", "mixtral-8x7b-32768"])
groq_api_key = st.sidebar.text_input("Enter GROQ API Key", type="password")
if not groq_model or not groq_api_key:
    st.error("🚨 Please provide GROQ Model and API Key to continue.")
    st.stop()

if groq_model and groq_api_key:
    set_key(dotenv_path, "GROQ_MODEL", groq_model)
    set_key(dotenv_path, "GROQ_API_KEY", groq_api_key)
    st.sidebar.success("GROQ model and API key saved to .env")

st.title("Oracle R12 Label Mapper with GPT + SQL Generator")

st.sidebar.markdown("## R12 Metadata Auto-Loader")

metadata_dir = Path("metadata")
metadata_files = list(metadata_dir.glob("*.csv"))

r12_metadata_df = pd.DataFrame()
if metadata_files:
    for file in metadata_files:
        try:
            with open(file, "rb") as f:
                file_data = f.read()
                temp_df = clean_and_load_metadata(file_data)
                r12_metadata_df = pd.concat([r12_metadata_df, temp_df], ignore_index=True)
        except Exception as e:
            st.sidebar.error(f"❌ Error loading {file.name}: {e}")

    if not r12_metadata_df.empty:
        st.sidebar.success(f"✅ Loaded {len(metadata_files)} metadata file(s) from /metadata/")
        st.sidebar.write("📋 Columns loaded:", r12_metadata_df.columns.tolist())
        st.sidebar.dataframe(r12_metadata_df.head())
    else:
        st.sidebar.warning("⚠️ No usable metadata found in /metadata/")
else:
    st.sidebar.warning("⚠️ No metadata CSV files found in /metadata/")


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
        raw_text = extract_text_from_pdf(uploaded_file)
        text = clean_text(raw_text)
        st.expander("📄 Raw Extracted PDF Text").code(raw_text)

    elif file_type in ["png", "jpg", "jpeg"]:
        text = extract_text_from_image(uploaded_file)
        st.text_area("Extracted Text from Image", text)

    else:
        st.error("Unsupported file format.")

    if text:
        headers = extract_headers_with_llm(text)
        if not headers:
            headers = [
                "Purchase Order Number", "Buyer", "Approved Date",
                "Delivery Date", "Quantity", "Unit Price", "Tax Amount", "Total Amount"
            ]
            st.warning("⚠️ No labels extracted from document. Using default PO-style fallback labels.")

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
                except requests.exceptions.HTTPError as http_err:
                    if http_err.response.status_code == 429:
                        retry_after = http_err.response.headers.get("Retry-After", "a few")
                        st.error(f"🚨 You have exceeded your token limit. Try again after {retry_after} seconds.")
                    else:
                        st.error(f"🚨 HTTP error occurred: {http_err}")
                    st.stop()
                except Exception as e:
                    st.error(f"🚨 Unexpected error during LLM mapping: {e}")
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
