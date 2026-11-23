Feature: The sonar job tells a failed quality gate from SonarQube Cloud being down
  The scanner reports both alike, so the job's scan does not wait for the
  gate, and its next step asks SonarQube Cloud. A gate that failed, or any
  refusal, fails the job whatever the pull request carries. When
  SonarQube Cloud gives no answer (it cannot be reached, answers 5xx, or
  does not finish in time) after three tries, the job fails too, unless the
  pull request carries the label sonar-down: then it passes with a warning
  and a note in the job's summary that the commit was not analysed. Each
  scenario runs the job's gate step as GitHub does, with a stub curl that
  answers SonarQube Cloud's API from the scenario, and a sleep that only
  records how long it was asked to wait.

  Scenario: The gate passes
    Given the scan passed and the scanner wrote a report
    And the analysis task answers "SUCCESS"
    And the quality gate answers "OK"
    When the gate step runs
    Then the step passed
    And nothing was bypassed

  Scenario: An analysis that is still pending is asked about again
    Given the scan passed and the scanner wrote a report
    And the analysis task answers "PENDING" and then "SUCCESS"
    And the quality gate answers "OK"
    When the gate step runs
    Then the step passed
    And it slept 1 time

  Scenario: A failed gate fails the job, naming what failed
    Given the scan passed and the scanner wrote a report
    And the analysis task answers "SUCCESS"
    And the quality gate answers "ERROR" on "new_coverage"
    When the gate step runs
    Then the step failed with the error "quality gate failed on: new_coverage"

  Scenario: A failed gate is not bypassed by the label
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers "SUCCESS"
    And the quality gate answers "ERROR" on "new_coverage"
    When the gate step runs
    Then the step failed with the error "quality gate failed on: new_coverage"
    And nothing was bypassed

  Scenario: A gate with no conditions is not bypassed by the label
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers "SUCCESS"
    And the quality gate answers "NONE"
    When the gate step runs
    Then the step failed with the error "first analysis"
    And nothing was bypassed

  Scenario: An analysis SonarQube Cloud failed is not bypassed by the label
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers "FAILED"
    When the gate step runs
    Then the step failed with the error "ended FAILED"
    And nothing was bypassed

  Scenario: A refusal is not bypassed by the label
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers with 401
    When the gate step runs
    Then the step failed with the error "refused the analysis task (401)"
    And nothing was bypassed

  Scenario: A scan that failed while SonarQube Cloud answers is a real failure, not an outage
    Given the scan failed and the scanner wrote no report
    And the pull request carries the label sonar-down
    And SonarQube Cloud answers the version query with 404
    When the gate step runs
    Then the step failed with the error "SonarQube Cloud answers (404)"
    And nothing was bypassed

  Scenario: An outage fails the job, after three tries, and names the label
    Given the scan failed and the scanner wrote no report
    When the gate step runs
    Then the step failed with the error "gave no answer"
    And the error names the label "sonar-down"
    And it slept 2 times

  Scenario: An outage passes with a warning and a note for the label
    Given the scan failed and the scanner wrote no report
    And the pull request carries the label sonar-down
    When the gate step runs
    Then the step passed
    And it warned "this commit was NOT analysed"
    And the job's summary says SonarQube Cloud was bypassed

  Scenario: An analysis task that answers 5xx is an outage
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers with 503
    When the gate step runs
    Then the step passed
    And it warned "this commit was NOT analysed"
    And it slept 2 times

  Scenario: A quality gate that stops answering is an outage
    Given the scan passed and the scanner wrote a report
    And the analysis task answers "SUCCESS"
    And the quality gate does not answer
    When the gate step runs
    Then the step failed with the error "the quality gate does not answer"

  Scenario: An analysis that is not done in time is an outage
    Given the scan passed and the scanner wrote a report
    And the analysis task answers "PENDING"
    And the analysis may take 0 seconds
    When the gate step runs
    Then the step failed with the error "the analysis was not done after 0s"

  Scenario: An analysis that is not done in time passes for the label
    Given the scan passed and the scanner wrote a report
    And the pull request carries the label sonar-down
    And the analysis task answers "PENDING"
    And the analysis may take 0 seconds
    When the gate step runs
    Then the step passed
    And it warned "this commit was NOT analysed"

  Scenario: The scan uploads without waiting, and the label is read before the gate
    When I read the sonar job
    Then its scan step does not wait for the quality gate and may fail
    And its steps run in the order "label", "scan", "gate"
