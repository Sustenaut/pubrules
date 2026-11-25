"""The variables block of a repository's pubrules.json: the names of the GitHub
variables it reads, never an org's values, maybe the default each takes when nothing
sets it, and maybe the workflow that takes them in, to run once one changes.

Version 2:

    "variables": {"version": 2,
                  "names": ["INGEST_SWEEP_SECONDS", "SOME_MAP"],
                  "defaults": {"INGEST_SWEEP_SECONDS": "120"},
                  "deploy": "deploy.yml"}

Version 1, a block with no version, is names and deploy alone; `upgrade` reads it as
version 2 (TRANSFORMS, one step a version: version 1 gets `version: 2` and
`defaults: {}`), and every reader takes a block through it. `pubrules sync --check`
takes either, and refuses a block of the wrong shape.

A default is the code's own constant, what the repository does when the variable
is unset, never an org's value: those are the owner's state file's, which a control
plane keeps GitHub to, and which only override a default. It is any JSON value, as a
state file's variables are: a string, `null` (unset is a state of its own, such as
off), or JSON, compared canonically (`canonical`). Every name in `defaults` is one
of `names`.

A deploy renders a variable nothing sets as "", so whatever reads a defaulted
variable takes "" as unset, as it takes a variable that isn't there: the code's
default applies, never os.environ.get(NAME, default), which gives "" back.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

BLOCK = "variables"
VERSION = 2
NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
WORKFLOW = re.compile(r"[A-Za-z0-9_.-]+\.ya?ml")
KEYS = {1: {"names", "deploy"}, 2: {"version", "names", "defaults", "deploy"}}


def _v1_to_v2(block: dict) -> dict:
    """Version 1 to 2: the version, and no defaults yet."""
    return {"version": 2, **{k: v for k, v in block.items() if k != "version"}, "defaults": {}}


# Each version's step to the next; a block chains them up to VERSION.
TRANSFORMS: dict[int, Callable[[dict], dict]] = {1: _v1_to_v2}


def version_of(block: dict) -> Any:
    """A block's version: 1 when it names none."""
    return block.get("version", 1)


def upgrade(block: dict) -> dict:
    """The block at VERSION, through each version's transformer in turn. A block of a
    version there is no step from comes back as it is, for block_problems to say."""
    while isinstance(version_of(block), int) and not isinstance(version_of(block), bool) \
            and version_of(block) in TRANSFORMS:
        block = TRANSFORMS[version_of(block)](block)
    return block


def canonical(value: Any) -> str:
    """A JSON value as one string, however it was spaced or its keys ordered."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def defaults(block: dict) -> dict[str, Any]:
    """Each defaulted name's default, from a block of any version."""
    return dict(upgrade(block).get("defaults") or {})


def name_problem(name: Any) -> str | None:
    if not isinstance(name, str) or not NAME.fullmatch(name) or name.startswith("GITHUB_"):
        return f"{json.dumps(name)} is not a variable's name: upper case letters, digits and _, " \
               f"not starting GITHUB_"
    return None


def block_problems(block: Any) -> list[str]:
    """What is wrong with a pubrules.json's variables block: one phrase each."""
    if not isinstance(block, dict):
        return ['it must be an object, with "names" and maybe "defaults" and "deploy"']
    version = version_of(block)
    if version not in KEYS or isinstance(version, bool):
        return [f'its "version" must be 2 (or left out, for version 1), not {json.dumps(version)}']
    takes = KEYS[version]
    listed = ", ".join(sorted(takes - {"version"}))
    out = [f"{key} is not a setting; version {version} takes {listed}"
           for key in sorted(block.keys() - takes)]
    names = block.get("names")
    if not isinstance(names, list) or not names:
        out.append('"names" must list at least one variable')
        names = []
    else:
        out += [p for n in names if (p := name_problem(n))]
        if len(set(map(json.dumps, names))) != len(names):
            out.append('"names" lists a variable twice')
    if "defaults" in block:
        given = block["defaults"]
        if not isinstance(given, dict):
            out.append('"defaults" must be an object, from each name to the default it takes')
        else:
            for name in given:
                if name not in names:
                    out.append(f'"defaults" gives {json.dumps(name)} a default, which "names" doesn\'t list')
    if "deploy" in block and not (isinstance(block["deploy"], str) and WORKFLOW.fullmatch(block["deploy"])):
        out.append('"deploy" must be a workflow\'s file name, such as deploy.yml')
    return out
