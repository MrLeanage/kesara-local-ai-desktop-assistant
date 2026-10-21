# Technology stack

| Component | Technology | Purpose |
|---|---|---|
| Desktop | Python 3.13, Tkinter/Tcl-Tk | Floating UI, chat, approvals |
| Coding | Ollama HTTP API, Qwen2.5-Coder 3B Q4_K_M | Local structured action agent |
| Recognition | faster-whisper, CTranslate2, Whisper small.en, PyAV | CPU int8 transcription |
| Capture | sounddevice / PortAudio | Microphone |
| Speech | PowerShell, .NET System.Speech, C# helper | Persistent synthesis and visemes |
| Quiet controls | Vosk small English | Interrupt commands |
| Optional camera | MediaPipe, OpenCV, hand landmarker | Palm/thumbs-up detection |
| Avatar | Pillow, cached RobotExpressive clips | Animation without live 3D rendering |
| Photo fallback | Pillow, NumPy, OpenCV | Face and gesture blending |
| Legacy developer renderer | pywebview, Three.js, TalkingHead | Optional 3D rendering |

requirements.txt contains direct pins. requirements-lock.txt snapshots all installed Python distributions, including transitive dependencies. It contains both OpenCV distributions as present in the development environment; validate camera/photo behavior before changing those pins. Python, Tk, PowerShell/.NET, Ollama and model weights are external prerequisites.

Source map: launch.py starts Ollama; kesara.py handles model/tools; desktop.py handles chat/conversation; voice.py handles capture/transcription/speech; interaction.py handles wake/camera; companion.py hosts the floating UI; robot_character.py plays the atlas. speech_worker.cs is compiled by the local speech worker.
