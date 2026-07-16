"""Verify package metadata and public exports."""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from email.policy import default
from importlib.metadata import metadata, version
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


_INVALID_WHEEL_CONTENTS_MESSAGE = (
    "distribution verification failed: invalid wheel contents\n"
)
_INVALID_SDIST_CONTENTS_MESSAGE = (
    "distribution verification failed: invalid source contents\n"
)
_INVALID_SDIST_ARCHIVE_MESSAGE = (
    "distribution verification failed: invalid source archive\n"
)
_INVALID_METADATA_MESSAGE = "distribution verification failed: invalid wheel metadata\n"
_IMPORT_FAILURE_MESSAGE = (
    "distribution verification failed: isolated import check failed\n"
)
_SDIST_MEMBER_LIMIT = 512
_SDIST_UNCOMPRESSED_LIMIT = 10_000_000
_SDIST_STREAM_LIMIT = 11_000_000


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
    verifier_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the standalone distribution verifier with captured output."""
    project_root = Path(__file__).parents[1]
    verifier_project_root = verifier_root or project_root
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(verifier_project_root / "scripts" / "verify_dist.py"),
            *(str(archive) for archive in archives),
        ],
        cwd=verifier_project_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _create_verifier_project(
    temporary_root: Path,
    project_contents: str,
) -> Path:
    """Copy the verifier beside controlled project metadata."""
    project_root = Path(__file__).parents[1]
    verifier_root = temporary_root / "verifier-project"
    scripts_root = verifier_root / "scripts"
    scripts_root.mkdir(parents=True)
    (scripts_root / "verify_dist.py").write_bytes(
        (project_root / "scripts" / "verify_dist.py").read_bytes()
    )
    (verifier_root / "pyproject.toml").write_text(project_contents)
    return verifier_root


def _wheel_metadata_version(wheel_path: Path) -> str:
    """Read the sole Version field from a built wheel."""
    with zipfile.ZipFile(wheel_path) as wheel:
        metadata_names = tuple(
            name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
        )
        assert len(metadata_names) == 1
        package_metadata = BytesParser(policy=default).parsebytes(
            wheel.read(metadata_names[0])
        )
    version_values = package_metadata.get_all("Version", [])
    assert len(version_values) == 1
    return version_values[0]


def _assert_verifier_rejection(
    result: subprocess.CompletedProcess[str],
    *,
    expected_message: str,
    canary: str,
) -> None:
    """Assert one constant, secret-free verifier rejection."""
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == expected_message
    assert canary not in result.stderr


def _write_wheel_variant(
    source_path: Path,
    target_path: Path,
    *,
    transform: Callable[[str, bytes], bytes] | None = None,
    extra_members: tuple[tuple[str, bytes], ...] = (),
) -> None:
    """Copy a wheel while transforming payloads or adding hostile members."""
    with (
        zipfile.ZipFile(source_path) as source,
        zipfile.ZipFile(target_path, mode="w") as target,
    ):
        for member in source.infolist():
            payload = source.read(member)
            if transform is not None:
                payload = transform(member.filename, payload)
            target.writestr(member, payload)
        for name, payload in extra_members:
            target.writestr(name, payload)


def _write_sdist_variant(
    source_path: Path,
    target_path: Path,
    *,
    transform: Callable[[tarfile.TarInfo], tarfile.TarInfo] | None = None,
    extra_members: tuple[tuple[tarfile.TarInfo, bytes], ...] = (),
    archive_format: int = tarfile.PAX_FORMAT,
) -> None:
    """Stream-copy an sdist while transforming or adding hostile members."""
    with (
        tarfile.open(source_path, mode="r:gz") as source,
        tarfile.open(
            target_path,
            mode="w:gz",
            format=archive_format,
        ) as target,
    ):
        for member in source:
            output_member = transform(member) if transform is not None else member
            file_object = source.extractfile(member) if output_member.isfile() else None
            target.addfile(output_member, file_object)
        for member, payload in extra_members:
            file_object = io.BytesIO(payload) if member.isfile() else None
            target.addfile(member, file_object)


def _regular_tar_member(name: str, payload: bytes) -> tuple[tarfile.TarInfo, bytes]:
    """Create one regular tar member and its exact payload."""
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    return (member, payload)


def _replace_metadata_field(payload: bytes, field: str, value: str) -> bytes:
    """Replace one known singleton metadata field with a canary value."""
    prefix = f"{field}: ".encode()
    lines = payload.splitlines(keepends=True)
    return b"".join(
        f"{field}: {value}\n".encode() if line.startswith(prefix) else line
        for line in lines
    )


def _duplicate_metadata_field(payload: bytes, field: str, value: str) -> bytes:
    """Append one conflicting singleton header before the metadata body."""
    header, body = payload.split(b"\n\n", maxsplit=1)
    return header + f"\n{field}: {value}\n\n".encode() + body


def test_distribution_metadata_and_typed_marker() -> None:
    """Distribution metadata identifies a typed Python 3.13 package."""
    package_metadata = metadata("hermes-agent-api-client")
    assert package_metadata["Version"] == version("hermes-agent-api-client")
    assert package_metadata["Requires-Python"] == ">=3.13"
    assert package_metadata["License-Expression"] == "UPL-1.0"

    package_root = Path(__file__).parents[1] / "src" / "hermes_agent_api_client"
    assert (package_root / "py.typed").is_file()


def test_public_version_matches_distribution_metadata() -> None:
    """The import package exposes its installed distribution version."""
    import hermes_agent_api_client  # noqa: PLC0415

    assert hermes_agent_api_client.__version__ == version("hermes-agent-api-client")


def test_public_exports_are_exact() -> None:
    """The package exports only the approved typed public API."""
    import hermes_agent_api_client  # noqa: PLC0415

    assert set(hermes_agent_api_client.__all__) == {
        "AssistantDeltaEvent",
        "HermesAgentApiClient",
        "HermesAuthenticationError",
        "HermesCapabilityError",
        "HermesCapabilities",
        "HermesContractError",
        "HermesEvent",
        "HermesHttpStatusError",
        "HermesIdentityError",
        "HermesProtocolError",
        "HermesTransportError",
        "KeepaliveEvent",
        "TerminalEvent",
        "TerminalOutcome",
        "ToolProgressEvent",
        "UsageEvent",
        "__version__",
    }


def test_public_failure_types_are_available_through_star_import() -> None:
    """Star imports expose the public protocol failure taxonomy."""
    namespace: dict[str, object] = {}
    exec("from hermes_agent_api_client import *", namespace)  # noqa: S102
    identity_type = namespace["HermesIdentityError"]
    capability_type = namespace["HermesCapabilityError"]
    protocol_type = namespace["HermesProtocolError"]
    assert isinstance(identity_type, type)
    assert isinstance(capability_type, type)
    assert isinstance(protocol_type, type)
    assert issubclass(identity_type, protocol_type)
    assert issubclass(capability_type, protocol_type)


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
    assert not any(
        part.startswith(".coverage")
        for name in wheel_names
        for part in Path(name).parts
    )
    assert not any(".venv" in Path(name).parts for name in wheel_names)
    assert not any("build" in Path(name).parts for name in wheel_names)
    assert not any("dist" in Path(name).parts for name in wheel_names)
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


def test_distribution_verifier_uses_current_project_version(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """A semantic-release stamp drives the expected artifact Version."""
    project_root = Path(__file__).parents[1]
    with (project_root / "pyproject.toml").open("rb") as project_file:
        project_data = tomllib.load(project_file)
    source_version = project_data["project"]["version"]

    wheel_path, sdist_path = built_distributions
    assert _wheel_metadata_version(wheel_path) == source_version

    stamped_version = "9876.5.4" if source_version != "9876.5.4" else "9876.5.3"
    verifier_root = _create_verifier_project(
        tmp_path,
        f'[project]\nversion = "{stamped_version}"\n',
    )
    stamped_wheel = tmp_path / "stamped.whl"

    def transform(name: str, payload: bytes) -> bytes:
        if name.endswith(".dist-info/METADATA"):
            return _replace_metadata_field(
                payload,
                "Version",
                stamped_version,
            )
        return payload

    _write_wheel_variant(wheel_path, stamped_wheel, transform=transform)
    assert _wheel_metadata_version(stamped_wheel) == stamped_version

    result = _run_distribution_verifier(
        stamped_wheel,
        sdist_path,
        verifier_root=verifier_root,
    )

    assert result.returncode == 0
    assert result.stdout == "distribution verification passed\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    "project_contents",
    [
        '[project]\nversion = "project-version-secret-canary\n',
        '[project]\nname = "project-version-secret-canary"\n',
        '[project]\nversion = ["project-version-secret-canary"]\n',
        '[project]\nversion = ""\n# project-version-secret-canary\n',
    ],
    ids=["malformed-toml", "missing-version", "non-string-version", "empty-version"],
)
def test_distribution_verifier_hides_invalid_project_version(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
    project_contents: str,
) -> None:
    """Invalid source metadata fails with one constant, secret-free message."""
    wheel_path, sdist_path = built_distributions
    canary = "project-version-secret-canary"
    verifier_root = _create_verifier_project(tmp_path, project_contents)

    result = _run_distribution_verifier(
        wheel_path,
        sdist_path,
        verifier_root=verifier_root,
    )

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_METADATA_MESSAGE,
        canary=canary,
    )


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


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "tests/wheel-secret-canary.py",
        "fixtures/wheel-secret-canary.json",
        ".coverage.wheel-secret-canary",
        ".venv/wheel-secret-canary",
        "build/wheel-secret-canary",
        "dist/wheel-secret-canary.whl",
    ],
)
def test_distribution_verifier_rejects_forbidden_wheel_members(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
    forbidden_name: str,
) -> None:
    """Wheel archives reject every development-only path category."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "forbidden-member.whl"
    canary = "wheel-secret-canary"
    _write_wheel_variant(
        wheel_path,
        variant_path,
        extra_members=((forbidden_name, canary.encode()),),
    )

    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_WHEEL_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_wheel_traversal(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Wheel archives reject parent-traversing member names."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "traversal.whl"
    canary = "wheel-traversal-canary"
    _write_wheel_variant(
        wheel_path,
        variant_path,
        extra_members=((f"../{canary}", canary.encode()),),
    )

    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_WHEEL_CONTENTS_MESSAGE,
        canary=canary,
    )


