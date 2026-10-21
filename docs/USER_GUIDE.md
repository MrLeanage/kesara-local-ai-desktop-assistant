# Kesara Local

Open the Kesara desktop / Start-menu shortcut, or double-click **Start Kesara.cmd**. The assistant, coding model, speech recognition and camera gestures run locally. No paid API or account is required. **Start Kesara CLI.cmd** opens the terminal version.

## Floating character

The default is the animated **RobotExpressive** character, with authored skeletal idle, wave, nod, head-shake and thumbs-up animations. Frames are cached from the 3D model and played at 24 fps, so there is no live browser renderer or photographic optical-flow calculation during normal use. Facial variants respond to speech; this is not human phoneme-perfect lip sync. The model is CC0 by Tomás Laulhé, with modifications by Don McCurdy; source and attribution are in assets/three/THIRD_PARTY.md.

The previous photographic Kesara face and hand-gesture experiment remains available in More. Its generated image records are in assets/photo-generation.md and assets/photo-gesture-generation.md.
Drag the character to reposition him. Click him or the status button beneath him to start a conversation; click again to end it, or stop the active task. **More** opens a small menu:

- **Open workspace**: full chat, projects, memory and settings. Closing the workspace hides it.
- **Enable name activation (microphone)**: optional local standby listening.
- **Enable camera gestures**: optional local camera controls.
- **Last speech heard in standby**: inspect the last recognized standby phrase, held in session memory.
- **Be quiet / idle**: stop speech and cancel further actions.
- **Use photographic Kesara**: switch to the previous photo avatar. The same menu switches back to the animated robot.
- **Quit Kesara**: exit and release the microphone/camera.

Name activation and camera start off in a normal launch. The command-line --wake option starts with name activation enabled. Status shows Mic on and Camera on when enabled.

## Talking

Once voice and AI are ready, click the character, speak, then pause for about 1.2 seconds. The turn is transcribed and sent automatically; Kesara speaks the reply and listens again. Recording has a 30-second limit. Recognition can make mistakes; use the workspace's manual Talk / Done / Send controls to review dictated text before submitting it.

With name activation enabled, say **Kesara** (Kae-sa-ra). He acknowledges “Yes, I'm listening.” You can also say **Kesara, [your request]** in one phrase. Detection waits for a pause and runs Whisper locally, so wake-up can take several seconds. Common transcription variants of the name are accepted. Unmatched standby speech is discarded instead of being submitted to the coding model.

Say **silent for a while**, **be quiet**, or **go to sleep** to stop speech and request cancellation of further actions. A command or model request already running may need to finish. Name activation stays armed if enabled. Say **stop listening** during a conversation to disable the listening loop and name activation, or disable it in More.

An old unsent draft does not block a new conversation: it is preserved in chat and unsent-drafts.jsonl, and is never submitted automatically. Voice settings in the workspace select the microphone and recognition-name hints.

## Camera gestures

After enabling camera gestures, hold an **open palm for 1.2 seconds** to pause, or a **thumbs-up for 1.2 seconds** to wake. Lower your hand before repeating. Camera gestures only control conversation; they never approve actions. Disable the camera in More to release it. Frames are processed locally and are not saved. Your live gestures and accent still need personal testing.

## Coding and PC access

Choose a project folder in the workspace. Kesara can list/read files, propose complete file changes and run PowerShell development commands. Every file write and shell command requires an explicit approval dialog. Declining an action prevents it. The app uses normal Windows-account permissions; it is not an administrator or a sandbox. Approvals remain visible while the workspace is hidden.

Save preferences in Settings → Saved memory, or type `/remember Use Python unless I ask otherwise`. Export conversation and start a new chat from the workspace. Saved preferences do not train or modify model weights.

## Runtime and speed

The coding model is Qwen2.5-Coder 3B Q4_K_M through local Ollama, with four CPU threads. It warms when Kesara opens and stays loaded for an hour when memory allows. Cold startup can take tens of seconds. Warm ordinary replies have previously begun in a few seconds; complex coding tasks take longer. Replies stream as generated.

Speech recognition is faster-whisper small.en, CPU int8. Balanced decoding now uses two beams; low-confidence results can retry with five. **Voice settings → Recognition speed → Accurate** restores five-beam decoding. The Philip and Kesara synthetic test sentences retained their words in both modes, but live recognition can still differ.

Windows speech is preloaded once and kept in a small local worker instead of starting PowerShell and compiling its event helper for every reply. Two warm checks reached the first speech/mouth event after about 0.15–0.28 seconds; these are speech-start timings, not total question-to-answer latency. Longer spoken answers can begin at the first complete sentence while the model finishes generating. The microphone stays paused until generation and speech finish, and Stop cancels queued speech.

End-of-turn checks run more frequently and wait for about 1.2 seconds of silence. Short pauses and silence-only clips are tested. Recognition and generation still take several seconds on this CPU, with variable timings under other PC workloads. The coding model, context window, file approvals and output capacity are unchanged.

An isolated 340×410 robot frame took about 5.5 milliseconds to render versus about 33 milliseconds for the previous photographic gesture frame. Cached Tk images further reduce repeated drawing. The 24 fps target can still drop during heavy PC work. See robot-verification.json, stream-speech-verification.json, low-latency-voice-verification.json and optimization-verification.json.

## Local files and diagnostics

- projects/: default project directory.
- memory.json: user-saved preferences.
- voice-settings.json: recognition-name hints.
- speech-model/: offline speech models; models/ and runtime/: Ollama files.
- voice-diagnostics.jsonl: recording/device/status metadata, without recordings or recognized words.
- runtime-state.json: diagnostic state flags and character counts, without transcript text.
- performance.jsonl: model timing metadata, without prompt/response text.
- activity.jsonl: executed action details; may include code and tool output.
- unsent-drafts.jsonl: preserved unsent text.

No raw audio or camera recordings are saved. Dictated task messages appear in chat. Do not store passwords in memory or project prompts. Closing the floating window now exits the assistant, including background listening.

Verification reports include photo-verification.json, companion-verification.json, conversation-verification.json, interaction-verification.json, speed-verification.json and earlier coding checks. These establish tested behavior, not guaranteed accuracy for every live recording or coding project.

CLI commands: /help, /remember TEXT, /memory, /forget NUMBER, /cd PATH, /reset, /quit.
