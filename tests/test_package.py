"""Verify package metadata and public exports."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from importlib.metadata import metadata, version
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def built_distributions() -> tuple[Path, Path]:
    """Build and return the sole wheel and source distribution."""
    project_root = Path(__file__).parents[1]
    subprocess.run(["uv", "build"], cwd=project_root, check=True)  # noqa: S607

    wheels = list((project_root / "dist").glob("*.whl"))
    sdists = list((project_root / "dist").glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    return (wheels[0], sdists[0])


def _run_distribution_verifier(
    *archives: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the standalone distribution verifier with captured output."""
    project_root = Path(__file__).parents[1]
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(project_root / "scripts" / "verify_dist.py"),
            *(str(archive) for archive in archives),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )


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


def test_public_exports_are_exact() -> None:
    """The package exports only the approved typed public API."""
    import hermes_agent_api_client  # noqa: PLC0415

    assert set(hermes_agent_api_client.__all__) == {
        "AssistantDeltaEvent",
        "HermesAgentApiClient",
        "HermesAuthenticationError",
        "HermesCapabilities",
        "HermesContractError",
        "HermesEvent",
        "HermesHttpStatusError",
        "HermesProtocolError",
        "HermesTransportError",
        "KeepaliveEvent",
        "TerminalEvent",
        "TerminalOutcome",
        "ToolProgressEvent",
        "UsageEvent",
        "__version__",
    }


def test_distribution_archives_contain_only_release_files(
    built_distributions: tuple[Path, Path],
) -> None:
    """Built archives include the package and exclude development artifacts."""
    wheel_path, sdist_path = built_distributions

    required_package_suffixes = {
        "hermes_agent_api_client/__init__.py",
        "hermes_agent_api_client/client.py",
        "hermes_agent_api_client/models.py",
        "hermes_agent_api_client/protocol.py",
        "hermes_agent_api_client/sse.py",
        "hermes_agent_api_client/py.typed",
    }
    with zipfile.ZipFile(wheel_path) as wheel:
        wheel_names = set(wheel.namelist())

    assert required_package_suffixes <= wheel_names
    assert not any("tests/" in name for name in wheel_names)
    assert not any("fixtures/" in name for name in wheel_names)
    assert any(name.endswith("LICENSE") for name in wheel_names)

    with tarfile.open(sdist_path, mode="r:gz") as sdist:
        sdist_names = set(sdist.getnames())

    required_sdist_suffixes = {
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "uv.lock",
        *required_package_suffixes,
    }
    assert all(
        any(name.endswith(suffix) for name in sdist_names)
        for suffix in required_sdist_suffixes
    )
    assert not any("tests/" in name for name in sdist_names)
    assert not any("fixtures/" in name for name in sdist_names)
    assert not any(name.endswith(".coverage") for name in sdist_names)
    assert not any(".venv/" in name for name in sdist_names)
    assert not any("/dist/" in f"/{name}/" for name in sdist_names)


def test_distribution_verifier_accepts_release_archives(
    built_distributions: tuple[Path, Path],
) -> None:
    """The standalone verifier accepts the built wheel and source archive."""
    wheel_path, sdist_path = built_distributions
    result = _run_distribution_verifier(wheel_path, sdist_path)

    assert result.returncode == 0
    assert result.stdout == "distribution verification passed\n"
    assert result.stderr == ""


def test_distribution_verifier_requires_one_archive_of_each_kind(
    built_distributions: tuple[Path, Path],
) -> None:
    """The verifier rejects an incomplete archive pair with constant output."""
    wheel_path, _ = built_distributions
    result = _run_distribution_verifier(wheel_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "distribution verification failed: expected one wheel and one sdist\n"
    )


def test_distribution_verifier_hides_malformed_archive_contents(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Malformed wheel diagnostics are constant and do not expose contents."""
    _, sdist_path = built_distributions
    content_canary = "archive-secret-canary"
    malformed_wheel = tmp_path / "malformed.whl"
    malformed_wheel.write_text(content_canary)

    result = _run_distribution_verifier(malformed_wheel, sdist_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "distribution verification failed: invalid wheel archive\n"
    assert content_canary not in result.stderr
