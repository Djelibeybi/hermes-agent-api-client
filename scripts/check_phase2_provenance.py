"""Verify Phase 2 Hermes release identity and immutable evidence provenance."""  # noqa: INP001

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


_REPOSITORY = "https://github.com/NousResearch/hermes-agent"
_GIT_REPOSITORY = f"{_REPOSITORY}.git"
_CANONICAL_TAG = "v2026.7.7.2"
_CANONICAL_COMMIT = "9de9c25f620ff7f1ce0fd5457d596052d5159596"
_CANONICAL_TAG_OBJECT = "b7751df34688835a108e0d630f3495fc11f3df79"
_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_ROOT = _ROOT / "tests" / "fixtures" / "hermes"
_CANONICAL_ROOT = _FIXTURE_ROOT / _CANONICAL_TAG
_PROVENANCE_PATH = _CANONICAL_ROOT / "provenance.json"
_ALLOWED_SOURCE_PATHS = frozenset(
    {
        "gateway/platforms/api_server.py",
        "tests/gateway/test_api_server.py",
    }
)
_NUMERIC_TAG = re.compile(r"^v(?P<version>[0-9]+(?:\.[0-9]+)+)$")
_BLOB_URL = re.compile(
    rf"^{re.escape(_REPOSITORY)}/blob/(?P<ref>[^/]+)/"
    r"(?P<path>[^#]+)#L(?P<start>[0-9]+)-L(?P<end>[0-9]+)$"
)
_EXPECTED_KINDS = {
    "chat_completions/tool_progress_pair.sse": "tag-source-derived",
    "chat_completions/terminal_length.sse": "tag-source-derived",
    "chat_completions/terminal_agent_error.sse": "tag-source-derived",
    "chat_completions/terminal_task_exception_contradiction.sse": (
        "tag-source-derived"
    ),
    "chat_completions/terminal_design_matrix.json": "design-derived",
}
_DECISIONS = frozenset({"D-01", "D-02", "D-03", "D-04"})
_PROVENANCE_SCHEMA_VERSION = 3
_TERMINAL_RECORD_COUNT = 2
_LIFECYCLE_TEXT_MAX = 256


class ProvenanceError(RuntimeError):
    """An input-independent provenance validation failure."""


def _fail(message: str) -> NoReturn:
    raise ProvenanceError(message)


def _run_git(*arguments: str, cwd: Path | None = None) -> str:
    """Run Git without retaining a value-bearing subprocess exception."""
    executable = shutil.which("git")
    if executable is None:
        _fail("latest-tag-verification-blocked")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable and arguments
            (executable, *arguments),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        _fail("latest-tag-verification-blocked")
    if completed.returncode != 0:
        _fail("latest-tag-verification-blocked")
    return completed.stdout


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail(f"invalid-json:{path.relative_to(_ROOT)}")
    if not isinstance(value, dict):
        _fail(f"expected-object:{path.relative_to(_ROOT)}")
    return cast("dict[str, Any]", value)


def _require_string(value: object, field: str) -> str:
    if type(value) is not str or not value:
        _fail(f"invalid-{field}")
    return cast("str", value)


def _require_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail(f"invalid-{field}")
    return [_require_string(item, field) for item in value]


def _release_tags() -> tuple[dict[str, str], dict[str, str]]:
    output = _run_git("ls-remote", "--tags", _GIT_REPOSITORY, "refs/tags/v[0-9]*")
    objects: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 2:  # noqa: PLR2004 - Git protocol row width
            continue
        commit, reference = fields
        prefix = "refs/tags/"
        if not reference.startswith(prefix):
            continue
        tag = reference.removeprefix(prefix)
        if tag.endswith("^{}"):
            peeled[tag.removesuffix("^{}")] = commit
        elif _NUMERIC_TAG.fullmatch(tag):
            objects[tag] = commit
    if _CANONICAL_TAG not in objects or _CANONICAL_TAG not in peeled:
        _fail("canonical-tag-not-annotated")
    if objects[_CANONICAL_TAG] != _CANONICAL_TAG_OBJECT:
        _fail("canonical-tag-object-mismatch")
    if peeled[_CANONICAL_TAG] != _CANONICAL_COMMIT:
        _fail("canonical-peeled-commit-mismatch")
    if not objects:
        _fail("latest-tag-verification-blocked")
    return objects, peeled


