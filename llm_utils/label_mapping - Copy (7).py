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
            print("\U0001F4E9 Sending payload to GROQ API:")
            print(json.dumps(payload, indent=2))

            response = requests.post(url, headers=headers, json=payload)
            print("\U0001F4E9 GROQ raw response text:")
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

    if metadata_df is not None:
        try:
            if isinstance(metadata_df, (bytes, str)):
                from io import StringIO
                metadata_df = pd.read_csv(StringIO(metadata_df.decode("utf-8")), sep="|")
            metadata_df.columns = [col.strip().lower() for col in metadata_df.columns]
        except Exception as e:
            raise ValueError(f"❌ Failed to parse metadata CSV: {e}")

    for _, row in metadata_df.iterrows():
        table = row['table_name'].strip().upper()
        columns = [col.strip().upper() for col in str(row['column_list']).split(',')]
        for col in columns:
            metadata_lookup.add((table, col))
            table_column_map.setdefault(table, set()).add(col)

    user_entries = [
        {
            "extracted_label": label,
            "hint_table": user_table_map.get(label, ""),
            "hint_column": user_column_map.get(label, ""),
            "comment": user_comment_map.get(label, "")
        }
        for label in headers
    ]

    print("\U0001F9EA Sending user entries to GROQ (mapping with hints):")
    print(json.dumps(user_entries, indent=2))

    def query_llm_for_mappings(entries, context_note=""):
        system_prompt = (
            "You are an Oracle R12 expert. Using the label, hint_table, hint_column, and optional comment, find the correct Oracle R12 TABLE and COLUMN.\n"
            f"{context_note}\n"
            "Return ONLY a JSON array like this:\n"
            "[{\"extracted_label\": \"label1\", \"oracle_r12_table\": \"TABLE_NAME\", \"oracle_r12_column\": \"COLUMN_NAME\"}]"
        )

        response = safe_groq_chat_completion(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(entries, indent=2)}
            ]
        )

        content = response["choices"][0]["message"]["content"].strip()
        print("\U0001F4E8 Raw LLM Response:")
        print(content)

        try:
            content = re.sub(r"//.*", "", content)  # remove inline comments
            json_match = re.search(r"\[\s*{.*?}\s*\]", content, re.DOTALL)
            if not json_match:
                raise ValueError(f"❌ Couldn't extract a valid JSON array:\n\n{content}")
            clean_json = json_match.group(0)
            return json.loads(clean_json)
        except Exception as e:
            raise ValueError(f"❌ Failed to parse LLM mapping response:\n\n{content}\n\nError: {e}")

    llm_mappings = query_llm_for_mappings(user_entries)

    # First pass validation
    for item in llm_mappings:
        label = item.get("extracted_label", "")
        llm_table = item.get("oracle_r12_table", "").strip().upper()
        llm_column = item.get("oracle_r12_column", "").strip().upper()

        # Check original, _ALL, and _B variants and _tl variants
        variants = [llm_table, llm_table + "_ALL", llm_table + "_B", llm_table + "_TL"]
        found_match = False

        for variant in variants:
            if (variant, llm_column) in metadata_lookup:
                llm_table = variant
                found_match = True
                print(f"✅ Found Match: {llm_table}.{llm_column}")
                break

        if found_match:
            print(f"✅ Found Match: {llm_table}.{llm_column}")
            validated_mappings.append({
                "extracted_label": label,
                "oracle_r12_table": llm_table,
                "oracle_r12_column": llm_column
            })
        else:
            discarded_llm_items.append({
    "extracted_label": label,
    "oracle_r12_table": llm_table,
    "oracle_r12_column": llm_column,
    "hint_table": user_table_map.get(label, ""),
    "hint_column": user_column_map.get(label, ""),
    "comment": user_comment_map.get(label, "")
})

    # Retry for discarded items
    discarded_output = []
    if discarded_llm_items:
        print("🗃️ Discarded LLM mappings (unmatched):")
        for item in discarded_llm_items:
            discarded_output.append({
                "extracted_label": item.get("extracted_label", "NOT_PROVIDED"),
                "oracle_r12_table": item.get("oracle_r12_table", "LLM_NOT_PROVIDED"),
                "oracle_r12_column": item.get("oracle_r12_column", "LLM_NOT_PROVIDED")
            })
        print(json.dumps(discarded_output, indent=2))


    return validated_mappings, discarded_llm_items, table_column_map
