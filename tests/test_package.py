"""Verify package metadata and public exports."""

from __future__ import annotations

from importlib.metadata import metadata, version
from pathlib import Path


def test_distribution_metadata_and_typed_marker() -> None:
    """Distribution metadata identifies a typed Python 3.13 package."""
    assert version("hermes-agent-api-client") == "0.1.0"
    package_metadata = metadata("hermes-agent-api-client")
    assert package_metadata["Requires-Python"] == ">=3.13"
    assert package_metadata["License-Expression"] == "UPL-1.0"

    package_root = Path(__file__).parents[1] / "src" / "hermes_agent_api_client"
    assert (package_root / "py.typed").is_file()


def test_public_version_is_static() -> None:
    """The import package exposes its static distribution version."""
    import hermes_agent_api_client  # noqa: PLC0415

    assert hermes_agent_api_client.__version__ == "0.1.0"
