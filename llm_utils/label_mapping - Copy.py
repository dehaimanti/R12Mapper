import time
import os
import json
import ast
import pandas as pd
import requests
import re
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

def safe_groq_chat_completion(model, messages, retries=3, delay=3):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }

    for i in range(retries):
        try:
            print("📩 Sending payload to GROQ API:")
            print(json.dumps(payload, indent=2))

            response = requests.post(url, headers=headers, json=payload)

            print("📩 GROQ raw response text:")
            print(response.text)

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception as e:
                    raise ValueError(f"✅ Status 200 but failed to parse JSON: {e}\nRaw: {response.text}")
            else:
                print(f"❌ Attempt {i+1}: GROQ error {response.status_code}: {response.text}")
                if i < retries - 1:
                    time.sleep(delay)
                else:
                    raise RuntimeError(f"GROQ API failed: {response.status_code} - {response.text}")
        except Exception as ex:
            print(f"🚨 Exception during GROQ call: {ex}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"❌ GROQ API call failed after {retries} retries: {ex}")

def ask_llm_for_mappings(headers, user_table_map, user_column_map, user_comment_map, metadata_df=None):
    validated_mappings = []
    discarded_llm_items = []
    metadata_lookup = set()
    table_column_map = {}

    print("🧪 Extracted headers:", headers)
    if not headers:
        raise ValueError("❌ No headers extracted. Nothing to map.")

    if metadata_df is not None:
        try:
            if isinstance(metadata_df, (bytes, str)):
                from io import StringIO
                metadata_df = pd.read_csv(StringIO(metadata_df.decode("utf-8")), sep="|")
            metadata_df.columns = [col.strip().lower() for col in metadata_df.columns]
        except Exception as e:
            raise ValueError(f"❌ Failed to parse metadata CSV: {e}")

    user_entries = [
        {
            "extracted_label": label,
            "hint_table": user_table_map.get(label, ""),
            "hint_column": user_column_map.get(label, ""),
            "comment": user_comment_map.get(label, "")
        }
        for label in headers
    ]

    print("🧪 Sending user entries to GROQ (table guessing):")
    print(json.dumps(user_entries, indent=2))

    # STEP 1: Ask LLM for likely R12 table names
    system_prompt_step1 = (
        "You are an Oracle R12 expert. For each label, guess the most likely Oracle R12 TABLE name "
        "based on label text and hints. Do NOT guess columns. Format:\n"
        "[{\"extracted_label\": \"label1\", \"oracle_r12_table\": \"TABLE_NAME\"}]"
    )

    response1 = safe_groq_chat_completion(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt_step1},
            {"role": "user", "content": f"Labels and hints:\n{json.dumps(user_entries, indent=2)}"}
        ]
    )

    content1 = response1["choices"][0]["message"]["content"].strip()
    print("📨 Raw LLM Response (table guessing):")
    print(content1)

    if not content1:
        raise ValueError("❌ First LLM response (table guess) was empty.")

    try:
        json_match = re.search(r"\[\s*{.*?}\s*\]", content1, re.DOTALL)
        if not json_match:
            raise ValueError(f"❌ Couldn't extract a JSON array from LLM response:\n\n{content1}")
        cleaned_json = json_match.group(0)
        guessed_table_mappings = json.loads(cleaned_json)
    except Exception as e:
        raise ValueError(f"❌ Failed to parse table guesses:\n\n{content1}\n\nError: {e}")

    guessed_tables = {entry["oracle_r12_table"].strip().upper() for entry in guessed_table_mappings if entry.get("oracle_r12_table")}

    filtered_metadata = metadata_df[
        metadata_df['table_name'].str.upper().isin(guessed_tables)
    ] if metadata_df is not None else None

    if filtered_metadata is not None:
        for _, row in filtered_metadata.iterrows():
            table = row['table_name'].strip().upper()
            columns = [col.strip().upper() for col in str(row['column_list']).split(',')]
            for col in columns:
                metadata_lookup.add((table, col))
                table_column_map.setdefault(table, set()).add(col)

    metadata_map = {tbl: list(cols) for tbl, cols in table_column_map.items()}

    # STEP 2: Ask LLM for full mapping now with metadata
    system_prompt_step2 = (
        "You are an Oracle R12 expert. Using the metadata and hints, map each label to the correct Oracle R12 TABLE and COLUMN.\n"
        "Only use from these tables and columns:\n"
        f"{json.dumps(metadata_map, indent=2)}\n\n"
        "Return ONLY a JSON array like this:\n"
        "[{\"extracted_label\": \"label1\", \"oracle_r12_table\": \"TABLE_NAME\", \"oracle_r12_column\": \"COLUMN_NAME\"}]"
    )

    response2 = safe_groq_chat_completion(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt_step2},
            {"role": "user", "content": json.dumps(user_entries, indent=2)}
        ]
    )

    raw_content = response2["choices"][0]["message"]["content"].strip()
    print("📨 Raw LLM Response (final mapping):")
    print(raw_content)

    if not raw_content:
        raise ValueError("❌ Final LLM mapping response was empty.")

    try:
        json_match = re.search(r"\[\s*{.*?}\s*\]", raw_content, re.DOTALL)
        if not json_match:
            raise ValueError(f"❌ Couldn't extract a valid JSON array:\n\n{raw_content}")
        clean_json = json_match.group(0)
        llm_mappings = json.loads(clean_json)
    except Exception as e:
        raise ValueError(f"❌ Failed to parse final LLM mapping response:\n\n{raw_content}\n\nError: {e}")

    for item in llm_mappings:
        label = item.get("extracted_label", "")
        llm_table = item.get("oracle_r12_table", "").strip().upper()
        llm_column = item.get("oracle_r12_column", "").strip().upper()

        # 🔍 Smart match: exact or try _ALL
        found_match = (llm_table, llm_column) in metadata_lookup

        if not found_match:
            alt_table = llm_table + "_ALL"
            if (alt_table, llm_column) in metadata_lookup:
                print(f"⚠️ Table '{llm_table}' not found, but found fallback '{alt_table}'.")
                llm_table = alt_table
                found_match = True

        if found_match:
            validated_mappings.append({
                "extracted_label": label,
                "oracle_r12_table": llm_table,
                "oracle_r12_column": llm_column
            })
        else:
            validated_mappings.append({
                "extracted_label": label,
                "oracle_r12_table": "NOT_FOUND",
                "oracle_r12_column": "NOT_FOUND"
            })
            discarded_llm_items.append(item)

    return validated_mappings, discarded_llm_items, table_column_map
