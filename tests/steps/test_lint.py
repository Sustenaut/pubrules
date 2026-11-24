"""Steps for the lint job's Python standard: pubrules-ruff.toml and its Ruff."""

from __future__ import annotations

import json
import re
import tomllib

from pytest_bdd import given, parsers, scenarios, then

from pubrules import __version__, cli

scenarios("lint.feature")

# The coverage settings a Python package's check asks for, so its pyproject.toml
# fails on nothing but what a scenario sets.
COVERAGE = '[tool.coverage.run]\npatch = ["subprocess"]\nparallel = true\n'
HASH = "--hash=sha256:" + "0" * 64


@given(parsers.parse("a {kind} repository that does not lint"))
def does_not_lint(repo, kind):
    lints(repo, kind, None)


@given(parsers.parse('a {kind} repository that lints with "{command}"'))
def lints(repo, kind, command):
    config = {"kind": {"Python": "utility", "service": "service"}[kind],
              "ci": {"with": {"test": "make functional", **({"lint": command} if command else {})}}}
    if kind == "Python":
        config["ci"]["release"] = False
        (repo / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n\n' + COVERAGE)
    (repo / "pubrules.json").write_text(json.dumps(config))


@given(parsers.parse("its pyproject.toml's [tool.ruff] is '{ruff}'"))
def ruff_block(repo, ruff):
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n\n' + COVERAGE + "\n[tool.ruff]\n"
        + ruff.replace("\\n", "\n") + "\n")


@given(parsers.re(r"a lock that pins this pubrules and (?P<ruff>no Ruff|the Ruff pubrules-ruff\.toml is written for)"))
def lock(repo, ruff):
    lines = [f"pubrules=={__version__} \\\n    {HASH}\n"]
    if ruff.startswith("the"):
        lines.append(f"ruff=={cli.RUFF} \\\n    {HASH}\n")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "requirements.lock").write_text("".join(lines))


@then(parsers.parse('"{path}" is the shared Python standard, managed by this pubrules'))
def shared_standard(repo, path):
    text = (repo / path).read_text()
    assert text.startswith(f"# Managed by pubrules {__version__}:"), text[:80]
    rules = tomllib.loads(text)
    assert rules["line-length"] == 120
    assert {"F", "B", "SIM", "UP", "I", "PLR0913"} <= set(rules["lint"]["select"]), rules["lint"]


@then("tests/requirements-pubrules.txt pins the Ruff pubrules-ruff.toml is written for")
def pins_ruff(repo):
    text = (repo / "tests" / "requirements-pubrules.txt").read_text()
    assert re.search(rf"^ruff=={re.escape(cli.RUFF)}$", text, re.M), text


@then("tests/requirements-pubrules.txt names no Ruff")
def no_ruff(repo):
    text = (repo / "tests" / "requirements-pubrules.txt").read_text()
    assert not re.search(r"^ruff\b", text, re.M), text
