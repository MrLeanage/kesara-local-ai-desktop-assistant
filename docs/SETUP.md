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


## Automatic first-run speech setup (Kesara 2.0)

After Python dependencies are installed, the desktop starts an asynchronous startup check for `speech-model/whisper-small.en`. If `model.bin`, `config.json`, `tokenizer.json`, or `vocabulary.txt` is absent, Kesara downloads the free `Systran/faster-whisper-small.en` model from Hugging Face into this local folder and loads it. If all four files already exist, no download occurs. Existing files are reused, and a failed download can resume on the next launch.

The status line displays download/loading progress (not a byte-accurate progress meter). Voice remains unavailable until the model loads; **text chat remains available** if the download fails. Internet access and several hundred MB of available disk space are needed for first setup. The startup download contacts Hugging Face; after setup, transcription runs locally. No paid API key is needed.

This automatic setup covers Whisper only. Ollama is still required and its configured `qwen2.5-coder:3b` model must be available on the running server. Optional Vosk name-activation interruption uses its separate Vosk model.

## Optional Parakeet V3 speech recognition (free / local, Kesara 2.0)

Kesara can now use the NVIDIA Parakeet TDT 0.6B v3 INT8 model via the Python
`sherpa-onnx` CPU runtime. This runs speech recognition fully offline after
the initial model download and does **not** require CUDA, cloud inference,
or a paid API. Existing Whisper Small/Medium remains selectable.

1. In PowerShell from your Kesara test checkout, install the **optional**
   Parakeet Python runtime once:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-parakeet.txt
   .\.venv\Scripts\python.exe -c "import sherpa_onnx; print('sherpa-onnx ready')"
   ```

2. Start Kesara normally and open **Chat workspace → Voice settings**.
   Select **NVIDIA Parakeet V3 (free, local CPU)** in "Offline speech engine".
   Leave "Review spoken text before sending" **enabled** while evaluating
   recognition accuracy on real project instructions. Save, then **restart Kesara**.
3. On the first Parakeet launch, Kesara downloads the official sherpa-onnx
   model archive (approximately 500 MB), checks its pinned SHA-256, safely
   extracts the four required model files, and loads the local ONNX recognizer.
   It requires approximately **2 GB of available disk space**. Download and
   initialization appear in the chat status line. Future launches reuse the
   local model, without internet access.
4. If the model integrity check fails, the source archive may have been
   republished upstream. Kesara deliberately **does not** execute unverified
   downloaded model files. Do not bypass the hash check: open an issue so the
   source and checksum can be reviewed and updated.
5. To return to Whisper at any time, select **Whisper (existing)**,
   save, and restart Kesara.

Technical details: model origin:
https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
The original NVIDIA model is distributed under CC BY 4.0; preserve
appropriate attribution when redistributing model files.

**Important:** The GitHub CI tests mock speech inference and model archives.
Live Windows recognition quality, throughput and memory consumption must be
measured on the laptop. This is an **offline turn-based recognizer**, not
full-duplex streaming/barge-in audio. Parakeet does not automatically
validate the user's intended commands; preserve code/tool approvals.

## Tool approval permissions (Kesara 2.0)

The chat workspace has a **Tool permissions** dropdown available before running any task.
Choose **Ask before each action** (default), **Allow project writes this session**,
**Allow writes + PowerShell this session**, **Always allow project writes**, or
**Always allow writes + PowerShell**. A **Reset** button immediately returns
that project to the default. Each project has its own selected policy.

Approval dialogs also offer **Decline**, **Allow once**, **Allow session**, and
**Always allow**. One-time approval never changes the policy. Session grants
last only until Kesara exits. Persistent grants are saved locally to
`approval-policy.json` (ignored by Git) and survive restarts.

**Warning:** PowerShell is *not* sandboxed. Persistent or session-wide shell
permission can execute arbitrary commands under your Windows account and
access files outside the project. Kesara shows an explicit warning before
such permission is granted. A persistent write grant is limited to writes
inside the selected project. Reads outside the project still prompt.

**Voice safety:** Enabling automatic permissions does not remove speech
verification. When any non-default automatic policy is active, every voice
transcript requires review in the composer before it can be executed. Spoken
file commands and paths also require review with the default permission policy.
Use typed requests to avoid transcription uncertainty.

## Multi-model coding engine (November 2026 increment)

Kesara now supports **Ollama (default, local), Google Gemini, Groq and
OpenRouter** with a standard-library router (`model_router.py`).

1. Update the checkout, start Kesara and open **Settings → AI engines / models**.
2. Select your model provider; default IDs include `qwen2.5-coder:3b`
   (Ollama), `gemini-2.5-flash` (Gemini), `openai/gpt-oss-20b`
   (Groq), and `openrouter/free` (OpenRouter). Model IDs can be changed in
   the settings window to match currently available free model offerings.
3. For a cloud provider, create an API key in that provider's official console.
   Set the corresponding environment variable **outside the repository**:
   `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY`.
   Restart Kesara from a process inheriting the variable. Do not type keys
   into chat messages or commit them to Git.
4. Check **explicit cloud context-sharing consent**. Kesara displays a second
   confirmation explaining that conversation, code and tool results may be
   sent to the chosen cloud provider. Leave it disabled for private/offline work.
5. Optionally enable fallback to local Ollama when your chosen cloud provider
   has an HTTP 429/5xx or a temporary network outage. Authentication errors
   and invalid model output never silently fall back. It does not pick another
   cloud service without your explicit selection.
6. Cloud responses must contain an agent JSON action; invalid action output
   is rejected before any filesystem or shell command executes.

The default remains **offline Ollama**. OpenRouter requests are hard-blocked
unless the configured model is `openrouter/free` or ends in `:free`.
**Important:** Gemini and Groq rate limits and billing rules depend on your
API account and the selected model. Kesara cannot guarantee that those
provider requests are free if you enable billing. Check the official free
allowances and billing before enabling cloud. Models may change availability.

This is a **provider-selection and fallback MVP**, not yet an autonomous
quality-based router with model benchmarking, distributed planning, or review
consensus. Cloud inference has not been integration-tested using your personal
API credentials. The CI suite uses simulated network responses only.

## Predictable directory copying

A known defect was generating invalid PowerShell copy commands and sometimes
interpreting relative destinations in Kesara's `projects` directory. Folder
copying now uses Python's validated directory-copy tool instead. Use **two full
quoted absolute paths**:

```text
Copy all content from "D:\AI works\Kesara 2.0\kesara-v2-test" to "D:\AI works\Kesara 2.0\Kesara-2"
```

Kesara refuses missing source folders, missing destination parents, existing
destinations, paths inside source folders, and relative/ambiguous path requests.
It presents a `COPY source -> destination` permission request before the
copy, unless the destination is within a separately approved workspace and
the configured project permission policy covers copies. The copy includes
all contents (including `.git` and `.venv`) and does not overwrite existing
folders; check disk space beforehand. It reports an incomplete copy rather
than claiming success on exceptions.

For copies with short names such as "copy kesara-v2-test to Kesara-2", supply
full quoted paths. Kesara will not guess relative directories.