@pytest.mark.parametrize(
    "field",
    ["Name", "Version", "Requires-Python", "License-Expression"],
)
def test_distribution_verifier_rejects_mismatched_singleton_metadata(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
    field: str,
) -> None:
    """Wheel metadata rejects a mismatched required singleton field."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "metadata-mismatch.whl"
    canary = "metadata-mismatch-canary"

    def transform(name: str, payload: bytes) -> bytes:
        if name.endswith(".dist-info/METADATA"):
            return _replace_metadata_field(payload, field, canary)
        return payload

    _write_wheel_variant(wheel_path, variant_path, transform=transform)
    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_METADATA_MESSAGE,
        canary=canary,
    )


@pytest.mark.parametrize(
    "field",
    ["Name", "Version", "Requires-Python", "License-Expression"],
)
def test_distribution_verifier_rejects_duplicate_singleton_metadata(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
    field: str,
) -> None:
    """Wheel metadata rejects duplicate required singleton fields."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "metadata-duplicate.whl"
    canary = "metadata-duplicate-canary"

    def transform(name: str, payload: bytes) -> bytes:
        if name.endswith(".dist-info/METADATA"):
            return _duplicate_metadata_field(payload, field, canary)
        return payload

    _write_wheel_variant(wheel_path, variant_path, transform=transform)
    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_METADATA_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_metadata_parser_defects(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Wheel metadata rejects malformed header syntax without leaking it."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "metadata-defect.whl"
    canary = "metadata-defect-canary"

    def transform(name: str, payload: bytes) -> bytes:
        if name.endswith(".dist-info/METADATA"):
            return f" {canary}\n".encode() + payload
        return payload

    _write_wheel_variant(wheel_path, variant_path, transform=transform)
    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_METADATA_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_reports_isolated_import_failure(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """A missing public export fails only with the constant import message."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "import-failure.whl"
    canary = "isolated-import-canary"

    def transform(name: str, payload: bytes) -> bytes:
        if name == "hermes_agent_api_client/__init__.py":
            return payload + f'\n__all__.append("{canary}")\n'.encode()
        return payload

    _write_wheel_variant(wheel_path, variant_path, transform=transform)
    result = _run_distribution_verifier(variant_path, sdist_path)

    _assert_verifier_rejection(
        result,
        expected_message=_IMPORT_FAILURE_MESSAGE,
        canary=canary,
    )


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_distribution_verifier_rejects_sdist_links(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
    member_type: bytes,
) -> None:
    """Source archives reject symbolic and hard links."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "linked.tar.gz"
    canary = "sdist-link-canary"
    linked_member = tarfile.TarInfo(f"package/{canary}")
    linked_member.type = member_type
    linked_member.linkname = canary
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=((linked_member, b""),),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_hides_malformed_sdist_contents(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Malformed sdist diagnostics are constant and do not expose contents."""
    wheel_path, _ = built_distributions
    canary = "malformed-sdist-canary"
    malformed_sdist = tmp_path / "malformed.tar.gz"
    malformed_sdist.write_text(canary)

    result = _run_distribution_verifier(wheel_path, malformed_sdist)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_ARCHIVE_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_sdist_special_files(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Source archives reject non-regular special file entries."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "special.tar.gz"
    canary = "sdist-special-canary"
    special_member = tarfile.TarInfo(f"package/{canary}")
    special_member.type = tarfile.CHRTYPE
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=((special_member, b""),),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_sdist_directory_payloads(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Source archive directories cannot declare unbounded file content."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "directory-payload.tar.gz"
    canary = "sdist-directory-payload-canary"
    directory_member = tarfile.TarInfo(f"package/{canary}")
    directory_member.type = tarfile.DIRTYPE
    directory_member.size = 1
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=((directory_member, b""),),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_sdist_traversal(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Source archives reject parent-traversing member names."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "traversal.tar.gz"
    canary = "sdist-traversal-canary"
    traversal_member = _regular_tar_member(f"../{canary}", canary.encode())
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=(traversal_member,),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_requires_regular_sdist_release_files(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Every required source archive member must be a regular file."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "required-directory.tar.gz"
    canary = "required-file-canary"

    def transform(member: tarfile.TarInfo) -> tarfile.TarInfo:
        if member.name.endswith("/README.md"):
            replacement = tarfile.TarInfo(member.name)
            replacement.type = tarfile.DIRTYPE
            replacement.uname = canary
            return replacement
        return member

    _write_sdist_variant(sdist_path, variant_path, transform=transform)
    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_limits_sdist_member_count(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Source archive verification stops after a safe member bound."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "excessive-members.tar.gz"
    canary = "sdist-member-count-canary"
    extra_members = tuple(
        _regular_tar_member(
            f"package/{canary}" if index == 0 else f"package/extra-{index}",
            b"",
        )
        for index in range(_SDIST_MEMBER_LIMIT + 1)
    )
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=extra_members,
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_limits_sdist_uncompressed_size(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Source archive verification stops after a safe size bound."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "oversized.tar.gz"
    canary = "sdist-uncompressed-size-canary"
    oversized_payload = b"\0" * (_SDIST_UNCOMPRESSED_LIMIT + 1)
    oversized_member = _regular_tar_member(
        f"package/{canary}",
        oversized_payload,
    )
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=(oversized_member,),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_limits_hidden_pax_header_bytes(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Hidden PAX headers cannot bypass the hard decompressed-byte limit."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "oversized-pax-header.tar.gz"
    canary = "sdist-pax-header-canary"
    pax_member, payload = _regular_tar_member("package/pax-member", b"")
    pax_member.pax_headers = {"comment": canary + ("x" * (_SDIST_STREAM_LIMIT + 1))}
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=((pax_member, payload),),
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_limits_hidden_gnu_long_name_bytes(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """GNU long-name records cannot bypass the decompressed-byte limit."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "oversized-gnu-long-name.tar.gz"
    canary = "sdist-gnu-long-name-canary"
    long_name = f"package/{canary}-" + ("x" * (_SDIST_STREAM_LIMIT + 1))
    long_name_member = _regular_tar_member(long_name, b"")
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=(long_name_member,),
        archive_format=tarfile.GNU_FORMAT,
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )


def test_distribution_verifier_rejects_gnu_sparse_members(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """GNU sparse entries are not ordinary regular release files."""
    wheel_path, sdist_path = built_distributions
    variant_path = tmp_path / "gnu-sparse.tar.gz"
    canary = "sdist-gnu-sparse-canary"
    sparse_member = tarfile.TarInfo(f"package/{canary}")
    sparse_member.type = tarfile.GNUTYPE_SPARSE
    _write_sdist_variant(
        sdist_path,
        variant_path,
        extra_members=((sparse_member, b""),),
        archive_format=tarfile.GNU_FORMAT,
    )

    result = _run_distribution_verifier(wheel_path, variant_path)

    _assert_verifier_rejection(
        result,
        expected_message=_INVALID_SDIST_CONTENTS_MESSAGE,
        canary=canary,
    )
