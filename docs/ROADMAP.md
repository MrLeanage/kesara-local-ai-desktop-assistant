# Kesara 2.0 — Delivery roadmap

Status: planning baseline (2026-11-19). Source of truth for implementation sequencing. Each milestone is independently reviewable; do not treat a milestone as complete until its acceptance checks pass.

## Product objective
Build a free-first Windows software engineering assistant that can inspect an existing codebase, propose architecture-aware changes, edit code with permission, run tests, report evidence, and eventually improve Kesara's own repository. Preserve a persistent readable chat and replace the avatar with a voice-reactive waveform.

## Principles
- **Smallest working release first:** reuse the existing Tkinter chat, voice, Ollama, five tool actions, and approval flow. Do not rebuild the stack prematurely.
- **No paid dependencies required:** Ollama/local models work by default; optional remote free-tier providers must be opt-in, clearly disclose network/data transfer and quota limits, and never be a prerequisite.
- **No silent self-modification:** Kesara may select his own source checkout as a project, but must use a feature branch, show proposed changes, request approval for writes/commands, test and review before merge. Never modify the running installation as an uncontrolled experiment.
- **Evidence over claims:** record commands, exit codes, test output and changed files. Distinguish implemented, tested, and planned.
- **Parallel-safe contributions:** one GitHub issue per deliverable, one branch per issue, no shared mutable branch across agents; PR to main only after integration checks.
- **Prefer standard library** where useful; defer complex frameworks until justified.

## Milestones and gates

### M0 — Existing runnable baseline / self-code proof (P0)
Outcome: an immediately usable coding prototype with documentation for working on its own codebase; no new UI dependency.

- Verify existing local Ollama + Qwen2.5-Coder 3B startup, CLI and desktop entry points.
- Provide a clear 'develop Kesara' workflow: select a separate checkout of this repository as the project; inspect before changing; approve writes/commands; keep Git changes recoverable.
- Add reproducible smoke tests for core tool routing/path boundaries and a simple supervised self-edit sandbox example.
- Ensure no secrets, models or virtual environments are committed.
- **Gate:** on Windows the CLI can read a harmless file, propose a small change, execute a user-approved test, and show observed results; an unapproved write is not performed.
- **Constraint:** GitHub-only contributors cannot claim the Windows gate passed without Windows evidence.

### M1 — Minimal persistent chat + voice-wave UI (P0)
Outcome: no avatar, one useful chat screen, re-openable conversation history, same voice functionality.

- Disable the avatar/3D character from active entry points; retain recoverability through Git history.
- Replace floating avatar with a responsive wave/orb visualization for idle, listening, thinking and speaking.
- SQLite local conversations/messages, conversation chooser, new chat, reopen, searchable transcripts, Markdown/code blocks (minimal render first), export.
- Keep full human-readable history separate from bounded model context.
- **Gate:** restart and reopen chats; code snippets remain readable; text mode works with mic unavailable; approvals remain visible; existing voice loop works on Windows.

### M2 — Repository-aware coding (P0)
Outcome: useful experienced-engineer workflow, rather than one-shot file writing.

- Build a bounded project map (languages, manifests, tests, entry points, Git status) with .gitignore and file-size exclusions.
- Search targeted symbols and references; fetch context on demand, with redaction and token budgets.
- Add plan/diff/review stages and safe patch edits instead of whole-file replacement.
- Begin with Java/Spring Boot, Python, and Flutter templates; no hardcoded assumption about a single stack.
- **Gate:** given a small real repository, Kesara explains the design impact, shows a plan, applies a reviewed patch, and does not touch unrelated files.

### M3 — Build/test/review loop (P1)
Outcome: repeatable implementation with evidence.

- Detect build/test commands for Maven, Gradle, pytest and Flutter; preview and approve execution.
- Collect outputs, analyze failures and retry within explicit limits.
- Report changed files, commands, return codes and remaining risks.
- **Gate:** two sample issues (one bug, one feature) pass applicable tests, with no unsupported success claims.

### M4 — Self-development and Git workflows (P1)
Outcome: Kesara can modify *his own checked-out code* under supervision.

- Explicit self-development project mode; separate worktree/branch; refuse dirty or protected main by default.
- Plan approval, per-operation permission, checkpoint commits and rollback path.
- Prepare PR summary and review package; optional GitHub integration behind consent, otherwise local Git.
- **Gate:** from a clean Kesara checkout, modify a small safe feature on a feature branch, run tests, produce diff and preserve main. User manually merges.

### M5 — Advanced assistant (P2)
Outcome: better inference/provider flexibility, project memory and optional issue integrations.

- Model/provider adapter prioritizing local free models and measuring suitability on real coding tasks; optional remote free tiers with explicit consent.
- Index project notes/architecture decisions with privacy limits.
- Jira ticket intake, richer architecture diagrams, stronger security policy, packaging and end-to-end Windows regression.
- **Gate:** demonstrate reproducible ticket-to-PR flow, with safeguards and no paid-service requirement.

## Immediate release definition
**First usable release = M0 + a thin M1:** existing voice/text coding actions remain available, user can choose the Kesara checkout as a project, explicit approvals remain active, chat survives restart, and avatar is replaced. Do not block that release on cloud APIs, Jira, autonomous PRs, RAG, or UI framework migration.

