import json
import os
import ast
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

def safe_groq_chat_completion(model, messages, retries=3, delay=3):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer " + GROQ_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }

    for i in range(retries):
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"GROQ API Error {response.status_code}: {response.text}")

def generate_sql(validated_mappings, table_column_map=None):
    if not validated_mappings:
        return "-- No mappings to generate SQL."

    valid_items = [
        m for m in validated_mappings
        if m["oracle_r12_table"] != "NOT_FOUND" and m["oracle_r12_column"] != "NOT_FOUND"
    ]

    if not valid_items:
        return "-- No valid mappings found for SQL generation."

    description = []
    for item in valid_items:
        label = item["extracted_label"]
        table = item["oracle_r12_table"]
        column = item["oracle_r12_column"]
        description.append(f'"{label}" => {table}.{column}')

    user_prompt = (
        "You are an expert Oracle SQL developer. Based on the following mappings of labels to Oracle R12 tables and columns, "
        "generate a SELECT SQL query that includes smart JOINs, uses table aliases, and makes sure all selected fields are accurate.\n\n"
        "Mappings:\n" + "\n".join(description) +
        "\n\nOnly include the tables and columns listed. Do not guess. If a value is NULL, use NULL AS \"Label\".\n"
        "Respond ONLY with the SQL query — no explanation."
    )

    response = safe_groq_chat_completion(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a senior Oracle SQL expert."},
            {"role": "user", "content": user_prompt}
        ]
    )

    sql = response['choices'][0]['message']['content']
    return sql
