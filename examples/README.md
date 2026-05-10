# Examples

Reference `.sage/` directories for real projects. Use them as starting points
when setting up Sage in a new project -- copy the structure, edit the
instructions to point at your own docs.

## chatbot/

The Python + Flask + pytest chatbot at `~/claudeProjects/chatbot/`. Shows how
to wire each agent to project-specific guidance:

- `sage-tester-config.yaml` -- how to run pytest with Flask in test mode
- `sage-test-creator-config.yaml` -- pytest conventions and fixtures
- `sage-developer-config.yaml` -- module boundaries (sage/chat, sage/llm, sage/memory, sage/web)
- `sage-product-owner-config.yaml` -- spec format and locations

To actually use this for chatbot, the chatbot project would copy
`examples/chatbot/.sage/` to `~/claudeProjects/chatbot/.sage/` and Sage would
find it automatically (the loader looks in `<absolute_root_dir>/.sage` by
default).

## Add your own

When you set up a new project, run `_tools/setup_project.py` from this dir to
scaffold a `.sage/` directory in your project, then fill in the instructions.