## Cross-chat/agent handoff protocol
1. Read this file, `AGENTS.md`, the relevant GitHub issue, and the current source before coding.
2. State scope, affected files, baseline commit, required acceptance checks, and security risks in the issue/PR.
3. Create a dedicated `feature/<issue>-<short-name>` branch from updated main (or designated integration base); never push directly to main.
4. Keep commits small. Avoid editing the same files in parallel unless coordinated.
5. Run tests you can run; include exact commands/results. Mark unavailable Windows tests as **NOT RUN**.
6. End with a concise handoff: completed, remaining, changed files, commit/PR, tests, blockers, next task.
7. Update status here only once evidence meets the gate. Different chats can resume from repository state, not chat memory.

## Milestone status
| Milestone | Status | Dependencies |
|---|---|---|
| M0 runnable/self-code proof | In progress | existing prototype |
| M1 minimal voice-wave + chat | Planned | M0 |
| M2 repository-aware coding | Planned | M0 |
| M3 build/test/review | Planned | M2 |
| M4 supervised self-development/Git | Planned | M2 + M3 |
| M5 advanced integrations | Backlog | M4 |

> Existing code already supports selecting arbitrary project folders and approval-gated reads/writes/shell. This is **not** proof that self-development is safe or robust; M0/M4 add the necessary checks.

## 2026-11-19 voice-ASR delivery increment
- Implemented selectable **NVIDIA Parakeet TDT 0.6B V3 INT8** offline speech engine with verified-download installer, `sherpa-onnx` CPU decoding and no paid API.
- Existing Whisper Small/Medium preserved; users explicitly choose the engine in Voice settings and restart.
- Added optional dependency manifest, source-only regression tests and Windows setup instructions under `docs/SETUP.md`.
- **Pending Windows acceptance gate:** install optional Python runtime, download model, compare spoken technical sentences with Whisper and verify low false-positive rate. Do not mark voice recognition reliable based only on CI mocks.

## 2026-11-19 coding agent reliability review
**Fixed / implemented**
- Deterministic `mkdir` action for explicit directory + folder-name requests. It uses the user's resolved absolute destination, not implicitly the selected project root. Creates nothing if the parent is missing or the folder already exists.
- Reads inside the *selected project* no longer prompt merely because that project is outside Kesara's internal `projects/` folder.
- Folder creation participates in project-scoped write approval settings.
- Ambiguous explicit folder paths fail closed instead of executing a guessed PowerShell `mkdir`.
- Regression tests cover explicit folder destinations, idempotency, scoped approvals and selected-workspace reads.

**Next critical engineering improvements (not yet implemented)**
1. Separate typed/confirmed intent from ASR transcript, show resolved target preview and a diff/plan before consequential work.
2. Replace generic shell-first file operations with typed filesystem tools (mkdir, move, delete, copy, path existence, search), path normalization and sandbox/allowlist boundaries.
3. Add repository indexing, source-symbol search, dependency awareness and language-specific project detectors for Maven/Gradle, Flutter, Python.
4. Replace full-file rewrite actions with structured patch/diff application, git branch isolation and rollback.
5. Add explicit plan-execute-verify loops, automated test runners and evidence-based completion reports.
6. Upgrade reasoning models when hardware/cloud budget permits; the 3B coding model should not be trusted to infer filesystem paths from noisy transcripts.
7. Reduce repeated approvals using fine-grained capability-scoped policies rather than unrestricted PowerShell authorizations.

**Acceptance gate:** verify correct explicit Windows destination with spaces, verify the active project reading a file outside `projects/`, verify no changes occur after declined approval. CI mocks cannot prove end-to-end Windows shell/audio behavior.

## 2026-11-19 architecture implementation increment — Python desktop retained

Decisions represented in this increment: keep existing Python/Tkinter UI and
voice; use free/local Ollama by default, with opt-in cloud providers; separate
model reasoning from native coding tools; preserve project-scoped approvals;
advance to plan → implement → test → review on a bounded, evidence-based path.
**Flutter desktop migration is intentionally deferred** for Kesara to help
with later, not undertaken in this increment.

Implemented now:
- `coding_tools.py`: bounded source scan with excluded generated directories,
  `project_map` (project manifest hints, entry points, Git status), targeted
  `search_code`, and allowlisted test-runner detection with explicit approval.
- New model action kinds `project_map`, `search`, and `test`; retain existing
  deterministic copy/mkdir and approval-controlled write/shell operations.
- Direct chat commands `/map`, `/search <symbol>`, and `/test` do not require
  model tool selection, making these usable with Qwen2.5-Coder 3B.
- Activity logs now record action type and success metadata, never the entire
  generated file contents, command, or tool output.
- Regression coverage includes constrained search, project mapping, test
  approvals, pass/fail evidence and model-independent direct commands.

Not yet delivered: full planning agent, multi-agent orchestration, AST-aware
patching, disposable Git worktrees, code review/rollback engine, Jira-driven
ticket-to-PR, self-modification, or Flutter migration. MCP is not necessary
for local filesystem/search/test tools; it may later be an adapter for Jira,
GitHub and other external services, always behind authorization.

Acceptance: on Windows, select a real repo; run `/map`, `/search <symbol>`,
and `/test`; inspect source mappings and real test output. GitHub CI covers
mocked test subprocesses but not full Windows integration.
