"""Steps for pubrules.api, the surface pubfleet and pubhost import: its names
and their shapes, against the fixture that records them."""

from __future__ import annotations

import ast
import difflib
import importlib
import inspect
import re
from pathlib import Path

from pytest_bdd import scenarios, then, when

scenarios("api.feature")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "api.txt"
SOURCE = ROOT / "src" / "pubrules"


def shape(value) -> str:
    """What a sibling relies on in `value`: a function's signature, a class's
    bases and public methods, a pattern's text and flags, a constant's value."""
    if isinstance(value, re.Pattern):
        return f"pattern {value.pattern!r} flags={int(value.flags)}"
    if inspect.isclass(value):
        bases = ", ".join(b.__name__ for b in value.__bases__)
        own = [f"{name}{inspect.signature(member)}" for name, member in sorted(vars(value).items())
               if inspect.isfunction(member) and (name == "__init__" or not name.startswith("_"))]
        return f"class({bases}) " + "; ".join(own)
    if inspect.isfunction(value):
        return f"function{inspect.signature(value)}"
    if isinstance(value, (str, int, float, bool)):
        return f"constant {value!r}"
    return f"type {value!r}"


def recorded() -> str:
    """The fixture's lines, without its header of # comments."""
    return "".join(line for line in FIXTURE.read_text(encoding="utf-8").splitlines(True)
                   if not line.startswith("#"))


@when("I read the shape of every name pubrules.api exports", target_fixture="surface")
def surface():
    api = importlib.import_module("pubrules.api")
    assert len(api.__all__) == len(set(api.__all__)), "pubrules.api.__all__ names one twice"
    # The version moves with every release; what a sibling relies on is that it is a str.
    return {name: "str, the installed version" if name == "version" and isinstance(api.version, str)
            else shape(getattr(api, name, None)) for name in api.__all__}


@then("it is the shape tests/fixtures/api.txt records")
def as_recorded(surface):
    now = "".join(f"{name}: {surface[name]}\n" for name in sorted(surface))
    if now != recorded():
        diff = "".join(difflib.unified_diff(recorded().splitlines(True), now.splitlines(True),
                                            "tests/fixtures/api.txt", "pubrules.api"))
        raise AssertionError(
            "pubrules.api changed, and pubfleet and pubhost import it. If the change is meant,\n"
            "write the lines after + below to tests/fixtures/api.txt in place of those after -,\n"
            "and record the change with pubrel add (removed or changed for a name dropped or\n"
            "reshaped, added for a new one).\n" + diff)


@then("each name is importable from pubrules.api")
def importable(surface):
    for name in surface:
        exec(f"from pubrules.api import {name}", {})  # noqa: S102 - the names are pubrules' own


@when("I read every import in src/pubrules", target_fixture="imports")
def imports():
    found = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path.name == "api.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                module = ("." * node.level) + (node.module or "")
                found += [(path, module, a.name) for a in node.names]
            elif isinstance(node, ast.Import):
                found += [(path, a.name, "") for a in node.names]
    assert found
    return found


@then("none is of pubrules.api")
def none_of_api(imports):
    bad = [f"{path.relative_to(ROOT)}: {module} {name}".strip() for path, module, name in imports
           if module in ("pubrules.api", ".api") or (module in ("pubrules", ".") and name == "api")]
    assert not bad, "pubrules.api is for sibling packages; import the name from its own module:\n" + "\n".join(bad)
