"""Build source or Windows source + offline dependency wheelhouse release."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--source-only', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / 'scripts/check_repository.py')], cwd=root, check=True)
if not args.source_only and (sys.platform != 'win32' or sys.version_info[:2] != (3, 13) or platform.machine().lower() not in {'amd64', 'x86_64'}):
    raise SystemExit('Dependency build requires Windows x64 Python 3.13.')
kind = 'source' if args.source_only else 'windows-py313-offline-dependencies'
out = root / 'dist'
out.mkdir(exist_ok=True)
stage = out / ('kesara-' + kind)
if stage.exists():
    raise SystemExit('Move the previous output before rebuilding: ' + str(stage))
stage.mkdir()
names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=root, text=True).splitlines()
for name in names:
    target = stage / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / name, target)
if not args.source_only:
    wheels = stage / 'wheelhouse'
    wheels.mkdir()
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--wheel-dir', str(wheels), '-r', str(root / 'requirements-lock.txt')], check=True)
    notices = stage / 'dependency-notices'
    notices.mkdir()
    for dist in importlib.metadata.distributions():
        for file in dist.files or []:
            if '.dist-info/' in str(file).replace('\\', '/') and ('license' in str(file).lower() or Path(file).name in {'METADATA', 'NOTICE', 'COPYING'}):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = notices / str(file)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
(stage / 'BUILD_INFO.json').write_text(json.dumps({'format': kind, 'python': sys.version, 'platform': platform.platform(), 'models_bundled': False, 'ollama_bundled': False}, indent=2), encoding='utf-8')
checks = []
for file in sorted(stage.rglob('*')):
    if file.is_file():
        with file.open('rb') as stream:
            checks.append(hashlib.file_digest(stream, 'sha256').hexdigest() + '  ' + file.relative_to(stage).as_posix())
(stage / 'SHA256SUMS.txt').write_text('\n'.join(checks) + '\n', encoding='utf-8')
archive = out / (stage.name + '.zip')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for file in stage.rglob('*'):
        if file.is_file():
            bundle.write(file, stage.name + '/' + file.relative_to(stage).as_posix())
print(archive)
