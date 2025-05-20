import pandas as pd
import re
import io

def clean_and_load_metadata(file_contents):
    """
    Loads and parses a metadata CSV file with format:
    TABLE_NAME|COLUMN_LIST
    ADOP_VALID_NODES|CONTEXT_NAME, NODE_NAME#1, ...
    
    Returns a cleaned pandas DataFrame with columns: 'table_name', 'column_list'
    """
    # Decode bytes to string
    decoded_str = file_contents.decode("utf-8")

    # Use pandas to read the pipe-delimited format
    df = pd.read_csv(io.StringIO(decoded_str), sep="|", engine="python")

    # Normalize column names
    df.columns = [col.strip().lower() for col in df.columns]

    # Rename if necessary to match expected format
    df.rename(columns={"table_name": "table_name", "column_list": "column_list"}, inplace=True)

    return df