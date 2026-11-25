"""Steps for the pins of other packages' releases (releases.py): `pubrules
new` and the nightly, run in this process so GitHub's answers are stand-ins.
The repository, the release state and the checks are conftest's and
pubtest's."""

from __future__ import annotations

import json
import re

from pytest_bdd import given, parsers, scenarios, then, when

from pubrules import cli, new, nightly

scenarios("releases.feature")


@given(parsers.parse('GitHub\'s latest release of "{slug}" is "{tag}"'))
def latest(monkeypatch, slug, tag):
    monkeypatch.setattr(nightly, "latest_release", lambda repo: tag if repo == slug else None)
    nightly.latest_tag.cache_clear()


@given(parsers.parse('release "{tag}" of "{slug}" carries "{file}"'))
def carries(monkeypatch, tag, slug, file):
    monkeypatch.setattr(nightly, "release_assets", lambda repo, at: [file] if (repo, at) == (slug, tag) else None)
    nightly.release_wheel.cache_clear()


@given(parsers.parse('the release state lists "{name}" with the wheel "{file}" at "{version}"'))
def release_state_wheel(release_state, name, file, version):
    data = json.loads(release_state.read_text())
    data["releases"][name] = {"version": version, "wheel": file}
    release_state.write_text(json.dumps(data))


@given(parsers.parse('the release state lists "{name}" at "{version}" with no wheel'))
def release_state_bare(release_state, name, version):
    data = json.loads(release_state.read_text())
    data["releases"][name] = version
    release_state.write_text(json.dumps(data))


@given(parsers.parse('PyPI\'s newest release of "{name}" is "{version}"'))
def pypi_release(pypi_pages, name, version):
    """PyPI's JSON API answer for `name`: beside it, a pre-release, a newer
    release whose only file is yanked and one with no files, none of which
    counts."""
    file, yanked = {"yanked": False}, {"yanked": True}
    pypi_pages[f"https://pypi.org/pypi/{name}/json"] = json.dumps({"releases": {
        "0.4.0": [file], version: [file], "0.5.0rc1": [file], "9.0.0": [yanked], "9.0.1": []}})


@given(parsers.parse('pubrules.json\'s PyPI mirror lists "{a}" and "{b}"'))
def pypi_mirror_lists(pypi_pages, repo, a, b):
    """A PyPI mirror's simple index page for the files' package."""
    name = a.split("-", 1)[0]
    pypi_pages[f"https://storage.example/pypi/simple/{name}/"] = "".join(
        f'<a href="../../f/{f}">{f}</a>\n' for f in (a, b))
    config = json.loads((repo / "pubrules.json").read_text())
    config["mirror"] = {"pypi": "https://storage.example/pypi"}
    (repo / "pubrules.json").write_text(json.dumps(config))


@given(parsers.parse('GitHub has no release of "{slug}"'))
def no_release(monkeypatch, slug):
    monkeypatch.setattr(nightly, "latest_release", lambda repo: None)
    nightly.latest_tag.cache_clear()


@given(parsers.parse('each wheel fetched hashes to "{sha}"'))
def hashes_to(monkeypatch, sha):
    monkeypatch.setattr(cli, "sha256_of", lambda url: sha)


@given("a service repository")
def service(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert cli.main(["init", "--kind=service", "--project=example"]) == 0
    capsys.readouterr()


@when(parsers.parse('I start the package "{name}"'), target_fixture="result")
def start(pubtest_ctx, repo, monkeypatch, name):
    monkeypatch.setattr(new, "check_tools", lambda: [])
    pubtest_ctx.attempt(lambda: exits(new.run(repo, name, f"PKG-{name.upper():<6.6}-10-2026".replace(" ", "X"),
                                              "", owner="example-org", key=False, lock=False)))
    return pubtest_ctx.outcome


@when("the nightly moves the repository's pins", target_fixture="moves")
def moves(repo, monkeypatch):
    monkeypatch.chdir(repo)
    moved = nightly.pins(repo, "", lock=False)
    nightly.latest_tag.cache_clear()
    return moved


@then(parsers.parse('the moves include "{line}"'))
def moves_include(moves, line):
    assert line in moves, moves


def exits(code):
    """A command's return, as the program's exit: what pubtest reads."""
    raise SystemExit(code)


@then("the pubtest tests/requirements.txt pins is one tests/requirements-pubrules.txt takes")
def pin_meets_floor(repo):
    """What `pubrules lock` needs to resolve: the pinned release is at
    least the pubtest floor the managed requirements-pubrules.txt names."""
    pinned = re.search(r"^pubtestrules==([0-9.]+)$", (repo / "tests/requirements.txt").read_text(), re.M)[1]
    floor = re.search(r"^pubtestrules>=([0-9.]+)$", (repo / "tests/requirements-pubrules.txt").read_text(), re.M)[1]
    assert tuple(map(int, pinned.split("."))) >= tuple(map(int, floor.split("."))), (pinned, floor)


@when(parsers.re(r"pubrules reads the pubtest floor from a template holding (?P<lines>(?:\"[^\"]*\"(?: and )?)+)$"),
      target_fixture="floor")
def floor_from(lines):
    text = "".join(f"{line}\n" for line in lines.strip('"').split('" and "'))
    try:
        return {"floor": cli.floor_in(text)}
    except SystemExit as stop:
        return {"stopped": str(stop.code)}


@when("pubrules reads the pubtest floor of the template it ships", target_fixture="floor")
def floor_shipped():
    return {"floor": cli.pubtest_floor()}


@then(parsers.parse('the floor is "{version}"'))
def floor_is(floor, version):
    assert floor == {"floor": version}, floor


@then(parsers.parse('it stops, saying "{text}"'))
def floor_stops(floor, text):
    assert text in floor.get("stopped", ""), floor


@then('the floor is the version on its "# pubtest floor:" line')
def floor_shipped_is(floor):
    from importlib import resources  # noqa: PLC0415
    text = (resources.files("pubrules") / "templates" / "common" / "tests" / "requirements-pubrules.txt").read_text()
    assert f"# pubtest floor: {floor['floor']}\n" in text, floor


@given(parsers.parse('there is no "{path}"'))
def no_file(repo, path):
    (repo / path).unlink(missing_ok=True)
