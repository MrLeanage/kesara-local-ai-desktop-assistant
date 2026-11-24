# Kesara Autonomous — MVP

This is a separate experimental entry point; the original UI is unchanged. Run from repository root with module syntax (not by executing operator.py directly).

## Windows prerequisites

- Python 3.13, authenticated native Codex CLI executable on PATH (npm .cmd wrappers are not supported by this prototype).
- A trusted project directory. No administrator privileges are required.
- Check Codex manually using codex --version and codex login status.

Terminal 1:

```powershell
py -3.13 -m autonomous.operator run
```

Terminal 2, with an existing test workspace:

```powershell
py -3.13 -m autonomous.operator submit "D:\Projects\kesara" "Read README.md and summarize the project without changing files."
py -3.13 -m autonomous.operator status
py -3.13 -m autonomous.operator result 1
```

The status "reported" means the delegated process exited successfully, not independent verification. Logs and SQLite data are under %LOCALAPPDATA%\KesaraOperator. Use one worker process only. Interrupted running jobs are retained but not automatically replayed.

## Optional Telegram

Create a private bot using BotFather. Obtain your own numeric Telegram user ID from a trusted source. Set KESARA_TELEGRAM_TOKEN and KESARA_TELEGRAM_CHAT in the local process environment; never commit secrets. Start the bot with:

```powershell
py -3.13 -m autonomous.operator run --telegram-workspace "D:\Projects\kesara"
```

Only the configured user's private chat is accepted. Send /task followed by an objective, or /status. For voice transcription install faster-whisper in the same Python environment. Voice messages are transcribed locally; the first model download needs internet. Review the transcription and submit it as /task. Do not use for sensitive material: Telegram receives messages and Codex may receive task content.

This prototype uses workspace-write, not administrator or unrestricted machine access. It does not install a service, operate arbitrary GUI apps, make live calls, automatically recover interrupted jobs, or independently validate Codex output. Stop the worker using Ctrl+C; check for remaining child processes before restarting. No production credentials or sensitive repositories should be used for initial tests.

## Acceptance checks

1. Submit a read-only task and verify the report against README.md.
2. In a disposable workspace, request a small application and inspect the generated files and test results.
3. Verify an unauthorized Telegram account cannot enqueue work.
4. Check that a failed Codex invocation records failed instead of reported.
5. Inspect logs and ensure no credentials are exposed before enabling remote use.

Windows end-to-end execution is not yet validated.
