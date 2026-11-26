"""Steps for what pubrules reads about secrets (secrets_config.py), and the
commands that moved to pubsec: the shared ones are conftest's."""

from __future__ import annotations

import json

from pytest_bdd import given, parsers, scenarios, then, when

from pubrules import secrets_config

scenarios("secrets-config.feature")

BLOCK = {"id": {"from": "the-app-id", "to": "THE_APP_ID"},
         "installation_id": {"from": "the-app-installation-id", "to": "THE_APP_INSTALLATION_ID"},
         "key": {"from": "the-app-key", "to": "THE_APP_KEY"}}


CLIENT_ID = {"from": "the-app-client-id", "to": "THE_APP_CLIENT_ID"}


@given(parsers.parse("its pubrules.json has a sound github_app block {which}"))
def sound(repo, which):
    config = json.loads((repo / "pubrules.json").read_text())
    config["github_app"] = {**BLOCK, "client_id": CLIENT_ID} if which == "with a client id" else BLOCK
    (repo / "pubrules.json").write_text(json.dumps(config))


@when(parsers.re(r'pubrules checks "(?P<value>[^"]*)" as a client_id'), target_fixture="verdict")
def check_client_id(value):
    return secrets_config.wrong_value("client_id", value)


@then(parsers.re(r'its verdict is (?P<expected>nothing|"[^"]+")$'))
def verdict_is(verdict, expected):
    if expected == "nothing":
        assert verdict is None, verdict
    else:
        assert verdict and verdict.startswith(expected.strip('"')), verdict


@given(parsers.parse("its pubrules.json's signing_keys is {block}"))
def block(repo, block):
    config = json.loads((repo / "pubrules.json").read_text())
    config["signing_keys"] = json.loads(block)
    (repo / "pubrules.json").write_text(json.dumps(config))
