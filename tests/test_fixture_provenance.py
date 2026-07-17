# pyright: reportPrivateUsage=false
"""Offline provenance checks for the immutable Hermes contract fixtures.

The fixtures are the only specification of the Hermes streaming contract: the
upstream server documents neither the `hermes` lifecycle block nor the terminal
semantics this client depends on. These checks therefore guard the evidence
itself — that no fixture drifted from its recorded hash, that each still carries
the facts it was captured to demonstrate, and that the design matrix continues
to agree with the client's own terminal mapping rather than a restatement of it.

Release identity and upstream source anchoring are deliberately not verified
here; both required cloning the upstream repository over the network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from hermes_agent_api_client.models import TerminalEvent, _require_lifecycle_text
from hermes_agent_api_client.protocol import (
    _MISSING_JSON_MEMBER,
    _json_object_pairs_hook,
    _JsonObjectPairs,
    _project_chat_chunk_object,
    _project_terminal_metadata,
    _project_tool_progress_object,
)
from hermes_agent_api_client.sse import _map_terminal_event

if TYPE_CHECKING:
    from collections.abc import Mapping

_CANONICAL_TAG = "v2026.7.7.2"
_CANONICAL_COMMIT = "9de9c25f620ff7f1ce0fd5457d596052d5159596"
_REPOSITORY = "https://github.com/NousResearch/hermes-agent"
_CANONICAL_ROOT = (
    Path(__file__).resolve().parent / "fixtures" / "hermes" / _CANONICAL_TAG
)
_PROVENANCE_PATH = _CANONICAL_ROOT / "provenance.json"
_PROVENANCE_SCHEMA_VERSION = 3
_DECISIONS = frozenset({"D-01", "D-02", "D-03", "D-04"})
_TOOL_FIXTURE = "chat_completions/tool_progress_pair.sse"
_DESIGN_MATRIX = "chat_completions/terminal_design_matrix.json"
_TERMINAL_RECORD_COUNT = 2
_TOOL_RECORD_COUNT = 4
_EXPECTED_KINDS = {
    "capabilities/supported.json": "immutable-tag-capture",
    "chat_completions/complete.sse": "synthetic-derived",
    _TOOL_FIXTURE: "tag-source-derived",
    "chat_completions/terminal_length.sse": "tag-source-derived",
    "chat_completions/terminal_agent_error.sse": "tag-source-derived",
    "chat_completions/terminal_task_exception_contradiction.sse": "tag-source-derived",
    _DESIGN_MATRIX: "design-derived",
}
# One row per terminal fixture: the lifecycle facts it must carry, and whether
# the client is required to reject it.
_TERMINAL_FIXTURES: tuple[tuple[str, dict[str, object], bool], ...] = (
    (
        "chat_completions/terminal_length.sse",
        {
            "finish_reason": "length",
            "completed": False,
            "partial": True,
            "failed": False,
            "error_code": "output_truncated",
        },
        False,
    ),
    (
        "chat_completions/terminal_agent_error.sse",
        {
            "finish_reason": "error",
            "completed": False,
            "partial": False,
            "failed": True,
            "error_code": "agent_error",
        },
        False,
    ),
    (
        "chat_completions/terminal_task_exception_contradiction.sse",
        {
            "finish_reason": "error",
            "completed": True,
            "partial": False,
            "failed": True,
            "error_code": "agent_error",
        },
        True,
    ),
)
_LIFECYCLE_FIELDS = ("completed", "failed", "partial", "error_code")


def _manifest() -> dict[str, Any]:
    """Load the recorded provenance manifest."""
    value = json.loads(_PROVENANCE_PATH.read_bytes())
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _entries() -> dict[str, Mapping[str, Any]]:
    """Return manifest fixture entries keyed by their declared path."""
    fixtures = _manifest()["fixtures"]
    assert isinstance(fixtures, list)
    entries: dict[str, Mapping[str, Any]] = {}
    for entry in cast("list[Mapping[str, Any]]", fixtures):
        path = entry["path"]
        assert isinstance(path, str)
        assert path not in entries, "duplicate fixture entry"
        entries[path] = entry
    return entries


def _sse_records(payload: bytes) -> list[tuple[str | None, str]]:
    """Frame fixture bytes the way the production decoder frames a stream."""
    text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    records: list[tuple[str | None, str]] = []
    for block in text.strip("\n").split("\n\n"):
        event: str | None = None
        data: str | None = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        assert data is not None, "fixture record carries no data line"
        records.append((event, data))
    return records


def _json_pairs(data: str) -> object:
    """Decode one record while retaining duplicate-member evidence."""
    return json.loads(data, object_pairs_hook=_json_object_pairs_hook)


def _raw_member(value: object, name: str) -> object:
    """Read a member straight off the undecoded wire object."""
    if not isinstance(value, _JsonObjectPairs):
        return _MISSING_JSON_MEMBER
    result: object = _MISSING_JSON_MEMBER
    for member_name, member_value in value.pairs:
        if member_name == name:
            result = member_value
    return result


def _terminal_event(wire: Mapping[str, Any]) -> TerminalEvent | None:
    """Derive the public terminal event using the client's own mapping."""
    hermes_value = wire.get("hermes", _MISSING_JSON_MEMBER)
    if hermes_value is _MISSING_JSON_MEMBER:
        projected: object = _MISSING_JSON_MEMBER
    elif isinstance(hermes_value, dict):
        members = cast("dict[str, object]", hermes_value)
        projected = _JsonObjectPairs(tuple(members.items()))
    else:
        return None
    metadata = _project_terminal_metadata(projected)
    if metadata is None:
        return None
    finish = wire.get("finish_reason")
    if finish is not None and type(finish) is not str:
        return None
    event = _map_terminal_event(finish, metadata)
    return event if isinstance(event, TerminalEvent) else None


