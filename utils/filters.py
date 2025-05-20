import re

EXCLUDED_PATTERNS = [
    re.compile(r"^Version$", re.IGNORECASE),
    re.compile(r"^Extractor Version$", re.IGNORECASE),
    re.compile(r"^ARU-dbdrv$", re.IGNORECASE),
    re.compile(r"^Template Code$", re.IGNORECASE),
    re.compile(r"^Template Type$", re.IGNORECASE),
    re.compile(r"^TYPE_EXCEL_TEMPLATE$", re.IGNORECASE),
    re.compile(r"^Preprocess XSLT File$", re.IGNORECASE),
    re.compile(r"^Last Modified Date$", re.IGNORECASE),
    re.compile(r"^Last Modified By$", re.IGNORECASE),
    re.compile(r"^Data Constraints:.*", re.IGNORECASE),
]

def is_excluded_line(line):
    for pattern in EXCLUDED_PATTERNS:
        if pattern.match(line.strip()):
            return True
    return False
