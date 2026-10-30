"""Every name a component imports from the use case's own modules must exist: a renamed helper fails here, in a
second, not in a pipeline run an hour later. Run by `pipewright test` (tests.command in usecase.yaml).

    python tests/check_imports.py
"""

import ast
import importlib
import sys
from pathlib import Path

COMPONENTS = Path(__file__).resolve().parents[1] / "components"
sys.path.insert(0, str(COMPONENTS))
own = {p.stem for p in COMPONENTS.glob("*.py")}

problems = []
for path in sorted(COMPONENTS.glob("*.py")):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module in own:
            module = importlib.import_module(node.module)
            problems += [f"{path.name}:{node.lineno}: {node.module} has no {a.name}"
                         for a in node.names if not hasattr(module, a.name)]

print("\n".join(problems) or f"imports OK in {len(list(COMPONENTS.glob('*.py')))} component files")
sys.exit(1 if problems else 0)
