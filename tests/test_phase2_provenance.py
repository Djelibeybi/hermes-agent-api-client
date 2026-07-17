# pyright: reportPrivateUsage=false
"""Adversarial tests for the Phase 2 provenance trust boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping

    from _pytest.capture import CaptureResult


_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "check_phase2_provenance.py"
_CANONICAL_FIXTURES = _ROOT / "tests" / "fixtures" / "hermes" / "v2026.7.7.2"
_LIFECYCLE_PATHS = (
    "chat_completions/tool_progress_pair.sse",
    "chat_completions/terminal_length.sse",
    "chat_completions/terminal_agent_error.sse",
    "chat_completions/terminal_task_exception_contradiction.sse",
    "chat_completions/terminal_design_matrix.json",
)
_KINDS = {
    "chat_completions/tool_progress_pair.sse": "tag-source-derived",
    "chat_completions/terminal_length.sse": "tag-source-derived",
    "chat_completions/terminal_agent_error.sse": "tag-source-derived",
    "chat_completions/terminal_task_exception_contradiction.sse": (
        "tag-source-derived"
    ),
    "chat_completions/terminal_design_matrix.json": "design-derived",
}


class _Cleanup(Protocol):
    def cleanup(self) -> None: ...


class _ProvenanceModule(Protocol):
    _REPOSITORY: str
    _FIXTURE_ROOT: Path
    _CANONICAL_ROOT: Path
    _PROVENANCE_PATH: Path
    _CANONICAL_TAG: str
    _CANONICAL_COMMIT: str
    _CANONICAL_TAG_OBJECT: str
    ProvenanceError: type[RuntimeError]

    def _load_object(self, path: Path) -> dict[str, object]: ...

    def _json_pairs(self, data: str) -> object: ...

    def _verify_fixture_entry(
        self,
        entry: Mapping[str, object],
        version_root: Path,
        source_root: Path,
        *,
        expected_release: str,
        expected_commit: str,
    ) -> None: ...

    def _verify_newer_release(
        self,
        release: Mapping[str, object],
        latest: str,
        latest_commit: str,
    ) -> None: ...

    def _normalize_lifecycle_events(
        self,
        entries: Mapping[str, Mapping[str, object]],
        version_root: Path,
    ) -> tuple[object, ...]: ...

    def _safe_fixture_path(self, version_root: Path, relative: str) -> Path: ...

    def _verify_design_matrix(self, path: Path) -> tuple[object, ...]: ...

    def _source_lines(
        self, source_root: Path, path: str, start: int, end: int
    ) -> bytes: ...

    def main(self, arguments: list[str] | None = None) -> int: ...


@dataclass(frozen=True)
class _ReleaseEvidence:
    release: str
    commit: str
    source_root: Path
    version_root: Path
    manifest: dict[str, object]


class _CleanupProbe:
    def __init__(self) -> None:
        self.called = False

    def cleanup(self) -> None:
        self.called = True


@pytest.fixture
def provenance() -> _ProvenanceModule:
    """Load the standalone verifier without making scripts importable."""
    spec = importlib.util.spec_from_file_location("phase2_provenance", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast("_ProvenanceModule", module)


def _run_git(root: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    assert executable is not None
    completed = subprocess.run(  # noqa: S603 - fixed executable, test-owned args
        (executable, *arguments),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _source_repository(tmp_path: Path, name: str) -> tuple[Path, str]:
    root = tmp_path / name
    source = root / "gateway" / "platforms" / "api_server.py"
    tests = root / "tests" / "gateway" / "test_api_server.py"
    source.parent.mkdir(parents=True)
    tests.parent.mkdir(parents=True)
    source.write_text("alpha = 1\nbeta = 2\ngamma = 3\n", encoding="utf-8")
    tests.write_text("def test_alpha():\n    assert True\n", encoding="utf-8")
    _run_git(root, "init", "-q")
    _run_git(root, "add", "gateway/platforms/api_server.py")
    _run_git(root, "add", "tests/gateway/test_api_server.py")
    _run_git(
        root,
        "-c",
        "user.name=Phase 2 Test",
        "-c",
        "user.email=phase2@example.invalid",
        "commit",
        "-q",
        "-m",
        "fixture source",
    )
    return root, _run_git(root, "rev-parse", "HEAD")


def _source_ref(
    provenance: _ProvenanceModule,
    source_root: Path,
    commit: str,
) -> dict[str, object]:
    path = "gateway/platforms/api_server.py"
    anchor = b"alpha = 1\nbeta = 2\n"
    assert (source_root / path).read_bytes().startswith(anchor)
    return {
        "repository": provenance._REPOSITORY,
        "commit": commit,
        "path": path,
        "line_start": 1,
        "line_end": 2,
        "anchor_sha256": hashlib.sha256(anchor).hexdigest(),
        "url": f"{provenance._REPOSITORY}/blob/{commit}/{path}#L1-L2",
    }


def _write_manifest(version_root: Path, manifest: Mapping[str, object]) -> None:
    version_root.mkdir(parents=True, exist_ok=True)
    (version_root / "provenance.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _release_evidence(
    provenance: _ProvenanceModule,
    tmp_path: Path,
    *,
    release: str,
    name: str,
    canonical_scope: bool,
) -> _ReleaseEvidence:
    source_root, commit = _source_repository(tmp_path, f"{name}-source")
    version_root = tmp_path / "fixtures" / release
    entries: list[dict[str, object]] = []
    source_ref = _source_ref(provenance, source_root, commit)
    for relative in _LIFECYCLE_PATHS:
        target = version_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = (_CANONICAL_FIXTURES / relative).read_bytes()
        target.write_bytes(payload)
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hermes_release": release,
                "source_commit": commit,
                "evidence_kind": _KINDS[relative],
                "source_refs": [dict(source_ref)],
                "reproduction": {
                    "mode": "isolated-test-evidence",
                    "procedure": ["Construct immutable local evidence."],
                    "configuration": {"live_server_invoked": False},
                },
                "semantic_assertions": ["Lifecycle evidence is locally complete."],
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 3,
        "hermes_release": release,
        "source_repository": provenance._REPOSITORY,
        "source_commit": commit,
        "fixtures": entries,
    }
    if canonical_scope:
        manifest["evidence_scope"] = {"live_server_tested": False}
    _write_manifest(version_root, manifest)
    return _ReleaseEvidence(release, commit, source_root, version_root, manifest)


def _latest_release_record(evidence: _ReleaseEvidence) -> dict[str, object]:
    fixture_root = f"tests/fixtures/hermes/{evidence.release}"
    return {
        "latest_evidence": {
            "hermes_release": evidence.release,
            "source_commit": evidence.commit,
            "evidence_kind": "immutable-tag-capture",
            "public_semantics": "identical",
            "fixture_root": fixture_root,
            "reproduction": {
                "mode": "isolated-test-evidence",
                "procedure": ["Validate the complete newer evidence root."],
                "configuration": {"live_server_invoked": False},
            },
            "semantic_assertions": ["Computed public lifecycle events are identical."],
            "difference_summary": {
                "canonical_fixture_root": "tests/fixtures/hermes/v-test-canonical",
                "newer_fixture_root": fixture_root,
                "changes": [
                    {
                        "canonical_path": _LIFECYCLE_PATHS[0],
                        "newer_path": _LIFECYCLE_PATHS[0],
                        "canonical_shape": "root-hermes",
                        "newer_shape": "root-hermes",
                        "public_event": "editor-controlled-and-non-authoritative",
                    }
                ],
                "normalized_public_events": {
                    "canonical": {"claimed": "identical"},
                    "newer": {"claimed": "identical"},
                },
            },
        }
    }


def _install_release_roots(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    fixture_root: Path,
    canonical: _ReleaseEvidence,
) -> None:
    monkeypatch.setattr(provenance, "_FIXTURE_ROOT", fixture_root)
    monkeypatch.setattr(provenance, "_CANONICAL_ROOT", canonical.version_root)
    monkeypatch.setattr(
        provenance, "_PROVENANCE_PATH", canonical.version_root / "provenance.json"
    )
    monkeypatch.setattr(provenance, "_CANONICAL_TAG", canonical.release)
    monkeypatch.setattr(provenance, "_CANONICAL_COMMIT", canonical.commit)


def _install_fetcher(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    releases: tuple[_ReleaseEvidence, ...],
) -> list[_CleanupProbe]:
    by_commit = {release.commit: release.source_root for release in releases}
    probes: list[_CleanupProbe] = []

    def fetch(commit: str) -> tuple[Path, _Cleanup]:
        probe = _CleanupProbe()
        probes.append(probe)
        return by_commit[commit], probe

    monkeypatch.setattr(provenance, "_fetch_source_tree", fetch)
    return probes


def _manifest_entries(evidence: _ReleaseEvidence) -> list[dict[str, object]]:
    entries = evidence.manifest["fixtures"]
    assert isinstance(entries, list)
    return cast("list[dict[str, object]]", entries)


def _rewrite(evidence: _ReleaseEvidence) -> None:
    _write_manifest(evidence.version_root, evidence.manifest)


def _replace_fixture_bytes(
    evidence: _ReleaseEvidence,
    relative: str,
    old: bytes,
    new: bytes,
) -> None:
    path = evidence.version_root / relative
    payload = path.read_bytes()
    assert payload.count(old) >= 1
    payload = payload.replace(old, new, 1)
    path.write_bytes(payload)
    entry = next(
        item for item in _manifest_entries(evidence) if item["path"] == relative
    )
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    _rewrite(evidence)


def _newer_harness(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    name: str,
) -> tuple[_ReleaseEvidence, _ReleaseEvidence, dict[str, object]]:
    fixture_root = tmp_path / "fixtures"
    canonical = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name=f"{name}-canonical",
        canonical_scope=True,
    )
    newer = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-newer",
        name=f"{name}-newer",
        canonical_scope=False,
    )
    _install_release_roots(provenance, monkeypatch, fixture_root, canonical)
    _install_fetcher(provenance, monkeypatch, (canonical, newer))
    return canonical, newer, _latest_release_record(newer)


def test_fixture_identity_is_bound_to_external_release_and_commit(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Reject mutually reinforcing identity fields that disagree externally."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name="identity",
        canonical_scope=True,
    )
    entry = _manifest_entries(evidence)[0]
    forged_commit = "0" * 40
    entry["hermes_release"] = "v9999.0"
    entry["source_commit"] = forged_commit
    source_refs = cast("list[dict[str, object]]", entry["source_refs"])
    for source_ref in source_refs:
        source_ref["commit"] = forged_commit
        source_ref["url"] = cast("str", source_ref["url"]).replace(
            evidence.commit, forged_commit
        )

    with pytest.raises(provenance.ProvenanceError):
        provenance._verify_fixture_entry(
            entry,
            evidence.version_root,
            evidence.source_root,
            expected_release=evidence.release,
            expected_commit=evidence.commit,
        )


def test_source_tree_head_must_equal_external_commit(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Reject valid anchors when the supplied repository is at another HEAD."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name="head",
        canonical_scope=True,
    )
    other_root, _ = _source_repository(tmp_path, "other-source")
    (other_root / "gateway" / "platforms" / "api_server.py").write_text(
        "different = True\n",
        encoding="utf-8",
    )
    _run_git(other_root, "add", "gateway/platforms/api_server.py")
    _run_git(
        other_root,
        "-c",
        "user.name=Phase 2 Test",
        "-c",
        "user.email=phase2@example.invalid",
        "commit",
        "-q",
        "-m",
        "different head",
    )

    with pytest.raises(provenance.ProvenanceError):
        provenance._verify_fixture_entry(
            _manifest_entries(evidence)[0],
            evidence.version_root,
            other_root,
            expected_release=evidence.release,
            expected_commit=evidence.commit,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-manifest",
        "empty-inventory",
        "missing-bytes",
        "stale-fixture-hash",
        "manifest-release",
        "entry-release",
        "manifest-commit",
        "entry-commit",
        "source-ref-commit",
        "stale-source-anchor",
        "behavioral-bytes",
    ],
)
def test_newer_release_rejects_unvalidated_or_different_evidence(  # noqa: C901
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Reject each missing, stale, mismatched, or behaviorally different input."""
    fixture_root = tmp_path / "fixtures"
    canonical = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name="canonical",
        canonical_scope=True,
    )
    newer = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-newer",
        name="newer",
        canonical_scope=False,
    )
    _install_release_roots(provenance, monkeypatch, fixture_root, canonical)
    probes = _install_fetcher(provenance, monkeypatch, (canonical, newer))
    release_record = _latest_release_record(newer)
    entries = _manifest_entries(newer)

    if mutation == "missing-manifest":
        (newer.version_root / "provenance.json").unlink()
    elif mutation == "empty-inventory":
        newer.manifest["fixtures"] = []
        _rewrite(newer)
    elif mutation == "missing-bytes":
        (newer.version_root / _LIFECYCLE_PATHS[0]).unlink()
    elif mutation == "stale-fixture-hash":
        entries[0]["sha256"] = "0" * 64
        _rewrite(newer)
    elif mutation == "manifest-release":
        newer.manifest["hermes_release"] = "v-wrong"
        _rewrite(newer)
    elif mutation == "entry-release":
        entries[0]["hermes_release"] = "v-wrong"
        _rewrite(newer)
    elif mutation == "manifest-commit":
        newer.manifest["source_commit"] = "0" * 40
        _rewrite(newer)
    elif mutation == "entry-commit":
        entries[0]["source_commit"] = "0" * 40
        _rewrite(newer)
    elif mutation == "source-ref-commit":
        refs = cast("list[dict[str, object]]", entries[0]["source_refs"])
        refs[0]["commit"] = "0" * 40
        _rewrite(newer)
    elif mutation == "stale-source-anchor":
        refs = cast("list[dict[str, object]]", entries[0]["source_refs"])
        refs[0]["anchor_sha256"] = "0" * 64
        _rewrite(newer)
    else:
        tool_path = newer.version_root / _LIFECYCLE_PATHS[0]
        payload = tool_path.read_bytes().replace(b"call_terminal_1", b"call_terminal_2")
        tool_path.write_bytes(payload)
        entries[0]["sha256"] = hashlib.sha256(payload).hexdigest()
        _rewrite(newer)

    with pytest.raises(provenance.ProvenanceError):
        provenance._verify_newer_release(
            release_record,
            newer.release,
            newer.commit,
        )
    assert all(probe.called for probe in probes)


