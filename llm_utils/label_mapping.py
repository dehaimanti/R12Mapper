import openai
import json
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def ask_llm_for_mappings(headers, user_table_map, user_column_map, user_comment_map, metadata_df=None):
    system_prompt = "You are an Oracle R12 expert. Map extracted labels to the most likely Oracle R12 table and column."

    metadata_mapping = {}
    if metadata_df is not None:
        # Print original column names
        print("📌 Original metadata_df columns:", metadata_df.columns.tolist())

        # Normalize column names
        metadata_df.columns = [col.strip().lower().replace('"', '') for col in metadata_df.columns]
        print("🧽 Normalized metadata_df columns:", metadata_df.columns.tolist())

        if 'table_name' in metadata_df.columns and 'column_list' in metadata_df.columns:
            print("✅ Using TABLE_NAME and COLUMN_LIST-based metadata parsing")
            for _, row in metadata_df.iterrows():
                table = str(row['table_name']).strip()
                columns = str(row['column_list']).split(',')
                for col in columns:
                    extracted_label = col.strip().lower()
                    metadata_mapping[extracted_label] = {
                        "table": table,
                        "column": col.strip()
                    }
        else:
            raise ValueError(f"❌ Metadata file must contain 'TABLE_NAME' and 'COLUMN_LIST' columns. Got: {metadata_df.columns.tolist()}")

    user_entries = []
    for label in headers:
        lower_label = label.lower()
        metadata_hint = metadata_mapping.get(lower_label, {})
        entry = {
            "extracted_label": label,
            "hint_table": user_table_map.get(label, "") or metadata_hint.get("table", ""),
            "hint_column": user_column_map.get(label, "") or metadata_hint.get("column", ""),
            "comment": user_comment_map.get(label, "")
        }
        user_entries.append(entry)

    user_prompt = f"Map these extracted labels to Oracle R12 tables and columns:\n{json.dumps(user_entries, indent=2)}"

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )

    return response['choices'][0]['message']['content']
