# Build and dependency bundling

The build format is a Windows **source + offline Python wheelhouse ZIP**, not a standalone EXE. Destination machines need Python 3.13 x64 with Tcl/Tk, PowerShell/.NET and the external model/Ollama files in SETUP.md. Virtual environments are not copied because they contain machine-specific paths.

```powershell
.\.venv\Scripts\python.exe scripts/build_release.py
```

This builds/downloads wheels for every pinned dependency, packages source/assets, copies installed dependency license metadata, and writes SHA256 checksums. Failure to build a wheel stops packaging. Output is in dist and is excluded from Git. Python dependencies are included only in this full build; models and Ollama are not.

For a small source-only archive:

```powershell
.\.venv\Scripts\python.exe scripts/build_release.py --source-only
```

On a matching Windows/Python machine, extract a dependency-bundled release and install without reaching PyPI:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

Then install external runtime/model files and launch. Wheels target the build OS/Python/architecture. Test microphone, recognition, speech, avatar, camera opt-in and approval accept/decline before distributing. Initial pip wheel creation needs internet/compiler support where an upstream wheel is unavailable. License metadata is collected from the build environment; upstream licenses still govern redistribution.

## GitHub later

A local Git repository is initialized on main. Review `git status` and `git diff --cached`, configure your Git identity, and make your first commit. Create an empty GitHub repository, then add its remote and push with GitHub Desktop or Git. This preparation does not sign in, create a remote or upload anything. Choose an original-source license deliberately.

Keep dependency archives in GitHub Releases rather than Git history, observing the service's applicable size limits. The clean source ZIP is also available for manual upload; extract it first.
