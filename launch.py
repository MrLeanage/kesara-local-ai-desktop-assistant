"""Start the private, local-only model server and Kesara."""
import os
from pathlib import Path
import subprocess
import time
import urllib.request

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
os.environ['OLLAMA_HOST'] = '127.0.0.1:11434'
os.environ['OLLAMA_MODELS'] = str(BASE / 'models')
os.environ['OLLAMA_NO_CLOUD'] = '1'
os.environ['OLLAMA_NUM_PARALLEL'] = '1'

def alive():
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=2) as r:
            return r.status == 200
    except Exception: return False

if not alive():
    exe = BASE / 'runtime' / 'ollama.exe'
    if not exe.exists(): raise SystemExit('Ollama runtime is missing. Setup has not completed.')
    with (BASE/'server.log').open('a') as log:
        subprocess.Popen([str(exe),'serve'],env=os.environ,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        if alive(): break
        time.sleep(0.5)
    else: raise SystemExit('Model server did not start. Check server.log.')

if '--cli' in __import__('sys').argv:
    from kesara import main
else:
    from desktop import main
if __name__=='__main__':main()