def _version_key(tag: str) -> tuple[int, ...]:
    match = _NUMERIC_TAG.fullmatch(tag)
    if match is None:
        _fail("invalid-numeric-release-tag")
    return tuple(int(part) for part in match.group("version").split("."))


def _latest_release(
    objects: Mapping[str, str], peeled: Mapping[str, str]
) -> tuple[str, str]:
    latest = max(objects, key=_version_key)
    return latest, peeled.get(latest, objects[latest])


def _verify_release_record(
    provenance: Mapping[str, Any], latest: str, latest_commit: str
) -> None:
    release = provenance.get("release_verification")
    if not isinstance(release, dict):
        _fail("missing-release-verification")
    expected = {
        "canonical_tag": _CANONICAL_TAG,
        "canonical_tag_object": _CANONICAL_TAG_OBJECT,
        "canonical_peeled_commit": _CANONICAL_COMMIT,
        "observed_latest_numeric_tag": latest,
        "observed_latest_peeled_commit": latest_commit,
    }
    for field, value in expected.items():
        if release.get(field) != value:
            _fail(f"release-verification-mismatch:{field}")
    disposition = release.get("compatibility_disposition")
    if latest == _CANONICAL_TAG:
        if disposition != "canonical-current":
            _fail("canonical-current-disposition-required")
        if "latest_evidence" in release:
            _fail("unexpected-latest-evidence")
        return
    if disposition != "identical-public-semantics":
        _fail("newer-tag-contract-decision-required")
    _verify_newer_release(cast("Mapping[str, Any]", release), latest, latest_commit)


def _verify_newer_release(  # noqa: C901, PLR0912
    release: Mapping[str, Any], latest: str, latest_commit: str
) -> None:
    evidence = release.get("latest_evidence")
    if not isinstance(evidence, dict):
        _fail("missing-newer-tag-evidence")
    if evidence.get("hermes_release") != latest:
        _fail("newer-tag-release-mismatch")
    if evidence.get("source_commit") != latest_commit:
        _fail("newer-tag-commit-mismatch")
    if evidence.get("evidence_kind") != "immutable-tag-capture":
        _fail("newer-tag-capture-required")
    if evidence.get("public_semantics") != "identical":
        _fail("newer-tag-public-semantics-unproven")
    fixture_root = f"tests/fixtures/hermes/{latest}"
    if evidence.get("fixture_root") != fixture_root:
        _fail("newer-tag-fixture-root-mismatch")
    _verify_reproduction(evidence)
    _require_string_list(evidence.get("semantic_assertions"), "semantic-assertions")
    difference = evidence.get("difference_summary")
    if not isinstance(difference, dict):
        _fail("missing-newer-tag-difference-summary")
    if difference.get("canonical_fixture_root") != (
        f"tests/fixtures/hermes/{_CANONICAL_TAG}"
    ):
        _fail("invalid-canonical-difference-root")
    if difference.get("newer_fixture_root") != fixture_root:
        _fail("invalid-newer-difference-root")
    changes = difference.get("changes")
    if not isinstance(changes, list) or not changes:
        _fail("empty-newer-tag-difference-summary")
    for change in changes:
        if not isinstance(change, dict):
            _fail("invalid-newer-tag-change")
        for field in (
            "canonical_path",
            "newer_path",
            "canonical_shape",
            "newer_shape",
            "public_event",
        ):
            if field not in change:
                _fail(f"incomplete-newer-tag-change:{field}")
    normalized = difference.get("normalized_public_events")
    if not isinstance(normalized, dict):
        _fail("missing-normalized-public-events")
    canonical = normalized.get("canonical")
    newer = normalized.get("newer")
    if not isinstance(canonical, dict) or not canonical or canonical != newer:
        _fail("newer-tag-public-events-differ")
    newer_manifest = _FIXTURE_ROOT / latest / "provenance.json"
    if not newer_manifest.is_file():
        _fail("missing-newer-tag-provenance")