def _public_event(event: TerminalEvent) -> dict[str, object]:
    """Render a terminal event the way the design matrix records it."""
    reason = event.failure_reason
    return {
        "outcome": event.outcome.value,
        "partial": event.partial,
        "failure_reason": None if reason is None else reason.value,
    }


def _is_lifecycle_text(value: object) -> bool:
    """Apply the client's own lifecycle-text rule rather than restating it."""
    try:
        _require_lifecycle_text(value)
    except ValueError:
        return False
    return True


def test_manifest_records_the_canonical_release_identity() -> None:
    """The manifest pins the exact upstream release the fixtures came from."""
    manifest = _manifest()

    assert manifest["schema_version"] == _PROVENANCE_SCHEMA_VERSION
    assert manifest["hermes_release"] == _CANONICAL_TAG
    assert manifest["source_repository"] == _REPOSITORY
    assert manifest["source_commit"] == _CANONICAL_COMMIT


def test_manifest_describes_every_fixture_file_and_no_others() -> None:
    """No fixture escapes the manifest and no manifest entry lacks a file."""
    on_disk = {
        str(path.relative_to(_CANONICAL_ROOT).as_posix())
        for path in _CANONICAL_ROOT.rglob("*")
        if path.is_file()
    } - {"provenance.json"}

    assert set(_entries()) == on_disk


@pytest.mark.parametrize("path", sorted(_EXPECTED_KINDS))
def test_fixture_bytes_still_match_the_recorded_hash(path: str) -> None:
    """A fixture edited after capture stops being the evidence it claims."""
    entry = _entries()[path]
    digest = hashlib.sha256((_CANONICAL_ROOT / path).read_bytes()).hexdigest()

    assert digest == entry["sha256"]


@pytest.mark.parametrize("path", sorted(_EXPECTED_KINDS))
def test_every_entry_carries_the_canonical_identity_and_role(path: str) -> None:
    """Each fixture states the release, commit, and evidence role it plays."""
    entry = _entries()[path]

    assert entry["hermes_release"] == _CANONICAL_TAG
    assert entry["source_commit"] == _CANONICAL_COMMIT
    assert entry["evidence_kind"] == _EXPECTED_KINDS[path]


def test_evidence_scope_keeps_admitting_what_the_fixtures_cannot_prove() -> None:
    """Captured fixtures must never be recorded as live-server evidence."""
    scope = _manifest()["evidence_scope"]

    assert scope["live_server_tested"] is False
    assert "live-server-compatibility" in scope["does_not_prove"]


