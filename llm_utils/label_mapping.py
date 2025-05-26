import time
import openai
from openai.error import ServiceUnavailableError
import json
import ast
import pandas as pd
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def safe_chat_completion_create(*args, retries=3, delay=3, **kwargs):
    for i in range(retries):
        try:
            return openai.ChatCompletion.create(*args, **kwargs)
        except ServiceUnavailableError as e:
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise e

def ask_llm_for_mappings(headers, user_table_map, user_column_map, user_comment_map, metadata_df=None):
    validated_mappings = []
    discarded_llm_items = []
    metadata_lookup = set()
    table_column_map = {}  # For dynamic join logic

    # ✅ Step 1: Load and parse metadata CSV with pipe delimiter
    if metadata_df is not None:
        try:
            if isinstance(metadata_df, (bytes, str)):
                from io import StringIO
                metadata_df = pd.read_csv(StringIO(metadata_df.decode("utf-8")), sep="|")

            metadata_df.columns = [col.strip().lower() for col in metadata_df.columns]
        except Exception as e:
            raise ValueError(f"❌ Failed to parse metadata CSV: {e}")

        if 'table_name' in metadata_df.columns and 'column_list' in metadata_df.columns:
            for _, row in metadata_df.iterrows():
                table = row['table_name'].strip().upper()
                columns = [col.strip().upper() for col in str(row['column_list']).split(',')]
                for col in columns:
                    metadata_lookup.add((table, col))
                    table_column_map.setdefault(table, set()).add(col)

    # ✅ Step 2: Ask LLM to suggest mappings
    user_entries = []
    for label in headers:
        entry = {
            "extracted_label": label,
            "hint_table": user_table_map.get(label, ""),
            "hint_column": user_column_map.get(label, ""),
            "comment": user_comment_map.get(label, "")
        }
        user_entries.append(entry)

    system_prompt = (
        "You are an Oracle R12 expert. Map the extracted labels to the most likely Oracle R12 table and column.\n"
        "Use the provided hints to help guide your selection.\n"
        "Respond ONLY with a JSON array of objects in this format:\n"
        "[{\"extracted_label\": \"label1\", \"oracle_r12_table\": \"TABLE_NAME\", \"oracle_r12_column\": \"COLUMN_NAME\"}]\n"
        "Do not add any explanations or extra text."
    )

    user_prompt = f"Here are the labels and hints:\n{json.dumps(user_entries, indent=2)}"

    response = safe_chat_completion_create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )

    raw_response = response['choices'][0]['message']['content']

    try:
        llm_mappings = json.loads(raw_response)
    except json.JSONDecodeError:
        try:
            llm_mappings = ast.literal_eval(raw_response)
        except Exception as e:
            raise ValueError(f"❌ Failed to parse LLM response: {e}")

    # ✅ Step 3: Validate mappings
    for item in llm_mappings:
        label = item.get("extracted_label", "")
        llm_table = item.get("oracle_r12_table", "").strip().upper()
        llm_column = item.get("oracle_r12_column", "").strip().upper()

        hint_table = user_table_map.get(label, "").strip().upper()
        hint_column = user_column_map.get(label, "").strip().upper()

        # Validate user hint
        if hint_table and hint_column and (hint_table, hint_column) in metadata_lookup:
            validated_mappings.append({
                "extracted_label": label,
                "oracle_r12_table": hint_table,
                "oracle_r12_column": hint_column
            })
            continue

        # Validate LLM suggestion
        if llm_table and llm_column and (llm_table, llm_column) in metadata_lookup:
            validated_mappings.append({
                "extracted_label": label,
                "oracle_r12_table": llm_table,
                "oracle_r12_column": llm_column
            })
            continue

        # If nothing works
        validated_mappings.append({
            "extracted_label": label,
            "oracle_r12_table": "NOT_FOUND",
            "oracle_r12_column": "NOT_FOUND"
        })
        discarded_llm_items.append(item)

    # ✅ Return extra info to help auto-generate JOINs later
    return validated_mappings, discarded_llm_items, table_column_map
