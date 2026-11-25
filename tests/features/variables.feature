Feature: A repository's pubrules.json names the GitHub variables it reads, and their defaults, in a block sync checks
  The values are in the owner's state file, which pubfleet's variables command
  keeps GitHub to; a default is the code's own constant, what the repository does
  when nothing sets the variable. pubrules checks the block's shape, of version 1
  (names and deploy) or 2 (with its version and defaults), and reads version 1 as 2.

  Scenario Outline: sync refuses a variables block of the wrong shape
    Given a repository initialised as "utility"
    And its pubrules.json's variables block is "<block>"
    When I run pubrules "sync" "--check"
    Then the exit code is 1
    And it warns "<message>"

    Examples:
      | block                                        | message                              |
      | ["SOME"]                                     | it must be an object                 |
      | {}                                           | "names" must list at least one       |
      | {"names": ["SOME", "SOME"]}                  | lists a variable twice               |
      | {"names": ["some"]}                          | "some" is not a variable's name      |
      | {"names": ["SOME"], "deploy": "../x.yml"}    | "deploy" must be a workflow's file   |
      | {"names": ["SOME"], "other": 1}              | other is not a setting               |
      | {"version": 3, "names": ["SOME"]}            | its "version" must be 2              |
      | {"version": true, "names": ["SOME"]}         | its "version" must be 2              |
      | {"defaults": {"SOME": "1"}, "names": ["SOME"]} | defaults is not a setting; version 1 takes deploy, names |
      | {"version": 2, "names": ["SOME"], "defaults": []} | "defaults" must be an object      |
      | {"version": 2, "names": ["SOME"], "defaults": {"OTHER": "1"}} | "defaults" gives "OTHER" a default, which "names" doesn't list |
      | {"version": 2, "names": ["SOME"], "other": 1} | other is not a setting; version 2 takes defaults, deploy, names |

  Scenario Outline: sync takes a variables block of either version: <case>
    Given a repository initialised as "utility"
    And its pubrules.json's variables block is "<block>"
    When I run pubrules "sync" "--check"
    Then it does not warn "variables block"

    Examples:
      | case                         | block                                                                                     |
      | version 1                    | {"names": ["SOME"], "deploy": "deploy.yml"}                                                |
      | version 2, no defaults       | {"version": 2, "names": ["SOME"]}                                                          |
      | version 2, a string default  | {"version": 2, "names": ["SOME", "OTHER"], "defaults": {"SOME": "120"}}                    |
      | version 2, a null default    | {"version": 2, "names": ["SOME"], "defaults": {"SOME": null}}                              |
      | version 2, a JSON default    | {"version": 2, "names": ["SOME"], "defaults": {"SOME": {"b": [1, 2], "a": true}}}          |

  Scenario: Version 1 is read as version 2, with no defaults
    When the variables block '{"names": ["SOME", "OTHER"], "deploy": "deploy.yml"}' is upgraded
    Then the result is:
      """
      {"version": 2, "names": ["SOME", "OTHER"], "deploy": "deploy.yml", "defaults": {}}
      """

  Scenario: Version 2 is read as it is
    When the variables block '{"version": 2, "names": ["SOME"], "defaults": {"SOME": null}}' is upgraded
    Then the result is:
      """
      {"version": 2, "names": ["SOME"], "defaults": {"SOME": null}}
      """

  Scenario: A version there is no step from is left for the check to say
    When the variables block '{"version": 9, "names": ["SOME"]}' is upgraded
    Then the result is:
      """
      {"version": 9, "names": ["SOME"]}
      """

  Scenario: A block's defaults, of either version
    When the defaults of the variables block '{"version": 2, "names": ["A", "B"], "defaults": {"A": "120", "B": null}}' are read
    Then the result is:
      """
      {"A": "120", "B": null}
      """
    When the defaults of the variables block '{"names": ["A"]}' are read
    Then the result is "{}"

  Scenario Outline: Defaults compare canonically, however spaced or ordered
    When "<a>" and "<b>" are compared canonically
    Then the result is "<same>"

    Examples:
      | a                       | b                         | same  |
      | {"a": 1, "b": [1, 2]}   | {"b":[1,2],"a":1}         | true  |
      | "120"                   | "120"                     | true  |
      | "120"                   | 120                       | false |
      | null                    | ""                        | false |