def _fetch_source_tree(
    commit: str,
) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="phase2-provenance-")
    root = Path(temporary.name)
    _run_git("init", "-q", cwd=root)
    _run_git("remote", "add", "origin", _GIT_REPOSITORY, cwd=root)
    _run_git("fetch", "-q", "--depth", "1", "origin", commit, cwd=root)
    _run_git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=root)
    if _run_git("rev-parse", "HEAD", cwd=root).strip() != commit:
        _fail("detached-source-commit-mismatch")
    return root, temporary


def _source_lines(source_root: Path, path: str, start: int, end: int) -> bytes:
    if path not in _ALLOWED_SOURCE_PATHS:
        _fail(f"unapproved-source-path:{path}")
    source_path = source_root / path
    try:
        lines = source_path.read_bytes().splitlines(keepends=True)
    except OSError:
        _fail(f"missing-source-path:{path}")
    if start < 1 or end < start or end > len(lines):
        _fail(f"invalid-source-anchor:{path}:L{start}-L{end}")
    return b"".join(lines[start - 1 : end])


def _verify_structured_source_ref(
    source_ref: Mapping[str, Any], source_root: Path, commit: str
) -> None:
    if source_ref.get("repository") != _REPOSITORY:
        _fail("source-repository-mismatch")
    if source_ref.get("commit") != commit:
        _fail("source-ref-commit-mismatch")
    path = _require_string(source_ref.get("path"), "source-path")
    start = source_ref.get("line_start")
    end = source_ref.get("line_end")
    if type(start) is not int or type(end) is not int:
        _fail("invalid-source-line-anchor")
    anchor = _source_lines(source_root, path, start, end)
    expected_hash = hashlib.sha256(anchor).hexdigest()
    if source_ref.get("anchor_sha256") != expected_hash:
        _fail(f"source-anchor-hash-mismatch:{path}:L{start}-L{end}")
    expected_url = f"{_REPOSITORY}/blob/{commit}/{path}#L{start}-L{end}"
    if source_ref.get("url") != expected_url:
        _fail("source-ref-url-mismatch")


def _verify_legacy_source_ref(
    upstream_url: object, source_root: Path, release: str, commit: str
) -> None:
    url = _require_string(upstream_url, "upstream-url")
    match = _BLOB_URL.fullmatch(url)
    if match is None or match.group("ref") not in {release, commit}:
        _fail("invalid-upstream-url")
    _source_lines(
        source_root,
        match.group("path"),
        int(match.group("start")),
        int(match.group("end")),
    )


def _verify_reproduction(entry: Mapping[str, Any]) -> None:
    reproduction = entry.get("reproduction")
    if not isinstance(reproduction, dict):
        _fail("missing-reproduction")
    _require_string(reproduction.get("mode"), "reproduction-mode")
    _require_string_list(reproduction.get("procedure"), "reproduction-procedure")
    configuration = reproduction.get("configuration")
    if not isinstance(configuration, dict):
        _fail("missing-reproduction-configuration")
    if configuration.get("live_server_invoked") is not False:
        _fail("live-server-invocation-must-be-false")


def _safe_fixture_path(version_root: Path, relative: str) -> Path:
    path = (version_root / relative).resolve()
    if not path.is_relative_to(version_root.resolve()):
        _fail("fixture-path-escape")
    return path


