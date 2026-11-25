"""Steps for the variables block's shape, which `pubrules sync --check` checks."""

from __future__ import annotations

import json

from pytest_bdd import given, parsers, scenarios, then, when

from pubrules import variables

scenarios("variables.feature")


@given(parsers.re(r"its pubrules.json's variables block is \"(?P<text>.+)\"$"))
def variables_block(repo, text):
    path = repo / "pubrules.json"
    config = json.loads(path.read_text())
    path.write_text(json.dumps({**config, "variables": json.loads(text)}))


@then(parsers.parse('it warns "{text}"'))
def warns(result, text):
    assert text in result.stderr, result.stderr


@then(parsers.parse('it does not warn "{text}"'))
def does_not_warn(result, text):
    assert text not in result.stderr, result.stderr


@when(parsers.parse("the variables block '{text}' is upgraded"))
def upgraded(pubtest_ctx, text):
    pubtest_ctx.attempt(lambda: variables.upgrade(json.loads(text)))


@when(parsers.parse("the defaults of the variables block '{text}' are read"))
def defaults_read(pubtest_ctx, text):
    pubtest_ctx.attempt(lambda: variables.defaults(json.loads(text)))


@when(parsers.parse('"{a}" and "{b}" are compared canonically'))
def compared(pubtest_ctx, a, b):
    pubtest_ctx.attempt(lambda: variables.canonical(json.loads(a)) == variables.canonical(json.loads(b)))
