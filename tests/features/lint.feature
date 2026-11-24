Feature: A repository that lints is held to one Python standard
  A Python package or a service turns the lint job on with one setting, a
  lint command in its ci block's `with` ("lint": "make lint"). Then pubrules
  manages pubrules-ruff.toml, the shared Ruff rules (line length 120,
  bugbear, simplify, pyupgrade, isort and pylint's size limits), and pins
  Ruff beside it in tests/requirements-pubrules.txt, so the rules and the
  tool move together. pyproject.toml takes the rules in with [tool.ruff]
  extend, and may make them stricter, never looser; sync --check holds
  every repository that lints to it.

  Scenario Outline: A lint command brings the shared rules and the Ruff that reads them
    Given a <kind> repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is 'extend = "pubrules-ruff.toml"'
    When I run pubrules "sync"
    Then it succeeds
    And the repository has "pubrules-ruff.toml"
    And "pubrules-ruff.toml" is the shared Python standard, managed by this pubrules
    And tests/requirements-pubrules.txt pins the Ruff pubrules-ruff.toml is written for
    When I run pubrules "sync" "--check"
    Then stderr does not mention "pubrules-ruff.toml"
    And stderr does not mention "ruff"

    Examples:
      | kind    |
      | Python  |
      | service |

  Scenario Outline: Without a lint command there are no shared rules and no Ruff
    Given a <kind> repository that does not lint
    When I run pubrules "sync"
    Then the file "pubrules-ruff.toml" does not exist
    And tests/requirements-pubrules.txt names no Ruff

    Examples:
      | kind    |
      | Python  |
      | service |

  Scenario: An edited pubrules-ruff.toml fails the check, and sync restores it
    Given a service repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is 'extend = "pubrules-ruff.toml"'
    And pubrules "sync" has run
    And a file "pubrules-ruff.toml" holding "line-length = 200"
    When I run pubrules "sync" "--check"
    Then it fails
    And stderr mentions "pubrules-ruff.toml differs from pubrules"
    When I run pubrules "sync"
    Then "pubrules-ruff.toml" is the shared Python standard, managed by this pubrules

  Scenario Outline: A pyproject.toml that does not take the rules in fails the check
    Given a service repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is '<ruff>'
    When I run pubrules "sync"
    And I run pubrules "sync" "--check"
    Then it fails
    And stderr mentions "pyproject.toml must take in the Python standard with [tool.ruff] extend = \"pubrules-ruff.toml\""

    Examples:
      | ruff                         |
      | line-length = 120            |
      | extend = "ruff.toml"         |

  Scenario: A lint command without a pyproject.toml fails the check
    Given a service repository that lints with "make lint"
    When I run pubrules "sync"
    And I run pubrules "sync" "--check"
    Then it fails
    And stderr mentions "there is no pyproject.toml"

  Scenario Outline: A pyproject.toml that loosens the shared rules fails the check
    Given a service repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is 'extend = "pubrules-ruff.toml"\n<setting>'
    When I run pubrules "sync"
    And I run pubrules "sync" "--check"
    Then it fails
    And stderr mentions "pyproject.toml's [tool.ruff] sets <name>, which is pubrules-ruff.toml's"

    Examples:
      | setting                          | name               |
      | line-length = 88                 | line-length        |
      | lint.select = ["F"]              | lint.select        |
      | lint.ignore = ["B"]              | lint.ignore        |
      | lint.extend-ignore = ["SIM"]     | lint.extend-ignore |
      | ignore = ["E7"]                  | ignore             |

  Scenario: A pyproject.toml may make the rules stricter and name the files a rule does not fit
    Given a service repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is 'extend = "pubrules-ruff.toml"\nlint.extend-select = ["N"]\nlint.per-file-ignores = {"tests/*" = ["PLR0913"]}'
    When I run pubrules "sync"
    Then it succeeds
    When I run pubrules "sync" "--check"
    Then stderr does not mention "pyproject.toml"

  Scenario: A lock without the pinned Ruff fails the check until pubrules lock
    Given a service repository that lints with "make lint"
    And its pyproject.toml's [tool.ruff] is 'extend = "pubrules-ruff.toml"'
    And a lock that pins this pubrules and no Ruff
    When I run pubrules "sync"
    Then it prints "now run `pubrules lock`"
    When I run pubrules "sync" "--check"
    Then it fails
    And stderr mentions "does not pin ruff"
    Given a lock that pins this pubrules and the Ruff pubrules-ruff.toml is written for
    When I run pubrules "sync" "--check"
    Then stderr does not mention "ruff"