def _verify_fixture_entry(
    entry: Mapping[str, Any], version_root: Path, source_root: Path
) -> None:
    relative = _require_string(entry.get("path"), "fixture-path")
    release = _require_string(entry.get("hermes_release"), "fixture-release")
    commit = _require_string(entry.get("source_commit"), "fixture-commit")
    fixture = _safe_fixture_path(version_root, relative)
    try:
        payload = fixture.read_bytes()
    except OSError:
        _fail(f"missing-fixture:{relative}")
    if entry.get("sha256") != hashlib.sha256(payload).hexdigest():
        _fail(f"fixture-hash-mismatch:{relative}")
    _require_string(entry.get("evidence_kind"), "evidence-kind")
    _verify_reproduction(entry)
    _require_string_list(entry.get("semantic_assertions"), "semantic-assertions")
    source_refs = entry.get("source_refs")
    if source_refs is None:
        _verify_legacy_source_ref(
            entry.get("upstream_url"), source_root, release, commit
        )
        return
    if not isinstance(source_refs, list) or not source_refs:
        _fail(f"missing-source-refs:{relative}")
    for source_ref in source_refs:
        if not isinstance(source_ref, dict):
            _fail(f"invalid-source-ref:{relative}")
        _verify_structured_source_ref(source_ref, source_root, commit)


