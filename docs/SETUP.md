# Runtime setup and configuration

All paths are relative to the repository root. You can copy these external resources from your existing working installation. Do not commit them.

1. Obtain the official Windows standalone [Ollama distribution](https://github.com/ollama/ollama/releases). Extract all runtime files and supporting libraries into `runtime/`, with `runtime/ollama.exe` present.
2. Start the dedicated server in PowerShell:

```powershell
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MODELS=Join-Path $PWD 'models'
$env:OLLAMA_NO_CLOUD='1'
$env:OLLAMA_NUM_PARALLEL='1'
.\runtime\ollama.exe serve
```

In a second PowerShell in this repository:

```powershell
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MODELS=Join-Path $PWD 'models'
.\runtime\ollama.exe pull qwen2.5-coder:3b
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small.en', local_dir='speech-model/whisper-small.en')"
```

3. Download [Vosk small English 0.15](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip). Extract into `speech-model/vosk-model-small-en-us-0.15/`, without a duplicate nested folder.
4. The hand landmarker and robot atlas are included in assets. Start Kesara after the files are ready.

If another Ollama instance owns port 11434, Kesara reuses it. Ensure that server has the selected model; its storage path is determined by its own environment. Otherwise stop that server and allow Kesara to start its private server. The launcher changes model storage only for a server it starts.

## Configuration

- `KESARA_MODEL`: environment variable, default `qwen2.5-coder:3b`.
- `KESARA_THREADS`: environment variable, default `4`.
- Launcher sets localhost port 11434, cloud off, parallelism one. Coding context 8192, output limit 2048 and keep-alive one hour are source constants.
- Whisper uses small.en, CPU int8/two threads. Microphone, name hints and recognition speed are set through Voice settings and stored locally in voice-settings.json.
- `launch.py --wake` enables name activation at startup. Normal startup has name activation and camera off.
- Windows supplies the synthesis voice. Enable desktop-app microphone/camera permissions if required.
- Use a writable directory: models, saved memory, projects and diagnostics live beside the source. Avoid Program Files.

Run `.\.venv\Scripts\python.exe scripts/check_repository.py --runtime` to check prerequisite files. Missing model errors: inspect server.log and Ollama list. Missing imports: repeat pip install and pip check. No speech: check Windows voices, PowerShell and System.Speech. First model load can take tens of seconds.
