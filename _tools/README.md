# Python tools

Two scripts. Both invoked by humans (setup) or by skills (loading).

---

## load_agents.py

Loads each agent's prompt for a mode. Skills call this; you generally don't.

```bash
python _tools/load_agents.py full
python _tools/load_agents.py dev-test-only
```

### What it does

1. Find `sage-config.yaml` (cwd → script parent → walk up the tree)
2. Validate it (`project`, `team`, required fields)
3. Find the project's `.sage/` directory:
   - `paths.sage_dir` if set
   - else `<absolute_root_dir>/.sage`
   - else `<root_dir>/.sage`
   - else `./.sage`
4. For each agent in the requested mode:
   - Read `agents/_BASE.md` (shared protocol + `{PROJECT_INSTRUCTIONS}` hook)
   - Read the role file (e.g., `agents/tester.md`)
   - Concatenate base + role
   - Read `.sage/sage-<agent-slug>-config.yaml` for that agent
   - Format its `instructions:` list as a markdown bullet list
   - Substitute `{PROJECT_INSTRUCTIONS}` and other variables
5. Print JSON to stdout, exit 0 on success, 1 on failure

### Output JSON

```json
{
  "success": true,
  "mode": "full",
  "team_name": "<from team.name or team.dev_test_team_name>",
  "agent_names": ["ProductOwner", "TestCreator", "Developer", "Tester"],
  "agents": {
    "ProductOwner": "<fully rendered prompt>",
    "TestCreator":  "<fully rendered prompt>",
    "Developer":    "<fully rendered prompt>",
    "Tester":       "<fully rendered prompt>"
  },
  "sage_dir": "<resolved path or null>",
  "config_summary": {
    "project_name": "...",
    "absolute_root_dir": "..."
  }
}
```

On failure:

```json
{ "success": false, "error": "<message>", "error_type": "<exception name>" }
```

### Variables substituted into prompts

| Placeholder | Source |
|---|---|
| `{AGENT_NAME}` | Agent class name (`Tester`) |
| `{AGENT_NAME_SLUG}` | Slug for the config file (`tester`) |
| `{PROJECT_NAME}` | `project.name` |
| `{PROJECT_ROOT}` | `project.absolute_root_dir` |
| `{TEAM_NAME}` | `team.name` |
| `{DEV_TEST_TEAM_NAME}` | `team.dev_test_team_name` |
| `{OUTPUT_DIR}` | `paths.output_dir` |
| `{PROJECT_INSTRUCTIONS}` | Bulleted list from `.sage/sage-<slug>-config.yaml` |

`{PROJECT_INSTRUCTIONS}` is the only hook that's project-specific. It lives in `agents/_BASE.md`, so every agent gets it without needing to be edited.

### Empty / missing instruction config

If `.sage/sage-<slug>-config.yaml` is missing or has empty `instructions: []`, the loader substitutes a placeholder:

```
_No project-specific instructions configured._

_Create `.sage/sage-<agent>-config.yaml` with an `instructions:` list to give this agent project-specific guidance._
```

The agent will run, but with no project-specific knowledge — fine for ad-hoc testing, useless for real work.

### Agent slug mapping

Defined in `AGENT_SLUGS` in `load_agents.py`:

| Agent name | Config file |
|---|---|
| `ProductOwner` | `sage-product-owner-config.yaml` |
| `TestCreator`  | `sage-test-creator-config.yaml`  |
| `Developer`    | `sage-developer-config.yaml`     |
| `Tester`       | `sage-tester-config.yaml`        |

Adding a new agent? Add it here and to `team.agents.full` (and `dev_test_only` if applicable) in `sage-config.yaml`.

---

## setup_project.py

Interactive scaffolding for a new project.

```bash
cd ~/StudioProjects/Breadcrumbs
python ~/claudeProjects/sage-feature-team/_tools/setup_project.py
```

### What it does

1. Asks for project name and absolute path
2. Writes `<project>/sage-config.yaml` (team config — no project-specific HOW)
3. Creates `<project>/.sage/` and writes four skeleton instruction files:
   - `sage-product-owner-config.yaml`
   - `sage-test-creator-config.yaml`
   - `sage-developer-config.yaml`
   - `sage-tester-config.yaml`

Each skeleton has `instructions: []` and a comment block showing the format. The user fills them in to point the agents at their project's docs.

### What it doesn't do

- Doesn't probe the project for language/framework — that knowledge lives in the user's instruction list
- Doesn't preflight test commands or servers — Tester does that at runtime per its instructions
- Doesn't write or copy any project markdown — the user creates those, organized however they like

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `sage-config.yaml not found` | No config in cwd, sage-feature-team root, or any parent dir | Run `setup_project.py` from your project root |
| `Profile not found` (legacy error) | Old config still references the deleted profile system | Replace with the simplified config from `setup_project.py` |
| `Agent file not found: agents/X.md` | `team.agents.full` references a missing role file | Check the `file:` path in `sage-config.yaml` matches an actual file in `agents/` |
| `_No project-specific instructions configured._` appears in agent prompt | `.sage/sage-<agent>-config.yaml` missing or has empty `instructions: []` | Edit the file to add real instructions |
| `instructions must be a list` | YAML scalar where a list was expected | Use the bullet list form: `instructions:\n  - "..."\n  - "..."` |

---

## Layout

```
_tools/
├── load_agents.py    ← assembles agent prompts
├── setup_project.py  ← scaffolds .sage/ for a new project
└── README.md         ← this file
```
