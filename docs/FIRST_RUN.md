# Kesara 2.0 — First local verification (M0 + thin M1)

Branch: `feature/kesara-core-history-agent`. This release uses **the existing free local Ollama model** and Python/Tkinter; it does not add an API key or paid provider.

## What is new
- Avatar is disabled from the normal GUI entry points. A lightweight animated waveform replaces it in the floating voice window and chat sidebar.
- Local SQLite conversation history (`chat-history.sqlite3`), conversation list, reopen and per-conversation project association.
- Existing voice transcription, local speech, approvals, project-folder chooser and five coding actions retained.
- A guidance file (`AGENTS.md`) and roadmap (`docs/ROADMAP.md`) enable multiple agents/chats to work independently.

**Limitations:** The waveform reacts to microphone level while listening and animates for speaking/thinking; it is not a real-time speaker-output spectrum. Previous historical chat is re-opened for reading; the agent starts fresh model context when changing conversations (no potentially unsafe replay of tool calls). Rich Markdown and code highlighting are deferred. No autonomous self-update/merge has been implemented.

## Install/run on Windows
1. Preserve your current working installation. Create a **separate test checkout** of this branch:
   ```powershell
   git clone --branch feature/kesara-core-history-agent https://github.com/MrLeanage/kesara-local-ai-desktop-assistant.git kesara-v2-test
   cd kesara-v2-test
   ```
2. The repository intentionally excludes the Python environment, Ollama runtime and model files. Follow `docs/SETUP.md` to install free dependencies/models to this checkout (or use a separate existing tested installation as described below).
3. Run the source-only smoke checks before starting:
   ```powershell
   .\.venv\Scripts\python.exe -m compileall -q desktop.py companion.py waveform.py history.py kesara.py
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```
4. Start the GUI with `Start Kesara.cmd`. Open chat through the floating panel.
5. Create a chat, submit a prompt, close and reopen Kesara. Confirm the chat is listed and text is retained.
6. Check microphone input and speech output; wave should react when listening. Test speech-off/text-only mode if the microphone fails.
7. Ask for a harmless new test file in a scratch project, **decline the first write**, confirm nothing changed, then try again and approve. Review the actual file and execution output.

## First supervised self-development exercise
- Keep Kesara's running installation separate from the development checkout.
- Create a third folder: a clean clone of Kesara source, on a dedicated Git branch.
- In Kesara's workspace choose that third folder as the project.
- Ask: "Inspect this repository, explain the architecture, then propose a tiny isolated improvement. Do not write code before explaining the plan. After approval, implement and test it. Show the diff."
- Approve each proposed write/PowerShell command individually. Review `git status`, `git diff`, and tests before committing.
- **Do not merge automatically or let Kesara modify the checkout it is currently running from.** Current implementation does not enforce this separation automatically; it is an operational safety rule until M4.

## Report results
Capture Python compile/test results, whether GUI started, conversation persistence, listening/speaking behavior and one rejected/approved write. Open an issue with error tracebacks if a gate fails. This branch is **ready for local verification**, not yet verified on Windows.

## Voice chat from the small floating window (P0 follow-up)
1. Ensure Whisper is ready (the voice button enables after recognition initialization). Ollama can initialize on its first request, but the configured model must be installed.
2. Click **Start voice chat** in the **small floating waveform window**. You do **not** need to open the main chat workspace.
3. Speak naturally, then pause. Kesara should automatically stop recording, transcribe, send the utterance to local Ollama, speak the reply aloud and begin listening for the next turn.
4. Confirm the small window visibly cycles through **Listening → Transcribing/Thinking → Speaking → Listening**; the full chat maintains the transcript for later review.
5. Click **End voice chat** to end the conversation. Changes to files and shell commands still require a manual approval window.
6. If voice cannot start, open the main workspace for the model/voice error. Test `ollama list` and verify the `qwen2.5-coder:3b` model.

**Scope:** This is automatic turn-taking with silence endpoint detection and sentence-streamed text-to-speech. It is not yet full-duplex streaming speech-to-speech: listening pauses while Kesara speaks, and voice interruption/barge-in and true simultaneous audio streams remain future work. The existing transcript UI still shows text for review; it does not require a manual Send during voice mode.
