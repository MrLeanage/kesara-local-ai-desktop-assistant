"""Resolve project-inspection requests and collect bounded, safe source evidence.

Never infer an explicit path from the selected workspace. Project files are
untrusted input to the model, and private credentials are never sampled.
"""
import os
import ast
from pathlib import Path
import re

INSPECT=re.compile(r'\b(summar(?:y|ize|ise)|overview|explain|analy[sz]e|inspect|review|architecture|understand|what (?:is|does).*project|tell me about)\b',re.I)
WINDOWS_PATH=re.compile(r'[A-Za-z]:[\\/]')
SKIP_DIRS={'.git','.venv','venv','node_modules','__pycache__','.dart_tool','build','dist','target','.idea','.gradle','.next','coverage','speech-model','models','runtime','backups','vendor','third_party','third-party','site-packages','bower_components'}
SKIP_FILES={'.env','.env.local','.env.production','credentials.json','secrets.json','id_rsa','id_ed25519','approval-policy.json','model-settings.json','voice-settings.json','memory.json'}
READ_PRIORITY=('README.md','README.rst','README.txt','pyproject.toml','requirements.txt','pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','pubspec.yaml','package.json','Cargo.toml','go.mod','AGENTS.md','docs/ROADMAP.md','docs/SETUP.md','kesara.py','desktop.py','model_router.py','project_inspector.py','voice.py','parakeet_backend.py','turn_detection.py','approval_policy.py','history.py','interaction.py','companion.py','launch.py','tests/test_core_smoke.py')
CODE_SUFFIXES={'.py','.java','.kt','.dart','.ts','.tsx','.js','.jsx','.go','.rs','.md','.yaml','.yml','.toml'}
MAX_TOTAL=10500
MAX_FILE=2000

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
        if 'assets' in relative_dir.parts:
            continue
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

def _component_line(relative, source):
    """Extract a conservative description from inspected Python syntax."""
    try:
        tree=ast.parse(source)
    except (SyntaxError,ValueError):
        return None
    doc=ast.get_docstring(tree)
    classes=[node.name for node in tree.body if isinstance(node,ast.ClassDef)]
    functions=[node.name for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    imports=[]
    for node in tree.body:
        if isinstance(node,ast.Import):
            imports.extend(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module:
            imports.append(node.module.split('.')[0])
    role=doc.splitlines()[0].strip() if doc else ''
    if not role:
        role='Python module containing '+(', '.join(classes[:3]) if classes else ', '.join(functions[:3]))
    detail='; '.join(filter(None,[
        'classes: '+', '.join(classes[:5]) if classes else '',
        'functions: '+', '.join(functions[:6]) if functions else '',
        'imports: '+', '.join(dict.fromkeys(imports))[:130] if imports else ''
    ]))
    return (str(relative)+': '+role[:180]+(' ('+detail+')' if detail else ''))

def structured_report(snapshot):
    """Real code-level report even if a small LLM cannot produce a summary."""
    root=Path(snapshot['root'])
    filenames=snapshot['files']
    paths=set(p.replace('\\','/') for p in filenames)
    sources={}
    for candidate in filenames:
        path=root/candidate
        if not candidate.endswith('.py') or Path(candidate).name.startswith('test_'):
            continue
        if len(Path(candidate).parts)>2:
            continue
        try:
            if path.stat().st_size<140000:
                sources[candidate]=path.read_text(encoding='utf-8',errors='replace')
        except OSError:
            continue
    lines=['PROJECT ANALYSIS — '+str(root),'']
    readme=next((name for name in ('README.md','README.rst','README.txt') if name in paths),None)
    if readme:
        try:
            raw=(root/readme).read_text(encoding='utf-8',errors='replace')
            paragraphs=[line.strip() for line in raw.splitlines() if line.strip()
                        and not line.strip().startswith(('#','!','[','```','<','|','- '))]
            if paragraphs:
                lines.extend(['PROJECT PURPOSE (from '+readme+')', ' '.join(paragraphs[:3])[:600],''])
        except OSError:
            pass
    technologies=[]
    if 'requirements.txt' in paths or 'pyproject.toml' in paths:technologies.append('Python')
    if 'pom.xml' in paths:technologies.append('Java / Maven')
    if 'build.gradle' in paths or 'build.gradle.kts' in paths:technologies.append('Java/Kotlin / Gradle')
    if 'pubspec.yaml' in paths:technologies.append('Flutter / Dart')
    if 'package.json' in paths:technologies.append('JavaScript / Node.js')
    if any('tkinter' in raw for raw in sources.values()):technologies.append('Tkinter desktop interface')
    if any('urllib.request' in raw for raw in sources.values()):technologies.append('HTTP client')
    if any('sqlite3' in raw for raw in sources.values()):technologies.append('SQLite')
    if any('faster_whisper' in raw for raw in sources.values()):technologies.append('Whisper transcription')
    if any('sherpa_onnx' in raw for raw in sources.values()):technologies.append('Sherpa-ONNX speech recognition')
    lines.extend(['TECHNOLOGIES','; '.join(dict.fromkeys(technologies)) if technologies else 'Not established from the inspected sources.',''])
    preferred=list(READ_PRIORITY)
    ordered=sorted(sources,key=lambda name:(preferred.index(name) if name in preferred else 100,str(name)))
    lines.append('MAIN COMPONENTS (verified Python source)')
    if ordered:
        for name in ordered[:15]:
            detail=_component_line(name,sources[name])
            if detail:lines.append('• '+detail)
    else:
        lines.append('No readable Python modules were discovered.')
    lines.extend(['','ARCHITECTURE AND EXECUTION'])
    checks=[
        ('kesara.py','Agent core: model requests and permitted file or shell actions.'),
        ('model_router.py','Inference routing: local and configured cloud models.'),
        ('project_inspector.py','Read-only repository source inspection and reporting.'),
        ('desktop.py','Desktop UI: user chat, model controls, approvals and voice integration.'),
        ('voice.py','Speech pipeline: recognition and audio input/output.'),
        ('parakeet_backend.py','Alternative local speech-recognition backend.'),
        ('turn_detection.py','Voice activity turn boundaries.'),
        ('approval_policy.py','Project-scoped tool authorization policies.'),
        ('history.py','Conversation persistence.'),
        ('launch.py','Application entry point.')
    ]
    found=False
    for filename,description in checks:
        if filename in paths:
            lines.append('• '+filename+' — '+description);found=True
    if not found:lines.append('Architecture cannot be determined beyond the inspected modules.')
    lines.extend(['','LIMITATIONS','This report is derived from inspected files and Python syntax, not a runtime execution test.',
                  'An LLM-generated narrative may provide deeper analysis when a capable model is configured.'])
    return '\n'.join(lines)

def summary_fallback(snapshot):
    return structured_report(snapshot)
