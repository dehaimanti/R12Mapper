import time
import json
import requests
import re

def safe_groq_chat_completion(model, api_key, messages, retries=3, delay=3):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }

    for i in range(retries):
        try:
            print("📤 Sending payload to GROQ API...")
            response = requests.post(url, headers=headers, json=payload)
            print("📨 GROQ raw response:")
            print(response.text)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Attempt {i+1}: Error {response.status_code}")
                if i < retries - 1:
                    time.sleep(delay)
                else:
                    raise RuntimeError(f"GROQ API failed: {response.status_code} - {response.text}")
        except Exception as ex:
            print(f"❌ Exception: {ex}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"❌ Failed after {retries} retries: {ex}")

def generate_sql(mappings, groq_model, groq_api_key, table_column_map=None):
    prompt = (
        "You're an Oracle SQL expert. Generate a SELECT SQL statement using the following mappings.\n"
        "Each mapping includes the target table and column to select. Use proper aliases and joins if needed.\n"
        "If multiple tables are involved, assume foreign keys exist appropriately.\n\n"
        "Mappings:\n"
        f"{json.dumps(mappings, indent=2)}"
    )

    response = safe_groq_chat_completion(
        model=groq_model,
        api_key=groq_api_key,
        messages=[
            {"role": "system", "content": "You are a helpful Oracle SQL query generator."},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        content = response["choices"][0]["message"]["content"]
        sql_match = re.search(r"(?i)(select .*?;)", content, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        else:
            return content.strip()
    except Exception as e:
        raise ValueError(f"❌ Failed to parse SQL from LLM response: {e}\nRaw:\n{response}")
