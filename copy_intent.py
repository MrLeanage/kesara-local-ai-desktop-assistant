"""Safe folder copy intent: accept only explicitly supplied absolute paths."""
import os
from pathlib import Path
import re
from folder_intent import DRIVE

QUOTED_ABSOLUTE=re.compile(r'["\']([A-Za-z]:[\\/][^"\']+|/[^"\']+)["\']')
COPY_INTENT=re.compile(r'\bcopy\b.*\b(?:to|into)\b',re.I|re.S)

def request_paths(prompt):
    if not COPY_INTENT.search(prompt):
        return None
    matches=QUOTED_ABSOLUTE.findall(prompt)
    if len(matches)!=2:
        return None
    source,destination=matches
    if os.name!='nt' and (DRIVE.match(source) or DRIVE.match(destination)):
        return None
    return Path(source).expanduser().resolve(),Path(destination).expanduser().resolve()

def is_copy_request(prompt):
    return bool(re.search(r'\b(?:copy|clone|duplicate)\b',prompt,re.I) and
                re.search(r'\b(?:folder|directory|contents?|files?|project|repo|repository)\b',prompt,re.I))
