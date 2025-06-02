import json
import requests

def extract_headers_with_llm(text, groq_model, groq_api_key):
    system_prompt = """
You are a document analysis expert. Given a snippet of a business document, extract only a Python list of column headers or labels. 
Only return valid Python list syntax. No explanations.

Example Input:
Account Number
Account Name
Debit
Credit

Example Output:
["Account Number", "Account Name", "Debit", "Credit"]

If the input contains only headers, return them all. If no headers are detected, return an empty list.
"""
    user_prompt = f"Document Text:\n{text.strip()[:5000]}"

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        result = response.json()
        return json.loads(result["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"❌ Error contacting GROQ API: {e}")
        return []
