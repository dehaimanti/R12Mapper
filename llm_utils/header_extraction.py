import openai
import json
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def extract_headers_with_llm(text):
    system_prompt = """
You are a document analysis expert. Extract only a Python list of column headers from business documents.
Example: ["Account", "Account #", "Debit", "Credit"]
"""
    user_prompt = f"Document Text:\n{text.strip()[:5000]}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )
    try:
        return json.loads(response["choices"][0]["message"]["content"])
    except Exception:
        return []
