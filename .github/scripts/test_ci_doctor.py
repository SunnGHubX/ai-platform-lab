"""ci-doctor classifier tests, using log excerpts from real failures in this repo's history."""
import ci_doctor
from ci_doctor import classify, render

GH = "terraform\tterraform test\t2026-11-09T19:06:00.0000000Z "  # gh --log-failed line prefix


def rule_ids(d):
    return [r.id for r, _ in d.matches]


def test_terraform_fmt_from_real_run():
    log = f"{GH}modules/eks-cluster/main.tf\n{GH}##[error]Terraform exited with code 3.\n"
    assert rule_ids(classify("terraform", log)) == ["terraform-fmt"]


def test_terraform_test_lists_failing_runs():
    log = (f'{GH}  run "image_only_service_gets_no_permissions"... \x1b[31mfail\x1b[0m\n'
           f'{GH}  run "queue_service_gets_only_queue_permissions"... skip\n'
           f"{GH}│ Error: Invalid ARN Value\n")
    d = classify("terraform", log)
    by_id = dict((r.id, items) for r, items in d.matches)
    assert by_id["terraform-test"] == ["image_only_service_gets_no_permissions"]


def test_pytest_failures_are_listed():
    log = ("FAILED tests/e2e/smoke_test.py::test_lab04_mlflow_train_and_register - CalledProcessError\n"
           "FAILED tests/e2e/smoke_test.py::test_lab06_otel_metrics_flow_to_prometheus - Failed\n")
    [(rule, items)] = classify("e2e", log).matches
    assert rule.id == "pytest" and len(items) == 2


def test_rego_and_policy_failures():
    assert rule_ids(classify("policy", "data.main.test_missing_memory_limit_denied: FAIL (941µs)\n")) == ["rego-test"]
    d = classify("policy", "FAIL - Deployment/x: container \"a\" uses the mutable :latest tag\n")
    assert rule_ids(d) == ["policy-violation"] and ":latest" in d.matches[0][1][0]


def test_promtool_failure():
    log = "  FAILED:\n    alertname: InferenceAvailabilityFastBurn, time: 1h10m0s,\n"
    d = classify("sre", log)
    assert rule_ids(d) == ["promtool"] and d.matches[0][1] == ["InferenceAvailabilityFastBurn,"]


def test_transient_only_run_says_rerun():
    d = classify("e2e", "Error response from daemon: toomanyrequests: You have reached your pull rate limit\n")
    assert d.transient_only
    assert "Looks transient" in render("e2e", "#", [d])


def test_real_failure_suppresses_cooccurring_transient_noise():
    log = "Transient error ... Connection reset by peer\nFAILED tests/x.py::test_a - AssertionError\n"
    assert rule_ids(classify("job", log)) == ["pytest"]


def test_oomkilled_detected():
    log = '--- RESTARTED mlops/mlflow x6 lastState={"terminated": {"exitCode": 137, "reason": "OOMKilled"}}\n'
    assert "oom" in rule_ids(classify("e2e", log))


def test_unknown_failure_shows_log_tail():
    d = classify("mystery", "line 1\nsomething odd happened\n")
    assert d.matches == [] and d.tail[-1] == "something odd happened"
    assert "No known pattern matched" in render("x", "#", [d])


def test_comment_carries_marker_for_idempotent_updates():
    assert render("x", "#", []).startswith(ci_doctor.MARKER)


def test_cli_local_log(tmp_path, capsys):
    f = tmp_path / "log.txt"
    f.write_text("FAILED tests/test_a.py::test_b - boom\n")
    assert ci_doctor.main(["--log-file", str(f)]) == 0
    assert "tests/test_a.py::test_b" in capsys.readouterr().out


def test_api_log_timestamps_are_stripped_before_matching():
    log = "2026-11-09T21:17:45.123Z FAILED tests/e2e/smoke_test.py::test_x - boom\n"
    assert rule_ids(classify("e2e", log)) == ["pytest"]


def test_echoed_fmt_command_is_not_a_failure():
    log = "2026-11-09T19:06:00.1Z Run terraform fmt -check -recursive -diff\n2026-11-09T19:06:01.1Z all good\n"
    assert classify("terraform", log).matches == []


def test_tail_is_context_before_first_error():
    lines = [f"line {i}" for i in range(50)] + ["##[error]Process completed with exit code 1."] + ["cleanup"] * 30
    d = classify("x", "\n".join(lines))
    assert d.tail[-1].startswith("##[error]") and "cleanup" not in d.tail


def test_shellcheck_findings_from_real_run():
    log = ("In tests/e2e/run.sh line 66:\n  for pid in x; do [ -n \"$pid\" ] && { kill; } || true; done\n"
           "                                                 ^-- SC2015 (info): Note that A && B || C is not if-then-else.\n")
    d = classify("tooling", log)
    assert rule_ids(d) == ["shellcheck"] and d.matches[0][1][0].startswith("SC2015 (info)")


def test_devcontainer_feature_failure_from_real_run():
    log = ("#16 0.136 (!) The 'moby' option is not supported on debian 'trixie'\n"
           '#16 0.137 ERROR: Feature "Docker (Docker-in-Docker)" (ghcr.io/devcontainers/features/docker-in-docker) failed to install!\n'
           "[2026-11-09T23:33:06.662Z] ERROR: failed to build: failed to solve: process did not complete\n"
           "Error: Command failed: docker buildx build --load\n")
    ids_ = rule_ids(classify("devcontainer", log))
    assert "devcontainer-feature" in ids_ and "docker-build" in ids_
    assert "terraform-validate" not in ids_  # plain "Error:" is not a Terraform error


def test_boxed_terraform_error_from_real_run():
    log = "\x1b[31m│\x1b[0m \x1b[0m\x1b[1m\x1b[31mError: \x1b[0m\x1b[0m\x1b[1mattaching IAM Policy (arn:aws:iam::aws:policy/ReadOnlyAccess)\n"
    d = classify("aws", log)
    assert rule_ids(d) == ["terraform-validate"] and d.matches[0][1][0].startswith("attaching IAM Policy")
