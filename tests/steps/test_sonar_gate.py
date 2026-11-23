"""Steps for the sonar job's gate step: its script run as GitHub runs a
step, in a work folder, with a stub curl that answers SonarQube Cloud's API
from files the scenario writes, and a sleep that records its seconds."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from pytest_bdd import parsers, given, scenarios, then, when

scenarios("sonar-gate.feature")

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "job-sonar.yml"
SERVER = "https://sonarcloud.io"
TASK = f"{SERVER}/api/ce/task?id=AX1"
GATE = f"{SERVER}/api/qualitygates/project_status?analysisId=AN1"
VERSION = f"{SERVER}/api/server/version"
GITHUB = "https://api.github.com/repos/o/r"

# Answers a request from api/<url with every other character an underscore>.<n>,
# the nth time it is asked (the last one for every time after), as
# "<status>" on a first line and the body after it; with no such file it
# fails as curl does when the host cannot be reached. -w '\n%{http_code}'
# is what the step asks for, so the status is printed after the body.
CURL = """#!/bin/bash
url="${*: -1}"
echo "$url" >> "$API/../requests"
key="$(printf '%s' "$url" | tr -c 'A-Za-z0-9' _)"
files=("$API"/"$key".*)
[ -e "${files[0]}" ] || exit 7
n=$(cat "$API/../count.$key" 2> /dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$API/../count.$key"
last=${#files[@]}
[ "$n" -gt "$last" ] && n=$last
file="$API/$key.$n"
status="$(head -n 1 "$file")"
case " $* " in *" -fsS "*) [ "$status" -ge 400 ] && exit 22 ;; esac
tail -n +2 "$file"
case " $* " in *" -w "*) printf '\\n%s' "$status" ;; esac
"""


def key(url):
    return re.sub(r"[^A-Za-z0-9]", "_", url)


def step():
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["sonar"]["steps"]
    return next(s for s in steps if s.get("id") == "gate")


@pytest.fixture
def world(tmp_path):
    (tmp_path / "api").mkdir()
    return {"work": tmp_path, "scan": "success", "env": {"EVENT": "pull_request", "PR_NUMBER": "7"}, "answers": {}}


def answer(world, url, status, body=""):
    world["answers"].setdefault(url, []).append((status, body))


def write_report(world, server=SERVER, task=TASK):
    folder = world["work"] / ".scannerwork"
    folder.mkdir()
    (folder / "report-task.txt").write_text(f"projectKey=o_r\nserverUrl={server}\nceTaskUrl={task}\n")


@given(parsers.re(r"the scan (?P<how>passed|failed) and the scanner wrote (?P<report>a report|no report)"))
def scan(world, how, report):
    world["scan"] = "success" if how == "passed" else "failure"
    if report == "a report":
        write_report(world)


@given("the scan passed")
def scan_passed(world):
    world["scan"] = "success"


@given(parsers.parse('the scanner wrote a report naming the server "{server}"'))
def report_server(world, server):
    write_report(world, server=server)


@given(parsers.parse('the scanner wrote a report naming the task "{task}"'))
def report_task(world, task):
    write_report(world, task=task)


@given("the pull request carries the label sonar-down")
def labelled(world):
    """As GitHub's API says now. The event's own payload is never read: it
    has no label here, as when a failed run is run again."""
    answer(world, f"{GITHUB}/pulls/7", 200, json.dumps({"labels": [{"name": "bug"}, {"name": "Sonar-Down"}]}))


@given("the run is for a push to main, whose merged pull request carries the label sonar-down")
def pushed_labelled(world):
    world["env"].update(EVENT="push")
    answer(world, f"{GITHUB}/commits/abc123/pulls", 200, json.dumps([
        {"merged_at": None, "labels": [{"name": "sonar-down"}]},
        {"merged_at": "2026-11-23T10:00:00Z", "labels": [{"name": "sonar-down"}]}]))


@given("the run is for a push to main, whose pull request that was not merged carries the label sonar-down")
def pushed_unmerged(world):
    world["env"].update(EVENT="push")
    answer(world, f"{GITHUB}/commits/abc123/pulls", 200, json.dumps([
        {"merged_at": None, "labels": [{"name": "sonar-down"}]}]))


@given("the event payload has no label")
def payload_bare(world):
    (world["work"] / "event.json").write_text(json.dumps({"pull_request": {"number": 7, "labels": []}}))
    world["env"]["GITHUB_EVENT_PATH"] = str(world["work"] / "event.json")


@given("GitHub's API refuses to give the pull request")
def label_refused(world):
    answer(world, f"{GITHUB}/pulls/7", 403)


@given(parsers.parse("the analysis may take {seconds:d} seconds"))
def timeout(world, seconds):
    world["env"]["TIMEOUT"] = str(seconds)


@given(parsers.parse("SonarQube Cloud answers the version query with {status:d}"))
def version(world, status):
    answer(world, VERSION, status)


@given(parsers.re(r'the analysis task answers (?P<first>"[A-Z]+")(?: and then (?P<second>"[A-Z]+"))?$'))
def task(world, first, second):
    for status in filter(None, (first, second)):
        status = status.strip('"')
        body = {"task": {"status": status, **({"analysisId": "AN1"} if status == "SUCCESS" else {})}}
        answer(world, TASK, 200, json.dumps(body))


@given(parsers.parse("the analysis task answers with {status:d}"))
def task_status(world, status):
    answer(world, TASK, status)


@given(parsers.re(r'the quality gate answers "(?P<gate>[A-Z]+)"(?: on "(?P<metric>[a-z_]+)")?$'))
def gate(world, gate, metric):
    conditions = [{"status": "ERROR", "metricKey": metric}] if metric else []
    answer(world, GATE, 200, json.dumps({"projectStatus": {"status": gate, "conditions": conditions}}))


@given("the quality gate does not answer")
def gate_silent(world):
    pass


@when("the gate step runs", target_fixture="ran")
def run(world):
    work = world["work"]
    for url, answers in world["answers"].items():
        for number, (status, body) in enumerate(answers, 1):
            (work / "api" / f"{key(url)}.{number}").write_text(f"{status}\n{body}")
    bin_dir = work / "bin"
    bin_dir.mkdir()
    (bin_dir / "curl").write_text(CURL)
    (bin_dir / "curl").chmod(0o755)
    (bin_dir / "sleep").write_text('#!/bin/sh\necho "$1" >> "$SLEPT"\n')
    (bin_dir / "sleep").chmod(0o755)
    summary = work / "summary.md"
    done = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step()["run"]],
        capture_output=True, text=True, check=False, cwd=work,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "API": str(work / "api"),
             "SLEPT": str(work / "slept"), "GITHUB_STEP_SUMMARY": str(summary), "SONAR_TOKEN": "t",
             "SCAN": world["scan"], "GITHUB_API": "https://api.github.com", "GH_TOKEN": "g",
             "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "abc123", **world["env"]})
    return {"code": done.returncode, "lines": done.stdout.splitlines(),
            "slept": (work / "slept").read_text().split() if (work / "slept").exists() else [],
            "summary": summary.read_text() if summary.exists() else "",
            "requests": (work / "requests").read_text().split() if (work / "requests").exists() else []}


@then("the step passed")
def passed(ran):
    assert ran["code"] == 0, ran


@then("nothing was bypassed")
def not_bypassed(ran):
    assert not any("NOT analysed" in line for line in ran["lines"]), ran
    assert "bypassed" not in ran["summary"], ran


@then(parsers.parse('the step failed with the error "{text}"'))
def failed(ran, text):
    assert ran["code"] != 0, ran
    assert any(line.startswith("::error::") and text in line for line in ran["lines"]), ran


@then(parsers.parse('the error names the label "{label}"'))
def names_label(ran, label):
    assert any(line.startswith("::error::") and f"add the label {label}" in line for line in ran["lines"]), ran


@then(parsers.parse('it warned "{text}"'))
def warned(ran, text):
    assert any(line.startswith("::warning::") and text in line for line in ran["lines"]), ran


@then(parsers.parse('no request went to "{host}"'))
def no_request(ran, host):
    assert not any(host in url for url in ran["requests"]), ran


@then("the job's summary says SonarQube Cloud was bypassed")
def summarised(ran):
    assert "SonarQube Cloud was bypassed" in ran["summary"], ran


@then(parsers.re(r"it slept (?P<times>\d+) times?$"))
def slept(ran, times):
    assert len(ran["slept"]) == int(times), ran


def steps_of():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["sonar"]["steps"]


@when("I read the sonar job")
def read_job():
    pass


@then("its scan step does not wait for the quality gate and may fail")
def scan_step():
    scan_step = next(s for s in steps_of() if s.get("id") == "scan")
    assert "-Dsonar.qualitygate.wait=false" in scan_step["with"]["args"]
    assert scan_step["continue-on-error"] is True


@then("the scanner's folder is removed before the scan")
def folder_removed():
    steps = steps_of()
    ids = [s.get("id") or s.get("run") for s in steps]
    assert ids.index("rm -rf .scannerwork") < ids.index("scan"), ids


@then(parsers.re(r'its steps run in the order (?P<ids>"[a-z]+"(?:, "[a-z]+")*)$'))
def order(ids):
    wanted = re.findall(r'"([a-z]+)"', ids)
    found = [s["id"] for s in steps_of() if s.get("id") in wanted]
    assert found == wanted, found
