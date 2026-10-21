"""Check common private files, runtime exclusions and Git blob sizes."""
from pathlib import Path
import argparse
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--runtime', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=root, text=True).splitlines()
blocked = {'memory.json', 'voice-settings.json', 'runtime-state.json', '.env', 'avatarsdk.glb', 'mpfb.glb'}
errors = []
for name in names:
    path = Path(name)
    if path.name in blocked or path.suffix in {'.log', '.jsonl'} or path.parts[0] in {'.venv', 'models', 'runtime', 'speech-model', 'projects', 'dist'}:
        errors.append('Private/runtime file: ' + name)
    if (root / path).stat().st_size > 95 * 1024 * 1024:
        errors.append('Oversized Git file: ' + name)
if args.runtime:
    for name in ['runtime/ollama.exe', 'speech-model/whisper-small.en/model.bin', 'speech-model/whisper-small.en/config.json', 'speech-model/whisper-small.en/tokenizer.json', 'speech-model/whisper-small.en/vocabulary.txt', 'speech-model/vosk-model-small-en-us-0.15/am/final.mdl', 'assets/robot-animations.zip', 'assets/hand_landmarker.task']:
        if not (root / name).is_file():
            errors.append('Missing runtime prerequisite: ' + name)
print('\n'.join(errors) if errors else 'Repository checks passed.')
sys.exit(bool(errors))
