"""Deterministic builders for versioned Hermes contract fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from copy import deepcopy
import json
from pathlib import Path
from typing import Any


HERMES_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "hermes" / "v2026.7.7.2"


def _golden_path(relative_path: str | Path) -> Path:
    """Return a validated path beneath the immutable Hermes fixture root."""
    path = (HERMES_FIXTURE_ROOT / relative_path).resolve()
    if not path.is_relative_to(HERMES_FIXTURE_ROOT.resolve()):
        msg = f"Fixture path escapes the Hermes fixture root: {relative_path}"
        raise ValueError(msg)
    return path


def load_golden_bytes(relative_path: str | Path) -> bytes:
    """Load canonical fixture bytes without exposing a mutation path."""
    return _golden_path(relative_path).read_bytes()


def load_golden_json(relative_path: str | Path) -> dict[str, Any]:
    """Load a canonical JSON object as fresh state for each caller."""
    value = json.loads(load_golden_bytes(relative_path))
    if not isinstance(value, dict):
        msg = f"Golden JSON must contain an object: {relative_path}"
        raise TypeError(msg)
    return value


def _mapping_at(document: dict[str, Any], path: Sequence[str]) -> dict[str, Any]:
    """Return the mapping at a JSON object path."""
    current = document
    for key in path:
        value = current[key]
        if not isinstance(value, dict):
            msg = f"JSON path does not identify an object: {path}"
            raise TypeError(msg)
        current = value
    return current


def reorder_json_keys(
    document: dict[str, Any],
    key_order: Sequence[str],
    *,
    path: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a deep copy with one object's keys in the requested order."""
    result = deepcopy(document)
    target = _mapping_at(result, path)
    if len(key_order) != len(target) or set(key_order) != set(target):
        msg = "Requested key order must be a bijection with the object keys"
        raise ValueError(msg)
    reordered = {key: target[key] for key in key_order}
    if not path:
        return reordered
    parent = _mapping_at(result, path[:-1])
    parent[path[-1]] = reordered
    return result


def remove_json_key(document: dict[str, Any], path: Sequence[str]) -> dict[str, Any]:
    """Return a deep copy with the selected key removed."""
    if not path:
        raise ValueError("A key path is required")
    result = deepcopy(document)
    parent = _mapping_at(result, path[:-1])
    del parent[path[-1]]
    return result


def add_json_key(
    document: dict[str, Any], path: Sequence[str], value: Any
) -> dict[str, Any]:
    """Return a deep copy with a new key and a deep-copied value."""
    if not path:
        raise ValueError("A key path is required")
    result = deepcopy(document)
    parent = _mapping_at(result, path[:-1])
    key = path[-1]
    if key in parent:
        raise KeyError(key)
    parent[key] = deepcopy(value)
    return result


def partition_bytes(
    payload: bytes, split_points: Iterable[int] | None = None
) -> tuple[bytes, ...]:
    """Partition bytes one-by-one or at caller-selected deterministic points."""
    if split_points is None:
        return tuple(payload[index : index + 1] for index in range(len(payload)))

    points = tuple(sorted(set(split_points)))
    if any(point <= 0 or point >= len(payload) for point in points):
        raise ValueError("Split points must fall strictly inside the payload")
    boundaries = (0, *points, len(payload))
    return tuple(payload[start:end] for start, end in zip(boundaries, boundaries[1:]))
