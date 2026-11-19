"""Safety rules for speech-recognized commands.

A noisy transcript is untrusted input. Actions that might change files,
execute commands, or use a spoken path require human transcript verification
even when ordinary conversation uses automatic sending.
"""
import re

_CHANGE_VERBS = re.compile(
    r"\b(create|make|mkdir|delete|remove|erase|rename|move|copy|paste|"
    r"write|overwrite|edit|modify|change|update|install|uninstall|"
    r"execute|run|launch|start|stop|commit|push|pull|deploy|publish|"
    r"build|generate|fix|refactor|implement|add|replace|setup|set up)\b",
    re.IGNORECASE,
)
_TARGETS = re.compile(
    r"\b(file|folder|directory|project|repo|repository|branch|"
    r"code|source|script|command|terminal|powershell|git|package|"
    r"module|test|application|app|database|path|drive|service)\b",
    re.IGNORECASE,
)
_PATHS = re.compile(r"(?:[A-Za-z]:[\\/]|(?:^|\s)[./~][\\/])")

def requires_voice_review(transcript):
    """True for likely consequential computer actions, never for simple chat."""
    if not transcript or not transcript.strip():
        return False
    return bool(_PATHS.search(transcript) or
                (_CHANGE_VERBS.search(transcript) and _TARGETS.search(transcript)))
