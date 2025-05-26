import json
import openai
from openai.error import ServiceUnavailableError
from config import OPENAI_API_KEY
import ast
import time

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

def generate_sql(validated_mappings, table_column_map=None):
    if not validated_mappings:
        return "-- No mappings to generate SQL."

    # Filter out invalid mappings
    valid_items = [
        m for m in validated_mappings 
        if m["oracle_r12_table"] != "NOT_FOUND" and m["oracle_r12_column"] != "NOT_FOUND"
    ]

    if not valid_items:
        return "-- No valid mappings found for SQL generation."

    # Step 1: Build prompt
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

    # Step 2: Call LLM
    response = safe_chat_completion_create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a senior Oracle SQL expert."},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )

    # Step 3: Return generated SQL
    sql = response['choices'][0]['message']['content']
    return sql
