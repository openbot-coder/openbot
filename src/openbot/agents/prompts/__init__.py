from pathlib import Path

workspace_prompt = (Path(__file__).parent / "workspace.md").read_text(encoding="utf-8")
print(workspace_prompt.format(workspace="openbot"))
