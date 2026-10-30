"""Every setting of a use case, in one file: what `pipewright resolve` runs, written back as a complete usecase.yaml.

    python tools/all_settings.py --env test --usecase lapse-risk > reference/lapse-risk-all-settings.yaml

Each value is one the team set (in usecase.yaml or config/*.yaml, shown as written), one the environment's
override file sets (marked with its file), or a default Pipewright filled in (marked `# default`). Values the
platform supplies (the runner, the dataset, the landing prefix) are left out: they come from the environment
manifest, never from the use case. The file ends with the settings the use case does not use at all.
`pipewright explain <key>` says what any key means.
"""

import argparse
import subprocess
import sys
from importlib import resources
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ORDER = ["tenant", "pipelines", "components", "framework", "triggers", "parameters", "steps", "data", "features",
         "training", "evaluation", "explainability", "registry", "model_card", "inference", "monitoring",
         "retraining", "data_protection", "outputs", "model", "approvals", "labels"]
NAMED = {"parameters", "steps", "hyperparameters", "search_space", "tables"}   # their keys are names, not settings
DERIVED = {"outputs.bigquery.tables.<name>.columns", "outputs.bigquery.dataset"}  # resolve reports, nobody sets
WIDTH = 78                                                    # the widest line that prints on a page
NOT_LISTED = {"resources", "pipeline", "resources_per_step", "features_store"}   # the platform's, older names, reserved


def documented() -> dict[str, str]:
    """Every documented key, with the first sentence of what it means."""
    text = resources.files("pipewright.config.schemas").joinpath("reference.yaml").read_text(encoding="utf-8")
    return {k: (v.split(". ")[0].rstrip(".") if isinstance(v, str) else "")
            for k, v in (yaml.safe_load(text) or {}).items()}


def generic(path: list[str]) -> str:
    return ".".join("<name>" if i and path[i - 1] in NAMED else part for i, part in enumerate(path))


def paths(node, prefix=()) -> set[str]:
    """Every dotted path (names generalised) a YAML document sets."""
    found = set()
    if isinstance(node, dict):
        for k, v in node.items():
            p = [*prefix, str(k)]
            found.add(generic(p))
            found |= paths(v, p)
    return found


def team_config(usecase: str, env: str) -> tuple[dict, set[str]]:
    """The team's own settings as written (usecase.yaml and its includes), and the paths the environment's
    override file sets."""
    folder = ROOT / "usecases" / usecase
    spec = yaml.safe_load((folder / "usecase.yaml").read_text(encoding="utf-8"))["spec"]
    for pattern in spec.get("include") or []:
        for part in sorted(folder.glob(pattern)):
            spec.update(yaml.safe_load(part.read_text(encoding="utf-8")) or {})
    override = folder / "environments" / f"{env}.yaml"
    overridden = paths(yaml.safe_load(override.read_text(encoding="utf-8")) or {}) if override.is_file() else set()
    return spec, overridden


def written(spec: dict, path: list[str]):
    node = spec
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def scalar(v) -> str:
    text = yaml.safe_dump(v, default_flow_style=True, width=1000, sort_keys=False).strip()
    return text.removesuffix("...").strip()


def emit(node, path, own, overridden, known, out, indent, shown):
    pad = "  " * indent
    for key, value in node.items():
        p = [*path, str(key)]
        g = generic(p)
        under_named = any(g.startswith(k + ".") for k in known if k.endswith("<name>"))
        if g in DERIVED or (g not in known and not under_named and not (path and path[-1] in NAMED)):
            continue
        shown.add(g)
        mine = written(own, p)
        if g in overridden and not isinstance(value, dict):
            mark = f"  # environments/{ENV}.yaml"
        elif mine is not None or any(t.startswith(g + ".") for t in overridden):
            mark = ""
            if mine is not None and not isinstance(value, dict):
                value = mine                       # as the team wrote it, ${...} references included
        else:
            mark = "  # default"
        if value is None:                          # not set: shown, but a use case cannot say null
            out.append(f"{pad}# {key}:  # not set by default")
        elif isinstance(value, dict) and value:
            out.append(f"{pad}{key}:{mark}")
            emit(value, p, own, overridden, known, out, indent + 1, shown)
        elif isinstance(value, list) and value and any(isinstance(x, dict) for x in value):
            out.append(f"{pad}{key}:{mark}")
            for item in value:
                line = f"{pad}  - {scalar(item)}"
                if len(line) <= WIDTH or not isinstance(item, dict):
                    out.append(line)
                else:                              # too wide for a page: one key per line
                    for i, (k, v) in enumerate(item.items()):
                        out.append(f"{pad}  {'- ' if i == 0 else '  '}{k}: {scalar(v)}")
            shown.update(f"{g}.{k}" for item in value if isinstance(item, dict) for k in item)
        else:
            line = f"{pad}{key}: {scalar(value)}"
            if len(line + mark) <= WIDTH:
                out.append(line + mark)
            elif isinstance(value, list):          # too wide for a page: one item per line
                out.append(f"{pad}{key}:{mark}")
                out.extend(f"{pad}  - {scalar(item)}" for item in value)
            else:                                  # the mark on its own line above
                out += [f"{pad}#{mark.lstrip().lstrip('#')}", line]


parser = argparse.ArgumentParser()
parser.add_argument("--env", required=True)
parser.add_argument("--usecase", required=True)
args = parser.parse_args()
ENV = args.env
text = subprocess.run(["pipewright", "resolve", "--env", args.env, "--usecase", args.usecase], cwd=ROOT,
                      capture_output=True, text=True, check=True).stdout
resolved = next(d for d in yaml.safe_load_all(text) if d)
(own, overridden), known = team_config(args.usecase, args.env), documented()
spec = {k: resolved[k] for k in ORDER if k in resolved}

out = [f"# Every setting of {args.usecase}, as `pipewright resolve --env {args.env}` runs it.",
       "# No mark: the team's own value, as written.",
       "# `# default`: what Pipewright uses when the key is left out.",
       f"# `# environments/{args.env}.yaml`: set for this environment only.",
       "# The platform's values (runner, dataset, landing prefix) are in the manifest.",
       "# Written by tools/all_settings.py. `pipewright explain <key>` explains a key.",
       "apiVersion: pipewright/v1", "kind: UseCase", "metadata:",
       f"  name: {resolved['usecase']}", f"  owner: {resolved['owner']}", "spec:"]
shown: set[str] = set()
emit(spec, [], own, overridden, known, out, 1, shown)

# The settings this use case does not use at all, each with what it is for: the rest of the range.
unused = sorted(k for k in known if k not in shown and k.split(".")[0] not in NOT_LISTED)
tops = [k for k in unused if not any(k.startswith(u + ".") for u in unused if u != k)]
out += ["", "# Also available, not used by this use case (see `pipewright explain`):"]
for k in tops:
    n = sum(1 for u in unused if u.startswith(k + "."))
    count = f" ({n} key{'s' if n > 1 else ''})" if n else ""
    head = f"#   {k}{count}: "
    room = max(WIDTH - len(head), 24)                 # one line each, readable in print
    what = known[k] if len(known[k]) <= room else known[k][:room - 4].rsplit(" ", 1)[0] + " ..."
    out.append(head + what)
sys.stdout.write("\n".join(out) + "\n")
