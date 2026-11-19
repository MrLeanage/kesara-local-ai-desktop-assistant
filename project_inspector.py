"""Resolve project-inspection requests and collect bounded, safe source evidence.

Never infer an explicit path from the selected workspace. Project files are
untrusted input to the model, and private credentials are never sampled.
"""
import os
from pathlib import Path
import re

INSPECT=re.compile(r'\b(summar(?:y|ize|ise)|overview|explain|analy[sz]e|inspect|review|architecture|understand|what (?:is|does).*project|tell me about)\b',re.I)
WINDOWS_PATH=re.compile(r'[A-Za-z]:[\\/]')
SKIP_DIRS={'.git','.venv','venv','node_modules','__pycache__','.dart_tool','build','dist','target','.idea','.gradle','.next','coverage','speech-model','models','runtime','backups'}
SKIP_FILES={'.env','.env.local','.env.production','credentials.json','secrets.json','id_rsa','id_ed25519','approval-policy.json','model-settings.json','voice-settings.json','memory.json'}
READ_PRIORITY=('README.md','README.rst','README.txt','pyproject.toml','requirements.txt','pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','pubspec.yaml','package.json','Cargo.toml','go.mod','AGENTS.md','docs/ROADMAP.md','docs/SETUP.md')
CODE_SUFFIXES={'.py','.java','.kt','.dart','.ts','.tsx','.js','.jsx','.go','.rs','.md','.yaml','.yml','.toml'}
MAX_TOTAL=19000
MAX_FILE=3800

def explicitly_requested_project(prompt):
    """Find the longest existing explicit absolute directory in prose."""
    if not INSPECT.search(prompt):
        return None
    quoted=re.findall(r'["\']([A-Za-z]:[\\/][^"\']+|/[^"\']+)["\']',prompt)
    if len(quoted)==1:
        path=Path(quoted[0]).expanduser()
        return path.resolve() if path.is_dir() else None
    if len(quoted)>1:
        return None
    candidates=[]
    for match in WINDOWS_PATH.finditer(prompt):
        if os.name!='nt':
            continue
        suffix=prompt[match.start():].replace('\n',' ')
        # Paths may contain spaces. Trim words from the right until a real
        # directory exists, rather than guessing a short workspace-relative path.
        for end in range(len(suffix),2,-1):
            trial=suffix[:end].rstrip(' ,:;.!?\\/\r\t')
            path=Path(trial)
            if path.is_dir():
                candidates.append(path.resolve())
                break
    if os.name!='nt':
        for item in re.findall(r'(?<!\w)/[^\n"\']+',prompt):
            for end in range(len(item),1,-1):
                path=Path(item[:end].rstrip(' ,:;.!?'))
                if path.is_dir():
                    candidates.append(path.resolve())
                    break
    return candidates[0] if len(candidates)==1 else None

def inspect_project(root):
    root=Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError('Project directory does not exist: '+str(root))
    files=[]
    # Prune large/generated folders BEFORE traversing them.
    for current,dirs,filenames in os.walk(root,followlinks=False):
        relative_dir=Path(current).relative_to(root)
        depth=len(relative_dir.parts) if relative_dir!=Path('.') else 0
        dirs[:]=[name for name in dirs if name not in SKIP_DIRS
                 and not (Path(current)/name).is_symlink() and depth<6]
        for name in filenames:
            if name in SKIP_FILES or name.startswith('.env'):
                continue
            path=Path(current)/name
            relative=path.relative_to(root)
            if path.is_symlink():
                continue
            if path.suffix.lower() not in CODE_SUFFIXES and name not in READ_PRIORITY:
                continue
            files.append(relative)
            if len(files)>=250:break
        if len(files)>=250:break
    names={str(path).replace('\\','/') for path in files}
    ordered=[]
    for important in READ_PRIORITY:
        if important in names: ordered.append(Path(important))
    for item in sorted(files,key=lambda p:(len(p.parts),str(p).lower())):
        if item not in ordered:ordered.append(item)
    samples=[]
    used=0
    for relative in ordered:
        if used>=MAX_TOTAL:break
        path=root/relative
        try:
            if path.stat().st_size>120000:continue
            raw=path.read_text(encoding='utf-8',errors='replace')
        except (OSError,UnicodeError):
            continue
        excerpt=raw[:min(MAX_FILE,MAX_TOTAL-used)]
        if not excerpt.strip():continue
        samples.append('FILE '+str(relative)+'\n'+excerpt)
        used+=len(excerpt)
        if len(samples)>=18:break
    return {'root':str(root),'files':[str(x) for x in files],
            'sampled':samples,'evidence':'\n\n'.join(samples)}

def summary_fallback(snapshot):
    names=snapshot['files']
    root=snapshot['root']
    indicators=[]
    for filename,description in [('pom.xml','Maven/Java'),('build.gradle','Gradle/Java'),
                                  ('pubspec.yaml','Flutter/Dart'),('package.json','Node.js/JavaScript'),
                                  ('pyproject.toml','Python'),('requirements.txt','Python')]:
        if filename in names:indicators.append(description)
    text='Project: '+root+'\n'
    text+='Detected technologies from manifests: '+(', '.join(indicators) if indicators else 'not established')+'\n'
    text+='Inspected '+str(len(names))+' candidate source/documentation files.\n'
    text+='Key files: '+', '.join(names[:22])
    text+='\nThis is an evidence inventory, not a complete architecture analysis.'
    return text
