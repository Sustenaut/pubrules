Feature: The reusable workflows parse as GitHub reads them
  pubrules' own CI runs only python-ci.yml, so a malformed rust-ci.yml would
  first fail in someone else's repository. Every workflow it ships is parsed
  here instead.

  Scenario Outline: A reusable workflow declares well-formed inputs
    When I parse the workflow "<workflow>"
    Then it is called with workflow_call
    And every input has only a type, a default, a description or required
    And every job the workflow runs uses only its declared inputs

    Examples:
      | workflow                  |
      | rust-ci.yml               |
      | python-ci.yml             |
      | service-ci.yml            |
      | node-ci.yml               |
      | job-node-test.yml         |
      | job-node-browser.yml      |
      | job-node-audit.yml        |
      | job-python-functional.yml |
      | job-python-browser.yml    |
      | job-python-audit.yml      |
      | job-python-lint.yml       |
      | job-sonar.yml             |
      | job-rust-gates.yml        |
      | job-rust-test.yml         |
      | job-rust-functional.yml   |
      | job-rust-fuzz.yml         |
      | job-rust-cross.yml        |
      | job-rust-audit.yml        |
      | job-rust-toolchains.yml   |
      | job-service-checks.yml    |
      | job-service-terraform.yml |
      | job-service-tests.yml     |

  Scenario Outline: A reusable workflow ends in the one check a ruleset requires
    When I parse the workflow "<workflow>"
    Then its "passed" job always runs and needs every other job

    Examples:
      | workflow      |
      | rust-ci.yml   |
      | python-ci.yml |
      | service-ci.yml |
      | node-ci.yml   |

  Scenario: rust-ci runs the targets pubrules required plans, in every job
    When I parse the workflow "rust-ci.yml"
    Then every job pubrules required plans for reads its targets from the plan job
    And the gates and functional inputs only add targets

  Scenario: rust-ci's plan hands the event, the branch and the changed files to pubrules
    When I parse the workflow "rust-ci.yml"
    Then the plan job compares a pull request with its base and passes it to pubrules required

  Scenario: The sonar job's layout comes before sonar-args, so a repository's own properties win
    When I parse the workflow "job-sonar.yml"
    Then the scan's layout comes before sonar-args and pubrules.json's sonar args

  Scenario: The sonar job keeps the coverage reports out of the code it analyses
    When I parse the workflow "job-sonar.yml"
    Then the coverage reports are downloaded outside the checkout, and the scan finds them there

  Scenario Outline: A package's reusable workflow sends its code to SonarQube Cloud when given a token
    When I parse the workflow "<workflow>"
    Then it takes an optional SONAR_TOKEN secret
    And its "sonar" job runs the pinned SonarQube scan only when the token is set
    And the scan names the project OWNER_REPO in the organization owner, lower-cased unless pubrules.json names it
    And without a token it warns, unless the pull request comes from a fork
    And the scan waits for the quality gate, so a failing gate fails the job

    Examples:
      | workflow      |
      | rust-ci.yml   |
      | python-ci.yml |
      | node-ci.yml   |

  Scenario: The sonar job sends its code to SonarQube Cloud when given a token, and its gate step decides on the result
    When I parse the workflow "job-sonar.yml"
    Then it takes an optional SONAR_TOKEN secret
    And its "sonar" job runs the pinned SonarQube scan only when the token is set
    And the scan names the project OWNER_REPO in the organization owner, lower-cased unless pubrules.json names it
    And without a token it warns, unless the pull request comes from a fork
    And the gate step fails the job on a failed quality gate

  Scenario Outline: A package's reusable workflow gives SonarQube Cloud the tests' coverage
    When I parse the workflow "<workflow>"
    Then the "<job>" job hands its coverage report to the sonar scan as "<property>"

    Examples:
      | workflow      | job        | property                          |
      | python-ci.yml | functional | sonar.python.coverage.reportPaths |
      | rust-ci.yml   | functional | sonar.rust.lcov.reportPaths       |
      | rust-ci.yml   | functional | sonar.python.coverage.reportPaths |
      | node-ci.yml   | test       | sonar.javascript.lcov.reportPaths |
      | python-ci.yml | browser    | sonar.python.coverage.reportPaths |
      | node-ci.yml   | browser    | sonar.javascript.lcov.reportPaths |

  Scenario Outline: A package's reusable workflow scans only once the browser tests' coverage is in
    When I parse the workflow "<workflow>"
    Then the sonar job waits for the browser job, and runs when it was skipped

    Examples:
      | workflow      |
      | python-ci.yml |
      | node-ci.yml   |

  Scenario: rust-ci measures coverage with the functional targets only when there is a scan to send it to
    When I parse the workflow "rust-ci.yml"
    Then the functional job runs make coverage in place of make functional when given a SONAR_TOKEN
    And the token itself never reaches the functional job

  Scenario Outline: Every action a workflow uses is pinned to a commit
    When I parse the workflow "<workflow>"
    Then every action it uses is pinned to a full commit hash, with its version in a comment

    Examples:
      | workflow       |
      | ci.yml         |
      | rust-ci.yml    |
      | python-ci.yml  |
      | service-ci.yml |
      | node-ci.yml    |
      | job-node-test.yml         |
      | job-node-browser.yml      |
      | job-node-audit.yml        |
      | job-python-functional.yml |
      | job-python-browser.yml    |
      | job-python-audit.yml      |
      | job-python-lint.yml       |
      | job-osv.yml               |
      | job-review.yml            |
      | job-sonar.yml             |
      | job-rust-gates.yml        |
      | job-rust-test.yml         |
      | job-rust-functional.yml   |
      | job-rust-msrv.yml         |
      | job-rust-fuzz.yml         |
      | job-rust-cross.yml        |
      | job-rust-audit.yml        |
      | job-rust-toolchains.yml   |
      | job-service-checks.yml    |
      | job-service-terraform.yml |
      | job-service-tests.yml     |

  Scenario: node-ci installs dependencies without running their scripts
    When I parse the workflow "node-ci.yml"
    Then its setup input runs npm ci with --ignore-scripts
    And its browser-setup input runs npx with --no-install

  Scenario Outline: A package's reusable workflow checks advisories on every run, with no switch
    When I parse the workflow "<workflow>"
    Then its "audit" job runs "<check>" on every event
    And no input turns the audit job off

    Examples:
      | workflow      | check                                      |
      | node-ci.yml   | npm audit --package-lock-only              |
      | python-ci.yml | pypa/gh-action-pip-audit                   |

  Scenario: rust-ci fuzzes long on a schedule unless pubrules.json turns the long run off
    When I parse the workflow "rust-ci.yml"
    Then its fuzz job reads security.fuzz.rust from pubrules.json on a scheduled run

  Scenario Outline: A package's reusable workflow tries more property-test inputs on a schedule unless pubrules.json says not to
    When I parse the workflow "<workflow>"
    Then its "<job>" job sets PUBRULES_FUZZ_RUNS before its tests, from security.fuzz.<language> on a scheduled run

    Examples:
      | workflow      | job        | language |
      | python-ci.yml | functional | python   |
      | node-ci.yml   | test       | node     |

  Scenario Outline: A package's reusable workflow scans every lockfile with OSV-Scanner and reviews new dependencies
    When I parse the workflow "<workflow>"
    Then its "osv" job runs "google/osv-scanner-action" on every event
    And its "review" job runs dependency review on public pull requests only
    And its passed job lets the review job be skipped

    Examples:
      | workflow      |
      | rust-ci.yml   |
      | node-ci.yml   |
      | python-ci.yml |

  # pubrules.json's "pubtest": {"cassettes": true} gives every job that runs
  # the suite data-repo: it reads the private <owner>/<repo>-data with a
  # read-only token of the release app, and puts it where pubtest looks.

  Scenario Outline: A job that runs the suite reads the data repository with a read-only token of the release app
    When I parse the workflow "<workflow>"
    Then it takes data-repo, off by default, and the release app's RELEASE_APP_ID and RELEASE_APP_KEY, optional
    And its "<job>" job, given data-repo, mints the release app's token for the owner's data repository alone, to read its contents
    And its "<job>" job checks the data repository out with that token, keeping no credentials, into the workspace
    And its "<job>" job moves the data repository beside the checkout before it runs the suite

    Examples:
      | workflow                  | job        |
      | job-node-test.yml         | test       |
      | job-node-browser.yml      | browser    |
      | job-python-functional.yml | functional |
      | job-python-browser.yml    | browser    |
      | job-rust-functional.yml   | functional |
      | job-service-tests.yml     | tests      |
      | node-ci.yml               | test       |
      | node-ci.yml               | browser    |
      | python-ci.yml             | functional |
      | python-ci.yml             | browser    |
      | service-ci.yml            | tests      |

  Scenario: With the release app's id and key, the data step names the data repository and passes
    When the data step runs with the release app's id and key, on a pull request from "Sustenaut/demo" to "Sustenaut/demo"
    Then the step passes, naming the data repository "demo-data"

  Scenario Outline: Without the release app's id or key, the data step fails saying what to set
    When the data step runs with <given>, on a pull request from "Sustenaut/demo" to "Sustenaut/demo"
    Then the step fails, with an error that names "<missing>"
    And the error says how to set them: "./with-secrets ./pubsec app-secrets"
    And the error names the data repository "Sustenaut/demo-data"

    Examples:
      | given                     | missing                         |
      | the release app's key     | RELEASE_APP_ID                  |
      | the release app's id      | RELEASE_APP_KEY                 |
      | neither                   | RELEASE_APP_ID RELEASE_APP_KEY  |

  Scenario Outline: A pull request GitHub gives no secrets fails the data step, saying why, rather than pass untested
    When the data step runs with neither, on a pull request from "<head>" to "Sustenaut/demo"<by>
    Then the step fails, with an error that names "<from>"
    And the error says "The job fails rather than pass untested"
    And the error does not say "./with-secrets"

    Examples:
      | head            | by                     | from                     |
      | someone/demo    |                        | the fork someone/demo    |
      | Sustenaut/demo  | , by "dependabot[bot]" | Dependabot               |

  Scenario: The data repository goes beside the checkout, where pubtest finds its cassettes
    When the step that moves the data repository runs after a checkout of it
    Then the data repository is beside the checkout, named as the checkout with -data
    And pubtest finds its cassettes in it, under integrations/cassettes

  Scenario: A data repository the release app could not read fails the job, saying what to do
    When the step that moves the data repository runs after the token step failed
    Then the step fails, with an error that names "there is no such repository, or the app is not installed on it"
    And the error says how to make one: "pubtest record --all --create-data-repo"
