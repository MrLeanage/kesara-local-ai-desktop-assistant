# Kesara — Local AI Desktop Assistant

**A local AI desktop assistant with voice conversations, an animated avatar, coding tools, and approval-based PC actions.**

Kesara (pronounced Kae-sa-ra) is a Windows application that brings a personal AI assistant onto your desktop. A small, draggable character stays beside your other applications, allowing you to speak naturally, ask questions, and get help preparing coding projects. Its More menu opens a full workspace for text chat, project selection, saved preferences and settings.

The project combines a local language model, offline speech recognition, Windows speech synthesis and an animated character in one interface. After downloading the required dependencies and models, ordinary conversation and inference run locally without a paid AI API account. Initial installation and downloads require internet access; commands you approve may also access the network.

## What can Kesara do?

| Capability | How it helps |
|---|---|
| Voice conversation | Speak, pause, and hear a reply. Conversation mode listens again after the response; manual dictation lets you review words before sending. |
| Coding and project preparation | Explain code, inspect files, propose new or edited files, and run development commands with your approval. |
| Desktop character | Keep a floating animated robot nearby, with listening/thinking/speaking states and authored gestures. |
| Optional name activation | Enable standby listening and call Kesara by name to begin a conversation. |
| Optional camera gestures | Hold an open palm to pause or a thumbs-up to wake; camera frames are processed locally. |
| Saved preferences | Store instructions for future conversations through editable local memory. This does not train the model. |

For example, you can select a project folder and ask Kesara to inspect its code, explain a function, or prepare a small Python application. Kesara proposes any required file changes or shell commands for review before executing them. You can use voice for conversation and open the workspace whenever you want to inspect text or manage a project.

## How it works

Microphone audio is transcribed by local Whisper through faster-whisper. The text goes to a local Ollama language model, which returns an answer or proposes a supported tool action. Approved actions execute through the Python application. Windows speech synthesis reads replies aloud while the avatar changes state and animates.

The default configuration uses Qwen2.5-Coder 3B for coding and Whisper small.en for speech recognition. The default avatar plays cached RobotExpressive animations to reduce rendering work on modest hardware. Its gestures are authored animation clips; the application does not provide photorealistic human motion or complete autonomous control of every Windows application.

Name activation and camera access are optional and disabled on normal startup. File writes and shell commands require explicit approval. Kesara uses your Windows account's permissions and is not a sandbox; only approve actions you understand. The full architecture and dependencies are described in the [technology stack](docs/TECHNOLOGY.md).

## Requirements and setup

Windows 10/11 x64, Python 3.13 x64 **with Tcl/Tk**, Windows PowerShell, an installed Windows speech voice and preferably 16 GB RAM. CPU inference works without a supported GPU. Allow several GB for dependencies/models and internet access for initial downloads.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

Install external runtime/model files using [SETUP.md](docs/SETUP.md), then run **Start Kesara.cmd**. The CLI launcher is **Start Kesara CLI.cmd**. Wait for model and voice readiness.

## Features

- Draggable desktop character; More opens chat, projects and settings.
- Offline transcription, automatic pause detection and Windows speech replies.
- Optional name activation and camera gestures, disabled at normal startup.
- Local coding agent with streamed answers and saved preferences.
- Explicit approval for every proposed file write and shell command. The app uses normal account access and is not sandboxed. Camera gestures never approve actions.

Read the [user guide](docs/USER_GUIDE.md), [technology stack](docs/TECHNOLOGY.md), [configuration](docs/SETUP.md), [build instructions](docs/BUILD.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## Repository contents

Code and avatar assets are included. Personal projects, memory, logs, local settings, virtual environments, model weights and Ollama binaries are excluded. Build output belongs in GitHub Releases, not source control. `scripts/check_repository.py` checks common private/runtime exclusions and Git file sizes; it is not a comprehensive secret scanner.

This is a Windows prototype. Speech accuracy and response speed vary with microphone, accent, hardware and workload. Fresh-machine installation and offline dependency installation need separate validation. The supplied source archive does not bundle Python dependencies; the build script can create a separate dependency-bundled archive.

## License

The owner has not selected a license for original application source. Choose one before advertising this project as open source. Third-party components retain their own terms.
