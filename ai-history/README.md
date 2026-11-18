# AI history

Exported transcripts of the AI-assisted sessions used to build this project.

They are included on purpose: the case asks how AI was used, and the transcripts show the
prompts, the plan proposed before each phase, the review and fix loops, and the decisions
that were changed or rejected along the way. Read them alongside `git log`; each phase in
the transcripts maps to a group of Conventional Commits.

Files:

- `00-prompt-design-session.md` – Claude chat: reading the case PDF, writing the build prompt, and the orchestrator correction.
- `01-build-session.md` – Claude Code session that built the project.

Notable turns worth looking for:

- **Phase 2**: inspecting compileit.com before writing the crawler; trafilatura measured as
  lossy on this site and replaced.
- **Phase 3**: textbook hybrid retrieval measured as *worse* than vector-only, and fixed.
- **Spec correction**: the agent refactored into an explicit orchestrator.
- **Phase 7**: the eval moved two prompt rules into the orchestrator; one limitation
  characterised rather than over-tuned.

Files are named `NN-<topic>.md` in chronological order and exported as-is, **except that
secrets are redacted** before they are added here (API keys replaced with `sk-…REDACTED`).
