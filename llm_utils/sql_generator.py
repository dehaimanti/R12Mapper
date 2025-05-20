import json
import openai  # Or your LLM wrapper

def generate_sql(mapping_json):
    try:
        mappings = json.loads(mapping_json)

        # Prepare natural-language input for the LLM
        prompt = "Generate a SQL SELECT query using the following table and column mappings:\n\n"
        for item in mappings:
            label = item.get("extracted_label", "")
            table = item.get("mapped_table", "")
            column = item.get("mapped_column", "")
            prompt += f"- '{label}' is mapped to {table}.{column}\n"

        prompt += "\nAssume proper JOINs between tables if needed. Use standard SQL syntax."

        # Call the LLM (replace with your own call method if needed)
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        sql = response['choices'][0]['message']['content'].strip()
        return sql

    except Exception as e:
        return f"-- Error generating SQL: {e}"