def test_tool_fixture_proves_correlated_ordered_progress() -> None:
    """The tool pair demonstrates one correlated running/completed lifecycle."""
    records = _sse_records((_CANONICAL_ROOT / _TOOL_FIXTURE).read_bytes())
    assert len(records) == _TOOL_RECORD_COUNT

    progress = [
        _project_tool_progress_object(_json_pairs(data)) for _, data in records[:2]
    ]
    running, completed = progress
    assert running is not None
    assert completed is not None
    assert [name for name, _ in records[:2]] == ["hermes.tool.progress"] * 2
    assert running["status"] == "running"
    assert completed["status"] == "completed"
    for record in (running, completed):
        assert _is_lifecycle_text(record["toolCallId"])
        assert _is_lifecycle_text(record["tool"])
    assert running["toolCallId"] == completed["toolCallId"]
    assert running["tool"] == completed["tool"]
    assert records[3] == (None, "[DONE]")


@pytest.mark.parametrize(
    ("path", "expected", "expect_rejection"),
    _TERMINAL_FIXTURES,
    ids=[path.rsplit("/", 1)[-1] for path, _, _ in _TERMINAL_FIXTURES],
)
def test_terminal_fixture_carries_the_lifecycle_facts_it_demonstrates(
    path: str,
    expected: dict[str, object],
    expect_rejection: bool,  # noqa: FBT001 - parametrized row, not a call-site flag
) -> None:
    """Each terminal fixture still encodes its exact lifecycle combination."""
    records = _sse_records((_CANONICAL_ROOT / path).read_bytes())
    assert len(records) == _TERMINAL_RECORD_COUNT
    assert records[1] == (None, "[DONE]")

    projected = _project_chat_chunk_object(_json_pairs(records[0][1]))
    assert projected is not None
    choices = cast("list[dict[str, Any]]", projected.document["choices"])
    assert choices[0]["finish_reason"] == expected["finish_reason"]

    metadata = projected.terminal_metadata
    assert metadata.root_present
    facts = {
        name: getattr(metadata, name)
        for name in _LIFECYCLE_FIELDS
        if getattr(metadata, name) is not _MISSING_JSON_MEMBER
    }
    assert facts == {
        name: value for name, value in expected.items() if name != "finish_reason"
    }

    event = _map_terminal_event(choices[0]["finish_reason"], metadata)
    assert isinstance(event, TerminalEvent) is not expect_rejection


@pytest.mark.parametrize(
    "path",
    [path for path, _, _ in _TERMINAL_FIXTURES],
    ids=[path.rsplit("/", 1)[-1] for path, _, _ in _TERMINAL_FIXTURES],
)
def test_terminal_fixture_still_carries_its_raw_error_canaries(path: str) -> None:
    """Leak tests are vacuous unless the fixture really carries raw error text."""
    records = _sse_records((_CANONICAL_ROOT / path).read_bytes())
    raw = _json_pairs(records[0][1])

    assert _raw_member(raw, "error") is not _MISSING_JSON_MEMBER
    assert _raw_member(_raw_member(raw, "hermes"), "error") is not _MISSING_JSON_MEMBER


def test_design_matrix_agrees_with_the_client_terminal_mapping() -> None:
    """Every recorded matrix row must match what the client actually decides."""
    matrix = json.loads((_CANONICAL_ROOT / _DESIGN_MATRIX).read_bytes())
    assert matrix["schema_version"] == 1
    assert set(cast("list[str]", matrix["decision_refs"])) == _DECISIONS
    cases = cast("list[Mapping[str, Any]]", matrix["cases"])
    assert cases

    seen: set[str] = set()
    for case in cases:
        case_id = cast("str", case["id"])
        assert case_id not in seen
        seen.add(case_id)
        refs = set(cast("list[str]", case["decision_refs"]))
        assert refs
        assert refs <= _DECISIONS

        wire = cast("Mapping[str, Any]", case["wire"])
        expected = cast("Mapping[str, Any]", case["expected"])
        event = _terminal_event(wire)
        if expected["disposition"] == "accept":
            assert event is not None, case_id
            assert _public_event(event) == expected["public_event"], case_id
        else:
            assert expected["disposition"] == "reject", case_id
            assert expected["error"] == "HermesProtocolError", case_id
            assert event is None, case_id