def _fixture_entries(provenance: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    fixtures = provenance.get("fixtures")
    if not isinstance(fixtures, list):
        _fail("invalid-fixture-manifest")
    entries: dict[str, Mapping[str, Any]] = {}
    for entry in fixtures:
        if not isinstance(entry, dict):
            _fail("invalid-fixture-entry")
        path = _require_string(entry.get("path"), "fixture-path")
        if path in entries:
            _fail(f"duplicate-fixture-entry:{path}")
        entries[path] = entry
    return entries


def _sse_data(payload: bytes) -> list[tuple[str | None, str]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        _fail("fixture-is-not-utf8")
    records: list[tuple[str | None, str]] = []
    for block in text.strip().split("\n\n"):
        event: str | None = None
        data: str | None = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if data is None:
            _fail("fixture-record-without-data")
        records.append((event, data))
    return records


def _json_object(data: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except json.JSONDecodeError:
        _fail("invalid-sse-json")
    if not isinstance(value, dict):
        _fail("sse-data-is-not-object")
    return cast("dict[str, Any]", value)


def _verify_tool_fixture(path: Path) -> None:
    records = _sse_data(path.read_bytes())
    if len(records) != 4:  # noqa: PLR2004 - fixed complete evidence sequence
        _fail("tool-fixture-record-count")
    running = _json_object(records[0][1])
    completed = _json_object(records[1][1])
    if records[0][0] != "hermes.tool.progress" or records[1][0] != (
        "hermes.tool.progress"
    ):
        _fail("tool-fixture-event-name")
    if running.get("status") != "running" or completed.get("status") != "completed":
        _fail("tool-fixture-status-order")
    if not running.get("toolCallId") or running.get("toolCallId") != completed.get(
        "toolCallId"
    ):
        _fail("tool-fixture-correlation")
    if running.get("tool") != completed.get("tool"):
        _fail("tool-fixture-name-mismatch")
    if "emoji" not in running or "label" not in running:
        _fail("tool-fixture-missing-tag-additive-fields")
    terminal = _json_object(records[2][1])
    choices = terminal.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
        or choices[0].get("finish_reason") != "stop"
        or "hermes" in terminal
    ):
        _fail("tool-fixture-invalid-stop")
    if records[3] != (None, "[DONE]"):
        _fail("tool-fixture-missing-done")


def _verify_terminal_sse(path: Path, expected: Mapping[str, object]) -> None:
    records = _sse_data(path.read_bytes())
    if len(records) != _TERMINAL_RECORD_COUNT or records[1] != (None, "[DONE]"):
        _fail(f"invalid-terminal-fixture:{path.name}")
    document = _json_object(records[0][1])
    choices = document.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        _fail(f"invalid-terminal-choice:{path.name}")
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != expected.get(
        "finish_reason"
    ):
        _fail(f"terminal-finish-reason-mismatch:{path.name}")
    hermes = document.get("hermes")
    if not isinstance(hermes, dict):
        _fail(f"missing-terminal-hermes:{path.name}")
    for field in ("completed", "partial", "failed", "error_code"):
        if hermes.get(field) != expected.get(field):
            _fail(f"terminal-field-mismatch:{path.name}:{field}")
    if "error" not in document or "error" not in hermes:
        _fail(f"missing-raw-error-canary:{path.name}")


def _contains_none(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(_contains_none(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_none(item) for item in value)
    return False


def _is_lifecycle_text(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= _LIFECYCLE_TEXT_MAX
        and all("!" <= character <= "~" for character in value)
    )


def _verify_accepted_public_event(
    case_id: str, wire: Mapping[str, Any], public_event: Mapping[str, Any]
) -> None:
    finish = wire.get("finish_reason")
    hermes = wire.get("hermes", {})
    if not isinstance(hermes, dict):
        _fail(f"invalid-accepted-hermes:{case_id}")
    if finish == "stop":
        expected = {"outcome": "success", "partial": False, "failure_reason": None}
    elif finish == "length":
        expected = {
            "outcome": "length",
            "partial": True,
            "failure_reason": "output_truncated",
        }
    elif finish == "error":
        partial = hermes.get("partial")
        if type(partial) is not bool:
            _fail(f"invalid-accepted-error-partial:{case_id}")
        code = hermes.get("error_code", "agent_error")
        if not _is_lifecycle_text(code):
            _fail(f"invalid-accepted-error-code:{case_id}")
        expected = {
            "outcome": "upstream_error",
            "partial": partial,
            "failure_reason": "agent_error" if code == "agent_error" else "unknown",
        }
    else:
        _fail(f"invalid-accepted-finish-reason:{case_id}")
    if public_event != expected:
        _fail(f"public-event-semantics-mismatch:{case_id}")


def _verify_design_matrix(  # noqa: C901, PLR0912
    path: Path,
) -> None:
    matrix = _load_object(path)
    if matrix.get("schema_version") != 1:
        _fail("terminal-matrix-schema-version")
    if set(matrix.get("decision_refs", [])) != _DECISIONS:
        _fail("terminal-matrix-decision-set")
    cases = matrix.get("cases")
    if not isinstance(cases, list) or not cases:
        _fail("empty-terminal-design-matrix")
    seen: set[str] = set()
    required_by_finish = {"stop": "D-01", "length": "D-02", "error": "D-03"}
    for case in cases:
        if not isinstance(case, dict):
            _fail("invalid-terminal-matrix-case")
        case_id = _require_string(case.get("id"), "terminal-case-id")
        if case_id in seen:
            _fail(f"duplicate-terminal-case:{case_id}")
        seen.add(case_id)
        wire = case.get("wire")
        expected = case.get("expected")
        refs = case.get("decision_refs")
        if not isinstance(wire, dict) or not isinstance(expected, dict):
            _fail(f"invalid-terminal-case-shape:{case_id}")
        if not isinstance(refs, list) or not refs or not set(refs) <= _DECISIONS:
            _fail(f"invalid-terminal-case-citations:{case_id}")
        finish = wire.get("finish_reason")
        required = required_by_finish.get(cast("str", finish))
        if required is None or required not in refs:
            _fail(f"missing-applicable-terminal-citation:{case_id}")
        if "hermes" in wire and _contains_none(wire["hermes"]) and "D-04" not in refs:
            _fail(f"missing-null-citation:{case_id}")
        disposition = expected.get("disposition")
        if disposition == "accept":
            public_event = expected.get("public_event")
            if not isinstance(public_event, dict):
                _fail(f"missing-public-event:{case_id}")
            if set(public_event) != {"outcome", "partial", "failure_reason"}:
                _fail(f"invalid-public-event:{case_id}")
            _verify_accepted_public_event(case_id, wire, public_event)
        elif disposition == "reject":
            if expected.get("error") != "HermesProtocolError":
                _fail(f"invalid-rejection:{case_id}")
        else:
            _fail(f"invalid-terminal-disposition:{case_id}")


def _verify_all_entries(
    provenance: Mapping[str, Any], source_root: Path
) -> dict[str, Mapping[str, Any]]:
    if provenance.get("schema_version") != _PROVENANCE_SCHEMA_VERSION:
        _fail("provenance-schema-version")
    if provenance.get("hermes_release") != _CANONICAL_TAG:
        _fail("canonical-release-mismatch")
    if provenance.get("source_repository") != _REPOSITORY:
        _fail("canonical-repository-mismatch")
    if provenance.get("source_commit") != _CANONICAL_COMMIT:
        _fail("canonical-source-commit-mismatch")
    scope = provenance.get("evidence_scope")
    if not isinstance(scope, dict) or scope.get("live_server_tested") is not False:
        _fail("historical-live-server-field-changed")
    entries = _fixture_entries(provenance)
    for entry in entries.values():
        _verify_fixture_entry(entry, _CANONICAL_ROOT, source_root)
    return entries


def _verify_scope(scope: str) -> None:
    objects, peeled = _release_tags()
    latest, latest_commit = _latest_release(objects, peeled)
    provenance = _load_object(_PROVENANCE_PATH)
    _verify_release_record(provenance, latest, latest_commit)
    source_root, temporary = _fetch_source_tree(_CANONICAL_COMMIT)
    try:
        entries = _verify_all_entries(provenance, source_root)
        if scope == "release-and-tool":
            path = "chat_completions/tool_progress_pair.sse"
            if entries.get(path, {}).get("evidence_kind") != _EXPECTED_KINDS[path]:
                _fail("tool-evidence-kind-mismatch")
            _verify_tool_fixture(_CANONICAL_ROOT / path)
            return
        for path, expected_kind in _EXPECTED_KINDS.items():
            if path == "chat_completions/tool_progress_pair.sse":
                continue
            if entries.get(path, {}).get("evidence_kind") != expected_kind:
                _fail(f"terminal-evidence-kind-mismatch:{path}")
        _verify_terminal_sse(
            _CANONICAL_ROOT / "chat_completions/terminal_length.sse",
            {
                "finish_reason": "length",
                "completed": False,
                "partial": True,
                "failed": False,
                "error_code": "output_truncated",
            },
        )
        _verify_terminal_sse(
            _CANONICAL_ROOT / "chat_completions/terminal_agent_error.sse",
            {
                "finish_reason": "error",
                "completed": False,
                "partial": False,
                "failed": True,
                "error_code": "agent_error",
            },
        )
        _verify_terminal_sse(
            _CANONICAL_ROOT
            / "chat_completions/terminal_task_exception_contradiction.sse",
            {
                "finish_reason": "error",
                "completed": True,
                "partial": False,
                "failed": True,
                "error_code": "agent_error",
            },
        )
        _verify_design_matrix(
            _CANONICAL_ROOT / "chat_completions/terminal_design_matrix.json"
        )
    finally:
        temporary.cleanup()


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("release-and-tool", "terminal"),
        required=True,
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the selected Phase 2 evidence gate."""
    scope = cast("str", _parse_args(arguments).scope)
    try:
        _verify_scope(scope)
    except ProvenanceError as error:
        print(str(error), file=sys.stderr)  # noqa: T201 - executable verifier output
        return 3 if str(error) == "latest-tag-verification-blocked" else 1
    print(f"phase2-provenance-ok:{scope}")  # noqa: T201 - executable verifier output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
