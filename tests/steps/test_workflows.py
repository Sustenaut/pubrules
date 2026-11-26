"""Steps parsing the workflows pubrules ships, as YAML, the way GitHub does."""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from pathlib import Path

import yaml

from pubrules import standard
from pytest_bdd import parsers, scenarios, then, when

scenarios("workflows.feature")

SOURCE = Path(__file__).resolve().parents[2]
WORKFLOWS = SOURCE / ".github" / "workflows"


@when(parsers.parse('I parse the workflow "{workflow}"'), target_fixture="workflow")
def parse(workflow):
    text = (WORKFLOWS / workflow).read_text()
    return {"text": text, "data": yaml.safe_load(text)}


def triggers(workflow):
    # YAML reads the bare key `on` as the boolean true.
    data = workflow["data"]
    return data.get("on", data.get(True))


@then("it is called with workflow_call")
def called(workflow):
    assert "workflow_call" in triggers(workflow)


@then("every input has only a type, a default, a description or required")
def inputs_well_formed(workflow):
    inputs = triggers(workflow)["workflow_call"]["inputs"]
    for name, spec in inputs.items():
        extra = set(spec) - {"type", "default", "description", "required"}
        assert not extra, f"input {name} has unexpected keys {extra}"


@then("every job the workflow runs uses only its declared inputs")
def inputs_declared(workflow):
    declared = set(triggers(workflow)["workflow_call"]["inputs"])
    used = set(re.findall(r"inputs\.([A-Za-z0-9_-]+)", workflow["text"]))
    assert used <= declared, f"undeclared inputs used: {used - declared}"


@then(parsers.parse('its "{name}" job always runs and needs every other job'))
def aggregate(workflow, name):
    jobs = workflow["data"]["jobs"]
    job = jobs[name]
    assert job.get("if") == "always()", job.get("if")
    assert set(job["needs"]) == set(jobs) - {name}, job["needs"]


@then("every job pubrules required plans for reads its targets from the plan job")
def jobs_read_plan(workflow):
    jobs = workflow["data"]["jobs"]
    outputs = jobs["plan"]["outputs"]
    for job in standard.JOBS:
        assert job in outputs, f"plan does not output {job}"
        assert f"needs.plan.outputs.{job}" in workflow["text"], f"no job reads {job}"
        assert "plan" in jobs[job]["needs"], f"{job} does not need plan"


@then("the gates and functional inputs only add targets")
def inputs_only_add(workflow):
    inputs = triggers(workflow)["workflow_call"]["inputs"]
    for name in ("gates", "functional"):
        assert inputs[name]["default"] == "", name
        assert f"EXTRA: '${{{{ inputs.{name} }}}}'" in workflow["text"], name
        assert f"REQUIRED: '${{{{ needs.plan.outputs.{name} }}}}'" in workflow["text"], name


