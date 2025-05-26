# excel_generator.py
import pandas as pd

def generate_excel_template(validated_mappings, output_path):
    """
    Generate an Excel template with headers from validated mappings.
    Columns with NOT_FOUND are ignored.
    """
    valid_headers = [
        mapping["extracted_label"]
        for mapping in validated_mappings
        if mapping["oracle_r12_table"] != "NOT_FOUND" and mapping["oracle_r12_column"] != "NOT_FOUND"
    ]

    df = pd.DataFrame(columns=valid_headers)
    df.to_excel(output_path, index=False)
    return output_path