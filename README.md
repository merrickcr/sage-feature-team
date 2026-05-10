# Sage Feature Team

A multi-agent feature-development workflow for Claude Code. Generic agents
(ProductOwner, TestCreator, Developer, Tester) coordinated by a Skill/Team
Lead. Project-specific knowledge lives in each project's `.sage/` directory.

---

## Core Idea

Each agent has **one fixed job** and **one generic instruction file**:

| Agent | Job | File |
|---|---|---|
| ProductOwner | Write a feature spec | `agents/product-owner.md` |
| TestCreator | Write tests for the spec | `agents/test-creator.md` |
| Developer | Make tests pass without breaking others | `agents/developer.md` |
| Tester | Run tests, report pass/fail | `agents/tester.md` |

Each project tells these agents **how** to do their job for that project via a
`.sage/sage-<agent>-config.yaml` file containing a list of plain-English
instructions. The instructions point at project markdown docs that the agent
reads at runtime.

```
sage-feature-team/                       ← this repo (the system)
├── agents/
│   ├── _BASE.md                         ← shared protocol + {PROJECT_INSTRUCTIONS} hook
│   ├── product-owner.md                 ← generic job
│   ├── test-creator.md                  ← generic job
│   ├── developer.md                     ← generic job
│   └── tester.md                        ← generic job
├── _tools/
│   ├── load_agents.py                   ← assembles agent prompts
│   └── setup_project.py                 ← scaffolds .sage/ in a new project
├── HANDBOOK.md                          ← protocol details (handshake, ACK, etc.)
├── sage-config.yaml                     ← team/path config (this is for chatbot)
└── examples/chatbot/.sage/              ← reference configs

<your-project>/                          ← e.g. ~/StudioProjects/Breadcrumbs
├── sage-config.yaml                     ← created by setup wizard
└── .sage/
    ├── sage-product-owner-config.yaml   ← project's instructions for ProductOwner
    ├── sage-test-creator-config.yaml    ← project's instructions for TestCreator
    ├── sage-developer-config.yaml       ← project's instructions for Developer
    └── sage-tester-config.yaml          ← project's instructions for Tester
```

---

## How a Run Works

1. User invokes `/sage-feature-team "Add dark mode"`
2. Skill reads `sage-config.yaml` and calls `_tools/load_agents.py`
3. Loader:
   - Reads `agents/_BASE.md` + each role file
   - Finds the project's `.sage/` directory (defaults to `<project_root>/.sage/`)
   - Reads `.sage/sage-<agent>-config.yaml` for each agent
   - Substitutes the instructions list into `{PROJECT_INSTRUCTIONS}` in `_BASE.md`
4. Skill creates a team and spawns the four agents with their fully-rendered prompts
5. Each agent reads its referenced project files (test guides, code conventions, etc.) using the Read tool when relevant
6. Skill routes work through ProductOwner → TestCreator → Developer ↔ Tester until tests pass or max cycles hit

Two modes:
- **full** — all four agents (spec → tests → code → validation)
- **dev-test-only** — Developer + Tester (tests already exist; fix and verify)

---

## Setup for a New Project

```bash
cd ~/StudioProjects/Breadcrumbs
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py
```

The wizard asks for project name + root path, then writes:
- `sage-config.yaml` (team name, paths)
- `.sage/sage-product-owner-config.yaml` (skeleton)
- `.sage/sage-test-creator-config.yaml` (skeleton)
- `.sage/sage-developer-config.yaml` (skeleton)
- `.sage/sage-tester-config.yaml` (skeleton)

Then edit each `.sage/sage-*-config.yaml` to fill in the `instructions:` list.
Each instruction is a one-line English statement, ideally pointing at a project
markdown file:

```yaml
instructions:
  - "When running tests, follow docs/run_gradle_tests.md."
  - "Test files go in app/src/test/java/, naming pattern <Feature>Test.kt."
  - "If a test references the emulator, see docs/start_emulator.md first."
```

See `examples/chatbot/.sage/` for filled-in reference configs.

---

## Files

| Path | Purpose |
|---|---|
| `agents/_BASE.md` | Shared protocol + the `{PROJECT_INSTRUCTIONS}` hook |
| `agents/<role>.md` | Generic job description per agent |
| `HANDBOOK.md` | Full protocol details (handshake, ACK, escalation, Monitor) |
| `sage-config.yaml` | This project's team/paths config (chatbot example) |
| `sage-config.SCHEMA.md` | Field reference for `sage-config.yaml` |
| `_tools/load_agents.py` | Assembles agent prompts; finds `.sage/`; substitutes vars |
| `_tools/setup_project.py` | Setup wizard for new projects |
| `_tools/README.md` | Tool-level docs |
| `templates/MESSAGE_TEMPLATE.md` | Standard SendMessage format |
| `templates/PROGRESS_TEMPLATE.md` | Progress file template |
| `guides/ORCHESTRATOR_PATTERNS.md` | Reusable Skill/Team Lead patterns |
| `references/ROUTING_REFERENCE.md` | Routing decision tree |
| `examples/chatbot/.sage/` | Reference `.sage/` configs for the chatbot project |
| `.claude/skills/sage-feature-team/SKILL.md` | The user-facing skill (full workflow) |
| `.claude/skills/sage-dev-test/SKILL.md` | The user-facing skill (dev-test cycles) |

---

## Adding a New Agent

1. Create `agents/<new-role>.md` (generic job description)
2. Add an entry to `team.agents.full` (and `dev_test_only` if applicable) in `sage-config.yaml`
3. Add the agent to `AGENT_SLUGS` in `_tools/load_agents.py` so its config file slug is known
4. Update the routing logic in `.claude/skills/sage-feature-team/SKILL.md`
5. Each project then creates `.sage/sage-<new-role>-config.yaml` to give it project-specific guidance

The hook (`{PROJECT_INSTRUCTIONS}`) is in `_BASE.md` — every agent gets it automatically.