@then("the plan job compares a pull request with its base and passes it to pubrules required")
def plan_passes_changes(workflow):
    steps = workflow["data"]["jobs"]["plan"]["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert checkout.get("with", {}).get("fetch-depth") == 2, checkout
    diff = next(s for s in steps if "git diff --name-only HEAD^1 HEAD" in s.get("run", ""))
    assert diff.get("if") == "github.event_name == 'pull_request'", diff
    required = next(s for s in steps if s.get("id") == "required")
    for flag in ("--event", "--head-ref", "--changed-files"):
        assert flag in required["run"], flag
    assert required["env"] == {"EVENT": "${{ github.event_name }}",
                               "HEAD_REF": "${{ github.head_ref }}"}


@then("it takes an optional SONAR_TOKEN secret")
def sonar_secret(workflow):
    secrets = triggers(workflow)["workflow_call"]["secrets"]
    assert secrets["SONAR_TOKEN"]["required"] is False


@then(parsers.parse('its "{name}" job runs the pinned SonarQube scan only when the token is set'))
def sonar_job(workflow, name):
    job = workflow["data"]["jobs"][name]
    assert job["env"] == {"SONAR_TOKEN": "${{ secrets.SONAR_TOKEN }}"}
    steps = job["steps"]
    scan = next(s for s in steps if s.get("uses", "").startswith("SonarSource/sonarqube-scan-action@"))
    assert scan["if"] == "env.SONAR_TOKEN != ''"
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["if"] == "env.SONAR_TOKEN != ''"
    assert checkout["with"]["fetch-depth"] == 0
    assert any(s.get("if") == "env.SONAR_TOKEN == ''" and "::notice::" in s["run"] for s in steps)


@then("the scan names the project OWNER_REPO in the organization owner, lower-cased unless pubrules.json names it")
def sonar_project(workflow):
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    args = next(s for s in steps if "sonarqube-scan-action" in s.get("uses", ""))["with"]["args"]
    assert "-Dsonar.organization=${{ steps.settings.outputs.organization }}" in args
    settings = next(s for s in steps if s.get("id") == "settings")
    assert ".security.sonar.organization" in settings["run"]
    assert 'organization=${organization:-${OWNER,,}}' in settings["run"]
    assert "2>/dev/null || true)" in settings["run"]  # no pubrules.json is no failure
    assert settings["env"]["OWNER"] == "${{ github.repository_owner }}"
    assert "-Dsonar.projectKey=${{ github.repository_owner }}_${{ github.event.repository.name }}" in args


@when(parsers.parse('I read the action "{name}"'), target_fixture="action")
def read_action(name):
    return yaml.safe_load((WORKFLOWS.parents[1] / "actions" / name / "action.yml").read_text())


@then("its site check runs with check-only, and every deploy step is skipped with it")
def check_only(action):
    assert action["inputs"]["check-only"]["default"] == "false"
    steps = {s["name"]: s for s in action["runs"]["steps"]}
    assert "inputs.check-only == 'true'" in steps["Check the site"]["if"]
    deploys = [s for name, s in steps.items() if name.startswith("Deploy")]
    assert deploys
    for step in deploys:
        assert step["if"].startswith("inputs.check-only != 'true' && "), step["name"]
    assert steps["Check the inputs"]["env"]["CHECK_ONLY"] == "${{ inputs.check-only }}"


@then("the scan's layout comes before sonar-args and pubrules.json's sonar args")
def layout_first(workflow):
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    args = next(s for s in steps if "sonarqube-scan-action" in s.get("uses", ""))["with"]["args"].split()
    # The scanner takes the last value a property is given.
    assert (args.index("inputs.layout") < args.index("inputs.sonar-args")
            < args.index("steps.settings.outputs.args")), args
    assert "layout" in triggers(workflow)["workflow_call"]["inputs"]


@then("the coverage reports are downloaded outside the checkout, and the scan finds them there")
def reports_outside(workflow):
    """A checkout analysed with sonar.sources=. would take an HTML coverage
    report in it for the repository's own code."""
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    download = next(s for s in steps if "download-artifact" in s.get("uses", ""))
    assert download["with"]["path"] == "${{ runner.temp }}/coverage-download", download
    report = next(s for s in steps if s.get("id") == "report")
    assert 'find "$RUNNER_TEMP/coverage-download"' in report["run"], report["run"]


@then("the scan waits for the quality gate, so a failing gate fails the job")
def sonar_gate(workflow):
    """Without the wait the scan only uploads, so `ci / passed` stays green
    while SonarQube Cloud's quality gate fails. The timeout
    keeps a stuck analysis from holding the job for the default 5 minutes
    longer than it needs."""
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    args = next(s for s in steps if "sonarqube-scan-action" in s.get("uses", ""))["with"]["args"].split()
    assert "-Dsonar.qualitygate.wait=true" in args
    assert "-Dsonar.qualitygate.timeout=300" in args
    # Before the caller's properties, so a caller can still override it.
    assert args.index("-Dsonar.qualitygate.wait=true") < args.index("${{")


@then("the gate step fails the job on a failed quality gate")
def gate_step(workflow):
    """The scan only uploads (the gate step asks SonarQube Cloud for the gate
    after it), and the gate step runs even when the scan failed."""
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    scan = next(s for s in steps if s.get("id") == "scan")
    assert "-Dsonar.qualitygate.wait=false" in scan["with"]["args"].split()
    gate = next(s for s in steps if s.get("id") == "gate")
    assert steps.index(gate) > steps.index(scan)
    assert gate["env"]["SCAN"] == "${{ steps.scan.outcome }}"
    assert "if" in gate and "success()" not in gate["if"]


@then("every action it uses is pinned to a full commit hash, with its version in a comment")
def pinned(workflow):
    for line in workflow["text"].splitlines():
        match = re.match(r"\s*(?:- )?uses: (\S+)(.*)", line)
        if not match or match.group(1).startswith("./") or line.lstrip().startswith("#"):
            continue
        action, rest = match.groups()
        # pubrel's and pubrules' own reusable workflows too (SonarQube's S7637).
        assert re.search(r"@[0-9a-f]{40}$", action), f"not pinned to a commit: {line.strip()}"
        assert re.match(r"\s+# v\d+\.\d+\.\d+$", rest), f"no version comment: {line.strip()}"


@then("its setup input runs npm ci with --ignore-scripts")
def npm_ignore_scripts(workflow):
    setup = triggers(workflow)["workflow_call"]["inputs"]["setup"]["default"]
    assert setup.startswith("npm ci ") and "--ignore-scripts" in setup.split()


@then("its browser-setup input runs npx with --no-install")
def npx_no_install(workflow):
    setup = triggers(workflow)["workflow_call"]["inputs"]["browser-setup"]["default"]
    assert setup.startswith("npx --no-install ")


@then(parsers.parse('the "{name}" job hands its coverage report to the sonar scan as "{prop}"'))
def coverage_handed_over(workflow, name, prop):
    jobs = workflow["data"]["jobs"]
    upload = next(s for s in jobs[name]["steps"]
                  if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["if-no-files-found"] == "ignore", upload
    inputs = triggers(workflow)["workflow_call"]["inputs"]
    report = "browser-coverage-report" if name == "browser" else "coverage-report"
    if report in inputs:
        assert upload["with"]["path"] == f"${{{{ inputs.{report} }}}}", upload
    needs = jobs["sonar"]["needs"]
    assert name in ([needs] if isinstance(needs, str) else needs), jobs["sonar"]
    download = next(s for s in jobs["sonar"]["steps"]
                    if s.get("uses", "").startswith("actions/download-artifact@"))
    wanted = download["with"].get("name") or download["with"]["pattern"]
    assert fnmatch.fnmatchcase(upload["with"]["name"], wanted), download
    assert "merge-multiple" not in download["with"], "reports of the same name would overwrite each other"
    assert download.get("continue-on-error") is True, download
    scan = next(s for s in jobs["sonar"]["steps"] if "sonarqube-scan-action" in s.get("uses", ""))
    assert f"-D{prop}=" in scan["with"]["args"], scan["with"]["args"]


@then("the sonar job waits for the browser job, and runs when it was skipped")
def sonar_waits_for_browser(workflow):
    jobs = workflow["data"]["jobs"]
    sonar = jobs["sonar"]
    assert "browser" in sonar["needs"], sonar["needs"]
    tests = next(n for n in sonar["needs"] if n != "browser")
    assert sonar["if"] == (
        f"always() && needs.{tests}.result == 'success' && "
        "contains(fromJSON('[\"success\", \"skipped\"]'), needs.browser.result)"), sonar["if"]
    upload = next(s for s in jobs["browser"]["steps"]
                  if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["path"] == "${{ inputs.browser-coverage-report }}", upload


@then("the functional job runs make coverage in place of make functional when given a SONAR_TOKEN")
def coverage_in_place(workflow):
    job = workflow["data"]["jobs"]["functional"]
    assert job["env"]["COVERAGE"] == "${{ secrets.SONAR_TOKEN != '' }}", job["env"]
    loop = next(s for s in job["steps"] if "for target in" in s.get("run", ""))
    assert 'if [[ "$target" = functional && "$COVERAGE" = true ]]; then target=coverage; fi' in loop["run"]
    shipped = (SOURCE / "src" / "pubrules" / "templates" / "rust" / "pubrules.mk").read_text()
    assert re.search(r"^coverage: .*##", shipped, re.M), "pubrules.mk has no coverage target"
    assert re.search(r"^\.PHONY: .*\bcoverage\b", shipped, re.M), "coverage is not phony"


@then("the token itself never reaches the functional job")
def token_kept_out(workflow):
    job = workflow["data"]["jobs"]["functional"]
    text = yaml.safe_dump(job)
    assert "secrets.SONAR_TOKEN }}" not in text, "the functional job is given the token"


@then(parsers.parse('its "{name}" job runs "{check}" on every event'))
def audit_job(workflow, name, check):
    job = workflow["data"]["jobs"][name]
    assert "if" not in job
    assert check in yaml.safe_dump(job["steps"])
    assert name in workflow["data"]["jobs"]["passed"]["needs"]


@then("no input turns the audit job off")
def audit_unconditional(workflow):
    steps = workflow["data"]["jobs"]["audit"]["steps"]
    # A retry's condition reads the try before it; none reads an input.
    assert not any("inputs." in str(step.get("if", "")) for step in steps)


@then("its fuzz job reads security.fuzz.rust from pubrules.json on a scheduled run")
def fuzz_setting(workflow):
    run = next(s["run"] for s in workflow["data"]["jobs"]["fuzz"]["steps"]
               if "fuzz-smoke" in s.get("run", ""))
    assert '"$EVENT" = schedule' in run and ".security.fuzz" in run and ".rust" in run
    assert "pubrules.json" in run and "$LONG" in run and "seconds=$SHORT" in run


@then(parsers.parse('its "{name}" job sets PUBRULES_FUZZ_RUNS before its tests, '
                    'from security.fuzz.{language} on a scheduled run'))
def property_runs(workflow, name, language):
    data = workflow["data"]
    steps = data["jobs"][name]["steps"]
    at = next(i for i, s in enumerate(steps) if "PUBRULES_FUZZ_RUNS" in s.get("run", ""))
    run = steps[at]["run"]
    assert '"$EVENT" = schedule' in run and ".security.fuzz" in run and f".{language}" in run
    assert "runs=$SHORT" in run and "runs=$LONG" in run and '>> "$GITHUB_ENV"' in run
    assert steps[at]["env"]["SHORT"] == "${{ inputs.fuzz-runs }}"
    assert steps[at]["env"]["LONG"] == "${{ inputs.fuzz-runs-scheduled }}"
    assert steps.index(next(s for s in steps if s.get("run") == "${{ inputs.test }}")) > at
    inputs = data[True]["workflow_call"]["inputs"]
    assert inputs["fuzz-runs"]["default"] == "100"
    assert inputs["fuzz-runs-scheduled"]["default"] == "10000"


@then(parsers.parse('its "{name}" job runs dependency review on public pull requests only'))
def review_job(workflow, name):
    job = workflow["data"]["jobs"][name]
    assert job["if"] == "github.event_name == 'pull_request' && !github.event.repository.private"
    assert job["steps"][-1]["uses"].startswith("actions/dependency-review-action@")
    assert name in workflow["data"]["jobs"]["passed"]["needs"]


@then("its passed job lets the review job be skipped")
def review_may_skip(workflow):
    run = workflow["data"]["jobs"]["passed"]["steps"][0]["run"]
    assert '.key == "review"' in run or '.result == "skipped"' in run


@then("without a token it warns, unless the pull request comes from a fork")
def sonar_warns(workflow):
    steps = workflow["data"]["jobs"]["sonar"]["steps"]
    step = next(s for s in steps if s.get("if") == "env.SONAR_TOKEN == ''")
    assert "::warning::" in step["run"] and "secrets: inherit" in step["run"]
    assert "::notice::" in step["run"]
    assert step["env"]["FORK"] == "${{ github.event.pull_request.head.repo.fork || false }}"
    assert "${{" not in step["run"]  # nothing in the message is an expression


# The data repository, where pubtest's cassettes are.

CHECKOUT = "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
APP_TOKEN = "actions/create-github-app-token@f418cff399f7aef4c2f0ad47e25ca7a6abbdd6fc"
DATA_PATH = ".pubrules-data"


def _data_steps(steps):
    return [s for s in steps if str(s.get("if", "")).startswith("inputs.data-repo")]


def _reference_steps():
    data = yaml.safe_load((WORKFLOWS / "job-python-functional.yml").read_text())
    return _data_steps(data["jobs"]["functional"]["steps"])


@then("it takes data-repo, off by default, and the data reader app's DATA_APP_CLIENT_ID and DATA_APP_KEY, optional")
def takes_data_repo(workflow):
    call = triggers(workflow)["workflow_call"]
    assert call["inputs"]["data-repo"]["type"] == "boolean"
    assert call["inputs"]["data-repo"]["default"] is False
    for name in ("DATA_APP_CLIENT_ID", "DATA_APP_KEY"):
        assert call["secrets"][name]["required"] is False, name
    assert not {"RELEASE_APP_ID", "RELEASE_APP_KEY"} & set(call["secrets"])


@then(parsers.parse('its "{job}" job, given data-repo, mints the data reader app\'s token, by its client id, for the owner\'s data '
                    'repository alone, to read its contents'))
def mints_read_token(workflow, job):
    steps = _data_steps(workflow["data"]["jobs"][job]["steps"])
    assert steps == _reference_steps()  # one block, the same in every workflow
    find, token = steps[0], steps[1]
    assert find["id"] == "data"
    assert 'repo="${GITHUB_REPOSITORY#*/}-data"' in find["run"]
    assert find["env"]["CLIENT_ID"] == "${{ secrets.DATA_APP_CLIENT_ID }}"
    assert find["env"]["HAS_KEY"] == "${{ secrets.DATA_APP_KEY != '' }}"
    assert "${{" not in find["run"]  # nothing in the messages is an expression
    assert token["uses"].startswith(APP_TOKEN)
    assert token["id"] == "data-token"
    # client-id, never the deprecated app-id (v3.1.0 on takes it).
    assert token["with"] == {"client-id": "${{ secrets.DATA_APP_CLIENT_ID }}",
                             "private-key": "${{ secrets.DATA_APP_KEY }}",
                             "owner": "${{ github.repository_owner }}",
                             "repositories": "${{ steps.data.outputs.repo }}",
                             "permission-contents": "read"}
    # Its failure is reported by the step after it, which says what to do.
    assert token["continue-on-error"] is True


@then(parsers.parse('its "{job}" job checks the data repository out with that token, keeping no credentials, '
                    'into the workspace'))
def checks_out_data(workflow, job):
    checkout = _data_steps(workflow["data"]["jobs"][job]["steps"])[2]
    assert checkout["if"] == "inputs.data-repo && steps.data-token.outcome == 'success'"
    assert checkout["uses"].startswith(CHECKOUT)
    assert checkout["with"] == {
        "repository": "${{ github.repository_owner }}/${{ steps.data.outputs.repo }}",
        "token": "${{ steps.data-token.outputs.token }}",
        "path": DATA_PATH,  # actions/checkout keeps a path inside the workspace
        "persist-credentials": False}


@then(parsers.parse('its "{job}" job moves the data repository beside the checkout before it runs the suite'))
def moves_before_suite(workflow, job):
    steps = workflow["data"]["jobs"][job]["steps"]
    assert steps[0]["uses"].startswith(CHECKOUT) and "with" not in steps[0]
    # Straight after the repository's own checkout, before anything runs.
    assert steps[1:5] == _data_steps(steps)
    assert f'mv {DATA_PATH} "$beside"' in steps[4]["run"]


def _run_step(tmp_path, step, env, cwd=None):
    output = tmp_path / "github-output"
    output.write_text("")
    done = subprocess.run(  # GitHub's default for `run`: bash -e.
        ["bash", "-e", "-c", step["run"]], capture_output=True, text=True, check=False, cwd=cwd or tmp_path,
        env={"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(output), **env})
    return {"code": done.returncode, "out": done.stdout, "output": output.read_text()}


CLIENT_ID = "Iv23liR3RvIw58sFy12M"
GIVEN = {"the data reader app's client id and key": (CLIENT_ID, "true"),
         "the data reader app's client id": (CLIENT_ID, "false"),
         "the data reader app's key": ("", "true"), "neither": ("", "false")}
GIVEN_ID = re.compile(r'the client id "(?P<value>[^"]*)" and the data reader app\'s key')


@when(parsers.re(r'the data step runs with (?P<given>.+?), on a pull request from "(?P<head>[^"]+)" to '
                 r'"(?P<base>[^"]+)"(?:, by "(?P<actor>[^"]+)")?$'), target_fixture="step")
def run_data_step(tmp_path, given, head, base, actor):
    if m := GIVEN_ID.fullmatch(given):
        client_id, has_key = m["value"], "true"
    else:
        client_id, has_key = GIVEN[given]
    return _run_step(tmp_path, _reference_steps()[0], {
        "GITHUB_REPOSITORY": base, "GITHUB_REPOSITORY_OWNER": base.split("/")[0], "HEAD": head,
        "ACTOR": actor or "someone", "CLIENT_ID": client_id, "HAS_KEY": has_key})


@then(parsers.parse('the step passes, naming the data repository "{name}"'))
def step_passes(step, name):
    assert step["code"] == 0, step
    assert step["output"] == f"repo={name}\n"
    assert "::error" not in step["out"]


@then(parsers.parse('the step fails, with an error that names "{text}"'))
def step_fails_naming(step, text):
    assert step["code"] != 0, step
    (error,) = [line for line in step["out"].splitlines() if line.startswith("::error")]
    assert text in error, error


def _error(step):
    return next(line for line in step["out"].splitlines() if line.startswith("::error"))


@then(parsers.re(r'the error (?:says|says how to set them:|says how to make one:|names the data repository) '
                 r'"(?P<text>[^"]+)"$'))
def error_says(step, text):
    assert text in _error(step), _error(step)


@then(parsers.parse('the error does not say "{text}"'))
def error_not(step, text):
    assert text not in _error(step), _error(step)


def _move(tmp_path, outcome):
    workspace = tmp_path / "work" / "demo" / "demo"
    (workspace / DATA_PATH / "integrations" / "cassettes").mkdir(parents=True)
    (workspace / "pubrules.json").write_text('{"kind": "utility", "pubtest": {"cassettes": true}}\n')
    # A data repository an earlier run on the same runner left.
    (workspace.parent / "demo-data" / "stale").mkdir(parents=True)
    step = _reference_steps()[3]
    found = _run_step(tmp_path, step, {"GITHUB_WORKSPACE": str(workspace), "GITHUB_REPOSITORY_OWNER": "Sustenaut",
                                        "TOKEN": outcome, "REPO": "demo-data"}, cwd=workspace)
    return {**found, "workspace": workspace}


@when("the step that moves the data repository runs after a checkout of it", target_fixture="step")
def move_data(tmp_path):
    return _move(tmp_path, "success")


@when("the step that moves the data repository runs after the token step failed", target_fixture="step")
def move_without_token(tmp_path):
    return _move(tmp_path, "failure")


@then("the data repository is beside the checkout, named as the checkout with -data")
def beside(step):
    assert step["code"] == 0, step
    workspace = step["workspace"]
    data = workspace.parent / f"{workspace.name}-data"
    assert (data / "integrations" / "cassettes").is_dir()
    assert not (data / "stale").exists()
    assert not (workspace / DATA_PATH).exists()


@then("pubtest finds its cassettes in it, under integrations/cassettes")
def pubtest_finds(step):
    from pubtest import cassettes  # noqa: PLC0415

    workspace = step["workspace"]
    found = cassettes.settings(workspace, env={})
    assert found.data_repo == workspace.parent / "demo-data"
    assert found.cassettes == workspace.parent / "demo-data" / "integrations" / "cassettes"
    assert found.cassettes.is_dir()
