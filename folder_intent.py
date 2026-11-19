"""Deterministic folder-creation intent for explicit, unambiguous destinations.

Only handles requests with both a concrete new folder name and an explicit
existing parent path. Ambiguous requests remain with the conversational agent.
"""
import os
import re
from pathlib import Path

FOLDER = re.compile(r'\b(?:create|make|add)\s+(?:a\s+|an\s+|new\s+)?(?:folder|directory)\s+(?:called|named)\s+["\']?([\w. -]{1,80}?)["\']?(?=\s+(?:inside|in|under|within|at)\b|\s*$)',re.I)
DRIVE = re.compile(r'[A-Za-z]:[\\/]')
BEFORE = re.compile(r'\b(?:create|make|add)\s+(?:a\s+|an\s+|new\s+)?(?:folder|directory)\b',re.I)

def explicit_mkdir_request(text):
    """Return (parent_path, folder_name), or None. Never invent a destination."""
    match = FOLDER.search(text)
    if not match:
        return None
    folder = match.group(1).strip(' ."\'')
    if folder in ('','.','..') or any(x in folder for x in ('/','\\',':')) or folder.endswith('.'):
        return None
    # Prefer a quoted absolute parent; it supports spaces in names reliably.
    quoted = re.findall(r'["\']([A-Za-z]:[\\/][^"\']+|/[^"\']+)["\']',text)
    if len(quoted)==1:
        parent = quoted[0].strip()
    elif len(quoted)>1:
        return None
    else:
        # A path supplied before "create a folder ..." is unambiguous.
        prefix=text[:BEFORE.search(text).start()].strip(' ,:.;')
        if DRIVE.match(prefix) or prefix.startswith('/'):
            parent=prefix
        else:
            tail=text[match.end():]
            following=re.match(r'\s+(?:inside|in|under|within|at)\s+(?:the\s+)?(?:directory|folder|path)?\s*(.*)',tail,re.I|re.S)
            if not following:
                return None
            parent=following.group(1).strip(' .\r\n\t')
            # Accept only a trailing absolute path, never inferred locations.
            if not (DRIVE.match(parent) or parent.startswith('/')):
                return None
    if os.name=='nt':
        if not DRIVE.match(parent) and not Path(parent).is_absolute():
            return None
    else:
        if DRIVE.match(parent) or not Path(parent).is_absolute():
            return None
    return parent,folder

def target_for_request(text):
    parsed=explicit_mkdir_request(text)
    if parsed is None:return None
    parent,folder=parsed
    root=Path(parent).expanduser().resolve()
    target=(root/folder).resolve()
    if target.parent!=root:
        return None
    return target
