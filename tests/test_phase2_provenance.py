# pyright: reportPrivateUsage=false
"""Adversarial tests for the Phase 2 provenance trust boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping


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
    ProvenanceError: type[RuntimeError]

    def _load_object(self, path: Path) -> dict[str, object]: ...

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