def test_complete_newer_release_uses_bytes_not_declaration_maps(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Accept equal validated bytes regardless of editor declaration maps."""
    fixture_root = tmp_path / "fixtures"
    canonical = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name="canonical-positive",
        canonical_scope=True,
    )
    newer = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-newer",
        name="newer-positive",
        canonical_scope=False,
    )
    _install_release_roots(provenance, monkeypatch, fixture_root, canonical)
    probes = _install_fetcher(provenance, monkeypatch, (canonical, newer))
    release_record = _latest_release_record(newer)
    latest_evidence = cast("dict[str, object]", release_record["latest_evidence"])
    difference = cast("dict[str, object]", latest_evidence["difference_summary"])
    difference["normalized_public_events"] = {
        "canonical": {"self_attested": "different-a"},
        "newer": {"self_attested": "different-b"},
    }

    provenance._verify_newer_release(release_record, newer.release, newer.commit)

    assert probes
    assert all(probe.called for probe in probes)


@pytest.mark.parametrize(
    ("relative", "old", "first_value"),
    [
        (_LIFECYCLE_PATHS[0], b'"toolCallId": "call_terminal_1"', b'"other"'),
        (_LIFECYCLE_PATHS[0], b'"tool": "terminal"', b'"other"'),
        (_LIFECYCLE_PATHS[0], b'"status": "running"', b'"completed"'),
        (
            _LIFECYCLE_PATHS[2],
            b'"hermes": {',
            b'{"completed": false}, "hermes": {',
        ),
        (_LIFECYCLE_PATHS[2], b'"finish_reason": "error"', b'"stop"'),
        (_LIFECYCLE_PATHS[2], b'"completed": false', b"true"),
        (_LIFECYCLE_PATHS[2], b'"failed": true', b"false"),
        (_LIFECYCLE_PATHS[2], b'"partial": false', b"true"),
        (_LIFECYCLE_PATHS[2], b'"error_code": "agent_error"', b'"other"'),
    ],
)
@pytest.mark.parametrize("same_value", [True, False], ids=("same", "conflicting"))
def test_newer_release_rejects_every_approved_duplicate_family(  # noqa: PLR0913
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relative: str,
    old: bytes,
    first_value: bytes,
    *,
    same_value: bool,
) -> None:
    """Reject duplicates even when ordinary JSON would retain canonical last value."""
    _, newer, release_record = _newer_harness(
        provenance, monkeypatch, tmp_path, name="duplicate"
    )
    key, canonical_value = old.split(b": ", 1)
    if key == b'"hermes"':
        duplicate = b'{"completed": false}, "hermes": {' if same_value else first_value
        replacement = key + b": " + duplicate
    else:
        duplicate_value = canonical_value if same_value else first_value
        replacement = key + b": " + duplicate_value + b", " + old
    _replace_fixture_bytes(newer, relative, old, replacement)

    with pytest.raises(provenance.ProvenanceError):
        provenance._verify_newer_release(release_record, newer.release, newer.commit)


def test_newer_release_accepts_duplicate_inside_ignored_additive_data(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep additive duplicate compatibility aligned with the production projector."""
    _, newer, release_record = _newer_harness(
        provenance, monkeypatch, tmp_path, name="additive"
    )
    old = '"emoji": "🖥️"'.encode()
    _replace_fixture_bytes(newer, _LIFECYCLE_PATHS[0], old, old + b", " + old)

    provenance._verify_newer_release(release_record, newer.release, newer.commit)


@pytest.mark.parametrize("relative", _LIFECYCLE_PATHS)
@pytest.mark.parametrize("attack", ["unknown", "swapped"])
def test_lifecycle_evidence_roles_are_exact_for_every_required_path(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relative: str,
    attack: str,
) -> None:
    """Reject unknown and opposite evidence roles in release-agnostic validation."""
    _, newer, release_record = _newer_harness(
        provenance, monkeypatch, tmp_path, name="role"
    )
    entry = next(item for item in _manifest_entries(newer) if item["path"] == relative)
    entry["evidence_kind"] = (
        "editor-invented"
        if attack == "unknown"
        else (
            "tag-source-derived"
            if _KINDS[relative] == "design-derived"
            else "design-derived"
        )
    )
    _rewrite(newer)

    with pytest.raises(
        provenance.ProvenanceError, match=r"^lifecycle-evidence-role-mismatch$"
    ):
        provenance._verify_newer_release(release_record, newer.release, newer.commit)


def _assert_closed_error(error: BaseException, *canaries: str) -> None:
    rendered = (
        str(error),
        repr(error),
        repr(error.args),
        "".join(traceback.format_exception(error)),
    )
    for canary in canaries:
        assert all(canary not in value for value in rendered)
    assert len(error.args) == 1
    assert isinstance(error.args[0], str)
    assert "\n" not in error.args[0]
    assert error.__cause__ is None
    assert error.__context__ is None


def test_fixture_path_failure_is_closed_and_context_free(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Do not retain a missing editor-controlled fixture path or OSError."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v-test-canonical",
        name="fixture-canary",
        canonical_scope=True,
    )
    entry = _manifest_entries(evidence)[0]
    canary = "fixture-secret-canary\nforged-line.sse"
    entry["path"] = canary
    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._verify_fixture_entry(
            entry,
            evidence.version_root,
            evidence.source_root,
            expected_release=evidence.release,
            expected_commit=evidence.commit,
        )
    _assert_closed_error(caught.value, "fixture-secret-canary", "forged-line")


def test_source_path_and_range_failures_are_closed(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Do not disclose source paths or ranges from anchor failures."""
    source_root, _ = _source_repository(tmp_path, "source-canary")
    for path, start, end, canaries in (
        ("source-secret-canary\nforged.py", 1, 2, ("source-secret-canary",)),
        (
            "gateway/platforms/api_server.py",
            1,
            987654321,
            ("987654321",),
        ),
    ):
        with pytest.raises(provenance.ProvenanceError) as caught:
            provenance._source_lines(source_root, path, start, end)
        _assert_closed_error(caught.value, *canaries)


def test_terminal_case_id_failure_is_closed(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Do not disclose design-matrix case identifiers."""
    canary = "case-secret-canary\nforged-line"
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decision_refs": ["D-01", "D-02", "D-03", "D-04"],
                "cases": [
                    {
                        "id": canary,
                        "wire": {"finish_reason": "stop"},
                        "expected": {"disposition": "accept"},
                        "decision_refs": ["D-01"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._verify_design_matrix(path)
    _assert_closed_error(caught.value, "case-secret-canary", "forged-line")


def test_main_prints_one_closed_code_for_real_canary_failure(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep the executable verifier's stderr closed and single-line."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v9999.1",
        name="cli-canary",
        canonical_scope=True,
    )
    canary = "cli-secret-canary\nforged-line.sse"
    _manifest_entries(evidence)[0]["path"] = canary
    _rewrite(evidence)
    _install_release_roots(provenance, monkeypatch, tmp_path / "fixtures", evidence)
    _install_fetcher(provenance, monkeypatch, (evidence,))
    monkeypatch.setattr(
        provenance,
        "_release_tags",
        lambda: ({evidence.release: "tag-object"}, {evidence.release: evidence.commit}),
    )

    assert provenance.main(["--scope", "release-and-tool"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "missing-fixture\n"
    assert "cli-secret-canary" not in captured.err
    assert "forged-line" not in captured.err


def _deep_json(*, object_root: bool) -> str:
    depth = 20_000
    if object_root:
        return '{"recursive-secret-canary":' * depth + "0" + "}" * depth
    return "[" * depth + '"recursive-secret-canary"' + "]" * depth


def _oversized_integer_json() -> str:
    return '{"oversized-secret-canary":' + "9" * 5_000 + "}"


def _install_canonical_cli_identity(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    evidence: _ReleaseEvidence,
) -> None:
    tag_object = "a" * 40
    monkeypatch.setattr(provenance, "_CANONICAL_TAG_OBJECT", tag_object)
    monkeypatch.setattr(
        provenance,
        "_release_tags",
        lambda: ({evidence.release: tag_object}, {evidence.release: evidence.commit}),
    )
    evidence.manifest["release_verification"] = {
        "canonical_tag": evidence.release,
        "canonical_tag_object": tag_object,
        "canonical_peeled_commit": evidence.commit,
        "observed_latest_numeric_tag": evidence.release,
        "observed_latest_peeled_commit": evidence.commit,
        "compatibility_disposition": "canonical-current",
    }


def _canonical_cli_evidence(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    release: str,
    name: str,
) -> _ReleaseEvidence:
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release=release,
        name=name,
        canonical_scope=True,
    )
    _install_release_roots(provenance, monkeypatch, tmp_path / "fixtures", evidence)
    _install_fetcher(provenance, monkeypatch, (evidence,))
    _install_canonical_cli_identity(provenance, monkeypatch, evidence)
    return evidence


def _assert_closed_cli_failure(
    captured: CaptureResult[str], code: str, *canaries: str
) -> None:
    assert captured.out == ""
    assert captured.err == f"{code}\n"
    assert "Traceback" not in captured.err
    for canary in canaries:
        assert canary not in captured.err


def test_recursive_lifecycle_json_is_a_closed_provenance_error(
    provenance: _ProvenanceModule,
) -> None:
    """Translate decoder recursion at the lifecycle pair boundary."""
    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._json_pairs(_deep_json(object_root=False))

    assert caught.value.args == ("invalid-sse-json",)
    _assert_closed_error(
        caught.value,
        "recursive-secret-canary",
        "RecursionError",
    )


def test_recursive_object_file_is_a_closed_provenance_error(
    provenance: _ProvenanceModule,
    tmp_path: Path,
) -> None:
    """Translate decoder recursion at the provenance/design object boundary."""
    path = tmp_path / "deep-object.json"
    path.write_text(_deep_json(object_root=True), encoding="utf-8")

    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._load_object(path)

    assert caught.value.args == ("invalid-provenance-json",)
    _assert_closed_error(
        caught.value,
        "recursive-secret-canary",
        "RecursionError",
    )


def test_main_closes_recursive_lifecycle_json_failure(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Emit one closed line when canonical lifecycle JSON exceeds recursion."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v9999.2",
        name="recursive-lifecycle-cli",
        canonical_scope=True,
    )
    _install_release_roots(provenance, monkeypatch, tmp_path / "fixtures", evidence)
    _install_fetcher(provenance, monkeypatch, (evidence,))
    _install_canonical_cli_identity(provenance, monkeypatch, evidence)
    tool_path = evidence.version_root / _LIFECYCLE_PATHS[0]
    payload = tool_path.read_text(encoding="utf-8")
    payload = payload.replace(
        'data: {"tool": "terminal"',
        "data: " + _deep_json(object_root=False),
        1,
    )
    tool_path.write_text(payload, encoding="utf-8")
    entry = next(
        item
        for item in _manifest_entries(evidence)
        if item["path"] == _LIFECYCLE_PATHS[0]
    )
    entry["sha256"] = hashlib.sha256(tool_path.read_bytes()).hexdigest()
    _rewrite(evidence)

    assert provenance.main(["--scope", "release-and-tool"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid-sse-json\n"
    assert "recursive-secret-canary" not in captured.err
    assert "Traceback" not in captured.err


def test_main_closes_recursive_object_file_failure(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Emit one closed line when the provenance object exceeds recursion."""
    evidence = _release_evidence(
        provenance,
        tmp_path,
        release="v9999.3",
        name="recursive-object-cli",
        canonical_scope=True,
    )
    _install_release_roots(provenance, monkeypatch, tmp_path / "fixtures", evidence)
    _install_fetcher(provenance, monkeypatch, (evidence,))
    _install_canonical_cli_identity(provenance, monkeypatch, evidence)
    (evidence.version_root / "provenance.json").write_text(
        _deep_json(object_root=True),
        encoding="utf-8",
    )

    assert provenance.main(["--scope", "terminal"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid-provenance-json\n"
    assert "recursive-secret-canary" not in captured.err
    assert "Traceback" not in captured.err


def test_oversized_lifecycle_integer_is_a_closed_provenance_error(
    provenance: _ProvenanceModule,
) -> None:
    """Translate Python's integer conversion limit at the SSE JSON boundary."""
    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._json_pairs(_oversized_integer_json())

    assert caught.value.args == ("invalid-sse-json",)
    _assert_closed_error(caught.value, "oversized-secret-canary", "ValueError")


@pytest.mark.parametrize("boundary", ["object", "design-matrix"])
def test_oversized_object_integer_is_a_closed_provenance_error(
    provenance: _ProvenanceModule,
    tmp_path: Path,
    boundary: str,
) -> None:
    """Translate Python's integer limit at each object-file consumer."""
    path = tmp_path / f"{boundary}.json"
    path.write_text(_oversized_integer_json(), encoding="utf-8")
    verify = (
        provenance._load_object
        if boundary == "object"
        else provenance._verify_design_matrix
    )

    with pytest.raises(provenance.ProvenanceError) as caught:
        verify(path)

    assert caught.value.args == ("invalid-provenance-json",)
    _assert_closed_error(caught.value, "oversized-secret-canary", "ValueError")


def test_main_closes_oversized_lifecycle_integer(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Emit one finite SSE code for a lifecycle integer conversion failure."""
    evidence = _canonical_cli_evidence(
        provenance,
        monkeypatch,
        tmp_path,
        release="v9999.4",
        name="oversized-lifecycle-cli",
    )
    relative = _LIFECYCLE_PATHS[0]
    path = evidence.version_root / relative
    payload = path.read_text(encoding="utf-8")
    first_data = next(
        line for line in payload.splitlines() if line.startswith("data: ")
    )
    replacement = "data: " + _oversized_integer_json()
    path.write_text(payload.replace(first_data, replacement, 1), encoding="utf-8")
    entry = next(
        item for item in _manifest_entries(evidence) if item["path"] == relative
    )
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _rewrite(evidence)

    assert provenance.main(["--scope", "release-and-tool"]) == 1
    _assert_closed_cli_failure(
        capsys.readouterr(), "invalid-sse-json", "oversized-secret-canary"
    )


@pytest.mark.parametrize("boundary", ["provenance", "design-matrix"])
def test_main_closes_oversized_object_integer(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    boundary: str,
) -> None:
    """Emit one finite object code for provenance and matrix JSON limits."""
    evidence = _canonical_cli_evidence(
        provenance,
        monkeypatch,
        tmp_path,
        release="v9999.5",
        name=f"oversized-{boundary}-cli",
    )
    if boundary == "provenance":
        path = evidence.version_root / "provenance.json"
    else:
        relative = "chat_completions/terminal_design_matrix.json"
        path = evidence.version_root / relative
        entry = next(
            item for item in _manifest_entries(evidence) if item["path"] == relative
        )
        entry["sha256"] = hashlib.sha256(_oversized_integer_json().encode()).hexdigest()
        _rewrite(evidence)
    path.write_text(_oversized_integer_json(), encoding="utf-8")

    assert provenance.main(["--scope", "terminal"]) == 1
    _assert_closed_cli_failure(
        capsys.readouterr(), "invalid-provenance-json", "oversized-secret-canary"
    )


def _malformed_matrix(location: str, invalid: object) -> dict[str, object]:
    matrix = cast(
        "dict[str, object]",
        json.loads(
            (
                _CANONICAL_FIXTURES / "chat_completions/terminal_design_matrix.json"
            ).read_text(encoding="utf-8")
        ),
    )
    cases = matrix["cases"]
    assert isinstance(cases, list)
    first_case = cast("object", cases[0])
    assert isinstance(first_case, dict)
    case = cast("dict[str, object]", first_case)
    if location == "root-refs":
        matrix["decision_refs"] = [invalid]
    elif location == "case-refs":
        case["decision_refs"] = [invalid]
    else:
        wire = case["wire"]
        assert isinstance(wire, dict)
        wire["finish_reason"] = invalid
    return matrix


@pytest.mark.parametrize("invalid", [[], {}], ids=["list", "dict"])
@pytest.mark.parametrize(
    ("location", "code"),
    [
        ("root-refs", "terminal-matrix-decision-set"),
        ("case-refs", "invalid-terminal-case-citations"),
        ("finish-reason", "missing-applicable-terminal-citation"),
    ],
)
def test_malformed_matrix_scalars_are_closed_direct_and_cli(  # noqa: PLR0913
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    location: str,
    code: str,
    invalid: object,
) -> None:
    """Reject unhashable matrix values with finite direct and CLI codes."""
    matrix = _malformed_matrix(location, invalid)
    payload = (json.dumps(matrix) + "\n").encode()
    direct_path = tmp_path / "direct-matrix.json"
    direct_path.write_bytes(payload)
    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._verify_design_matrix(direct_path)
    assert caught.value.args == (code,)
    _assert_closed_error(caught.value, "TypeError")

    evidence = _canonical_cli_evidence(
        provenance,
        monkeypatch,
        tmp_path,
        release="v9999.6",
        name=f"matrix-{location}",
    )
    relative = "chat_completions/terminal_design_matrix.json"
    matrix_path = evidence.version_root / relative
    matrix_path.write_bytes(payload)
    entry = next(
        item for item in _manifest_entries(evidence) if item["path"] == relative
    )
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    _rewrite(evidence)

    assert provenance.main(["--scope", "terminal"]) == 1
    _assert_closed_cli_failure(capsys.readouterr(), code, "TypeError")


def test_nul_fixture_path_is_closed_direct_and_cli(
    provenance: _ProvenanceModule,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject an invalid manifest path without retaining it or its exception."""
    evidence = _canonical_cli_evidence(
        provenance,
        monkeypatch,
        tmp_path,
        release="v9999.7",
        name="nul-fixture-path",
    )
    entry = _manifest_entries(evidence)[0]
    canary = "fixture-secret-canary\0.sse"
    entry["path"] = canary
    _rewrite(evidence)

    with pytest.raises(provenance.ProvenanceError) as caught:
        provenance._verify_fixture_entry(
            entry,
            evidence.version_root,
            evidence.source_root,
            expected_release=evidence.release,
            expected_commit=evidence.commit,
        )
    assert caught.value.args == ("invalid-fixture-path",)
    _assert_closed_error(caught.value, "fixture-secret-canary", "ValueError")

    assert provenance.main(["--scope", "release-and-tool"]) == 1
    _assert_closed_cli_failure(
        capsys.readouterr(), "invalid-fixture-path", "fixture-secret-canary"
    )
