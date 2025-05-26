import json
import openai
from config import OPENAI_API_KEY
from typing import Union

openai.api_key = OPENAI_API_KEY

def generate_sql(mapping_data: Union[str, list]) -> str:
    """
    Generate a SQL SELECT query using OpenAI based on Oracle R12 label-column mappings.
    Works with either 'oracle_r12_table'/'oracle_r12_column' or 'table'/'column' keys.
    """
    try:
        # Safely parse JSON string if needed
        if isinstance(mapping_data, str):
            try:
                mappings = json.loads(mapping_data)
            except json.JSONDecodeError:
                return "-- Error: Provided string is not valid JSON."
        elif isinstance(mapping_data, list):
            mappings = mapping_data
        else:
            return "-- Error: mapping_data must be a JSON string or a list."

        if not mappings:
            return "-- No mappings provided."

        # Build the prompt
        prompt_lines = [
            "You are an Oracle SQL expert.",
            "Given the following field-to-database mappings, generate a SQL SELECT statement.",
            "",
            "Rules:",
            "- Include all columns in the SELECT clause, fully qualified with table aliases.",
            "- List all involved tables in the FROM clause (comma-separated, with aliases).",
            "- Write JOIN conditions in the WHERE clause based on *_ID or logical FK patterns.",
            "- Avoid CROSS JOINs.",
            "- Format SQL cleanly and clearly.",
            "- Output only the SQL — no explanations or comments.",
            "",
            "Mappings:"
        ]

        for item in mappings:
            label = item.get("extracted_label")
            table = item.get("oracle_r12_table") or item.get("table")
            column = item.get("oracle_r12_column") or item.get("column")
            if label and table and column:
                prompt_lines.append(f"- '{label}' → {table}.{column}")

        prompt = "\n".join(prompt_lines)

        # Send to OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        return response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"-- Error generating SQL: {e}"
