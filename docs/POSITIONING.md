# Standalone Automation Agent — Positioning

**Hook:** *Your team's QE standards, enforced — on top of Copilot.*

**What it is:** an MCP-based QE agent that generates UI/API automation which
consistently matches your existing framework's standards — for every developer,
on any model, in the IDE **or** CI/headless/cloud — and plugs into a
requirements→tests pipeline. It *orchestrates* Copilot rather than replacing it.

---

## The objection every technical buyer raises first

> "Why not just use `.github/copilot-instructions.md`? Copilot can match our style,
> reuse our code, and write the test itself."

**Honest answer: for one developer in the IDE, that's often enough.** Custom
instructions auto-apply "match our style / reuse X / don't invent" to Copilot, and
a skilled dev with a good prompt gets a solid test. If that's your whole use case,
you don't need this agent — and we should say so.

The agent earns its place where **copilot-instructions.md structurally cannot reach.**

### Where copilot-instructions.md stops, and the agent continues

| Need | copilot-instructions.md | This agent |
|---|---|---|
| Enforce style for one dev, in the editor | ✅ Good enough | ✅ (overkill) |
| **Identical** behavior across many devs/repos | ⚠️ per-repo, per-dev, drifts, unversioned centrally | ✅ one server, one standard, central |
| Run in **CI / headless / outside the IDE** | ❌ editor-only | ✅ CLI / CI / cloud-hosted |
| **Model/host independence** | ❌ tied to Copilot editor | ✅ sampling / token / any provider |
| **Programmatic** invocation (other agents, scripts) | ❌ | ✅ it's a tool/API |
| **Pipeline**: requirements (RAG) → cases → scripts → data → API | ❌ | ✅ one stage of a QE platform |
| **Audit / governance** (who generated what, to which standard) | ❌ | ✅ logged, allow-listed, centralized |
| Validate output before review (self-heal) | ❌ | ✅ Phase-1 static heal |

**One line:** *instructions are a per-repo hint; the agent is a portable, governed,
auditable QE standard that also runs where the IDE can't.*

---

## What the agent actually contributes (vs "Copilot does it all")

Copilot does the heavy lifting it's best at — and the agent **orchestrates** it:

```
Copilot gathers files (LSP/nav) → AGENT enforces standards + drafts → host model
writes → AGENT validates (self-heal) → Copilot grounds (resolve methods, fix
imports) → USER reviews each change (diff + Allow/Skip)
```

- The **code is written by the host model** (e.g. Copilot's Claude Sonnet 4.6) — no
  extra key. The **agent decides *how* it must be written** (your standards, style
  contract, real method signatures, no-invent rules) and **validates** it.
- The agent turns "depends on each dev prompting Copilot perfectly" into
  "**the same, every time, everywhere, auditable.**"

---

## Who it's for

- QE / test-automation teams standardizing across **many devs and repos**.
- Orgs that **already have Copilot** and want governed, consistent test generation.
- Teams needing generation in **CI / headless / hosted**, or as part of a
  requirements-to-tests **pipeline**.

## When NOT to use it (be honest)

- A **single developer** doing interactive, exploratory test writing in the IDE →
  **Copilot (+ copilot-instructions.md) is enough.**

## The pitch (don't over-claim)

> Copilot is a *capability*. This agent is a *governed, portable QE standard built on
> that capability* — consistent for every developer, runnable in CI and the cloud,
> model-agnostic, validated, and wired into your requirements→tests pipeline.

Its value scales with **team size, number of repos, and reach** (CI / hosted /
pipeline). It is **not** sold as "smarter than Copilot" — it's sold as
"**the same standard, every time, everywhere, auditable.**"
