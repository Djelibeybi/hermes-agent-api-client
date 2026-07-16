"""Verify release archives without importing from the source checkout."""  # noqa: INP001

from __future__ import annotations

import gzip
import io
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Never

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence
    from email.message import Message


_PROJECT_ROOT = Path(__file__).parents[1]
_EXPECTED_ARCHIVES_MESSAGE = (
    "distribution verification failed: expected one wheel and one sdist"
)
_INVALID_WHEEL_ARCHIVE_MESSAGE = (
    "distribution verification failed: invalid wheel archive"
)
_INVALID_SDIST_ARCHIVE_MESSAGE = (
    "distribution verification failed: invalid source archive"
)
_INVALID_WHEEL_CONTENTS_MESSAGE = (
    "distribution verification failed: invalid wheel contents"
)
_INVALID_SDIST_CONTENTS_MESSAGE = (
    "distribution verification failed: invalid source contents"
)
_INVALID_METADATA_MESSAGE = "distribution verification failed: invalid wheel metadata"
_IMPORT_FAILURE_MESSAGE = (
    "distribution verification failed: isolated import check failed"
)
_MALFORMED_ARCHIVE_MESSAGE = "distribution verification failed: malformed archive"
_SUCCESS_MESSAGE = "distribution verification passed"

_REQUIRED_PACKAGE_SUFFIXES = frozenset(
    {
        "hermes_agent_api_client/__init__.py",
        "hermes_agent_api_client/client.py",
        "hermes_agent_api_client/models.py",
        "hermes_agent_api_client/protocol.py",
        "hermes_agent_api_client/sse.py",
        "hermes_agent_api_client/py.typed",
    }
)
_REQUIRED_SDIST_SUFFIXES = _REQUIRED_PACKAGE_SUFFIXES | {
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "uv.lock",
}
_EXPECTED_DEPENDENCIES = {
    "httpx>=0.28.1,<1",
    "pydantic>=2.13.4,<3",
}
_EXPECTED_SINGLETON_METADATA = {
    "Name": "hermes-agent-api-client",
    "Requires-Python": ">=3.13",
    "License-Expression": "UPL-1.0",
}
_FORBIDDEN_RELEASE_COMPONENTS = frozenset(
    {"tests", "fixtures", ".venv", "build", "dist"}
)
_ARCHIVE_ARGUMENT_COUNT = 2
_MAX_WHEEL_UNCOMPRESSED_BYTES = 10_000_000
_MAX_METADATA_BYTES = 1_000_000
_MAX_SDIST_MEMBERS = 512
_MAX_SDIST_UNCOMPRESSED_BYTES = 10_000_000
_MAX_SDIST_STREAM_BYTES = 11_000_000
_ORDINARY_TAR_FILE_TYPES = frozenset({tarfile.REGTYPE, tarfile.AREGTYPE})
_ISOLATED_IMPORT_SCRIPT = """
import importlib
import sys

sys.path.insert(0, sys.argv[1])
package = importlib.import_module("hermes_agent_api_client")
exports = package.__all__
if not isinstance(exports, list) or not all(isinstance(name, str) for name in exports):
    raise TypeError
namespace = {}
exec("from hermes_agent_api_client import *", namespace)
if any(name not in namespace for name in exports):
    raise ImportError
"""


class VerificationError(Exception):
    """A distribution failed a verifier contract with a constant message."""


class _BoundedReader(io.RawIOBase):
    """Limit bytes returned from one decompressed source stream."""

    def __init__(self, source: gzip.GzipFile, limit: int) -> None:
        """Store the source and its hard cumulative byte limit."""
        self._source = source
        self._limit = limit
        self._consumed = 0

    def read(self, size: int = -1) -> bytes:
        """Return bounded bytes or reject before crossing the hard limit."""
        remaining = self._limit - self._consumed
        requested = remaining + 1 if size < 0 or size > remaining else size
        payload = self._source.read(requested)
        if len(payload) > remaining:
            _fail(_INVALID_SDIST_CONTENTS_MESSAGE)
        self._consumed += len(payload)
        return payload


def _fail(message: str) -> Never:
    """Raise a verifier failure without retaining an upstream exception."""
    raise VerificationError(message)


def _project_version() -> str:
    """Return the expected artifact version from safe source metadata."""
    try:
        with (_PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
            project_data = tomllib.load(project_file)
        version_value = project_data["project"]["version"]
    except (
        KeyError,
        OSError,
        tomllib.TOMLDecodeError,
        TypeError,
        UnicodeDecodeError,
    ):
        _fail(_INVALID_METADATA_MESSAGE)
    if not isinstance(version_value, str) or not version_value:
        _fail(_INVALID_METADATA_MESSAGE)
    return version_value


def _resolve_archives(arguments: Sequence[str]) -> tuple[Path, Path]:
    """Return exactly one wheel path and one source archive path."""
    if len(arguments) != _ARCHIVE_ARGUMENT_COUNT:
        _fail(_EXPECTED_ARCHIVES_MESSAGE)
    paths = tuple(Path(argument) for argument in arguments)
    wheels = tuple(path for path in paths if path.name.endswith(".whl"))
    sdists = tuple(path for path in paths if path.name.endswith(".tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        _fail(_EXPECTED_ARCHIVES_MESSAGE)
    return (wheels[0], sdists[0])


def _names_are_safe(names: Collection[str]) -> bool:
    """Reject absolute, platform-specific, and parent-traversing members."""
    for name in names:
        member_path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or member_path.is_absolute()
            or ".." in member_path.parts
        ):
            return False
    return True


def _has_suffix(names: Collection[str], suffix: str) -> bool:
    """Return whether an archive contains one exact relative suffix."""
    return any(name == suffix or name.endswith(f"/{suffix}") for name in names)


def _contains_forbidden_release_path(names: Collection[str]) -> bool:
    """Return whether names include development-only path components."""
    return any(
        part in _FORBIDDEN_RELEASE_COMPONENTS or part.startswith(".coverage")
        for name in names
        for part in PurePosixPath(name).parts
    )


def _wheel_names_are_valid(names: Collection[str]) -> bool:
    """Validate wheel package, license, and exclusion members."""
    return (
        _names_are_safe(names)
        and set(names) >= _REQUIRED_PACKAGE_SUFFIXES
        and not _contains_forbidden_release_path(names)
        and any(name.endswith("LICENSE") for name in names)
    )


def _sdist_names_are_valid(
    names: Collection[str],
    regular_names: Collection[str],
) -> bool:
    """Validate source archive release members and exclusions."""
    return (
        _names_are_safe(names)
        and all(
            _has_suffix(regular_names, suffix) for suffix in _REQUIRED_SDIST_SUFFIXES
        )
        and not _contains_forbidden_release_path(names)
    )


def _metadata_is_valid(
    package_metadata: Message,
    expected_version: str,
) -> bool:
    """Validate the exact public wheel metadata contract."""
    dependencies = package_metadata.get_all("Requires-Dist", [])
    expected_singleton_metadata = {
        **_EXPECTED_SINGLETON_METADATA,
        "Version": expected_version,
    }
    return (
        not package_metadata.defects
        and all(
            len(values := package_metadata.get_all(field, [])) == 1
            and values[0] == expected
            for field, expected in expected_singleton_metadata.items()
        )
        and set(dependencies) == _EXPECTED_DEPENDENCIES
        and len(dependencies) == len(_EXPECTED_DEPENDENCIES)
    )


def _verify_isolated_imports(extraction_root: Path) -> None:
    """Import every public export from the extracted wheel in isolation."""
    try:
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-c",
                _ISOLATED_IMPORT_SCRIPT,
                str(extraction_root),
            ],
            cwd=extraction_root,
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        _fail(_IMPORT_FAILURE_MESSAGE)
    if result.returncode != 0:
        _fail(_IMPORT_FAILURE_MESSAGE)


def _verify_wheel(wheel_path: Path, expected_version: str) -> None:
    """Validate wheel members, metadata, and isolated public imports."""
    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            names = set(wheel.namelist())
            if not _wheel_names_are_valid(names):
                _fail(_INVALID_WHEEL_CONTENTS_MESSAGE)
            if sum(info.file_size for info in wheel.infolist()) > (
                _MAX_WHEEL_UNCOMPRESSED_BYTES
            ):
                _fail(_INVALID_WHEEL_CONTENTS_MESSAGE)

            metadata_names = tuple(
                name for name in names if name.endswith(".dist-info/METADATA")
            )
            if len(metadata_names) != 1:
                _fail(_INVALID_METADATA_MESSAGE)
            metadata_info = wheel.getinfo(metadata_names[0])
            if metadata_info.file_size > _MAX_METADATA_BYTES:
                _fail(_INVALID_METADATA_MESSAGE)
            try:
                package_metadata = BytesParser(policy=default).parsebytes(
                    wheel.read(metadata_info)
                )
            except (KeyError, ValueError):
                _fail(_INVALID_METADATA_MESSAGE)
            if not _metadata_is_valid(package_metadata, expected_version):
                _fail(_INVALID_METADATA_MESSAGE)

            with TemporaryDirectory() as temporary_directory:
                extraction_root = Path(temporary_directory)
                wheel.extractall(extraction_root)  # noqa: S202 - names prevalidated
                _verify_isolated_imports(extraction_root)
    except VerificationError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile):
        _fail(_INVALID_WHEEL_ARCHIVE_MESSAGE)


def _record_sdist_member(
    member: tarfile.TarInfo,
    names: set[str],
    regular_names: set[str],
    total_uncompressed_bytes: int,
) -> int:
    """Validate and record one bounded source archive member."""
    if member.name in names or not _names_are_safe((member.name,)):
        _fail(_INVALID_SDIST_CONTENTS_MESSAGE)
    names.add(member.name)
    if member.type in _ORDINARY_TAR_FILE_TYPES:
        if (
            member.size < 0
            or member.size > _MAX_SDIST_UNCOMPRESSED_BYTES - total_uncompressed_bytes
        ):
            _fail(_INVALID_SDIST_CONTENTS_MESSAGE)
        regular_names.add(member.name)
        return total_uncompressed_bytes + member.size
    if member.type != tarfile.DIRTYPE or member.size != 0:
        _fail(_INVALID_SDIST_CONTENTS_MESSAGE)
    return total_uncompressed_bytes


def _verify_sdist(sdist_path: Path) -> None:
    """Validate bounded source members without extracting their contents."""
    names: set[str] = set()
    regular_names: set[str] = set()
    total_uncompressed_bytes = 0
    try:
        with (
            sdist_path.open("rb") as compressed_stream,
            gzip.GzipFile(fileobj=compressed_stream) as decompressed_stream,
            tarfile.open(
                fileobj=_BoundedReader(
                    decompressed_stream,
                    _MAX_SDIST_STREAM_BYTES,
                ),
                mode="r|",
            ) as sdist,
        ):
            for member_count, member in enumerate(sdist, start=1):
                if member_count > _MAX_SDIST_MEMBERS:
                    _fail(_INVALID_SDIST_CONTENTS_MESSAGE)
                total_uncompressed_bytes = _record_sdist_member(
                    member,
                    names,
                    regular_names,
                    total_uncompressed_bytes,
                )
    except VerificationError:
        raise
    except (OSError, tarfile.TarError):
        _fail(_INVALID_SDIST_ARCHIVE_MESSAGE)
    if not _sdist_names_are_valid(names, regular_names):
        _fail(_INVALID_SDIST_CONTENTS_MESSAGE)


def main(arguments: Sequence[str]) -> int:
    """Verify the requested archives and return a process exit status."""
    try:
        wheel_path, sdist_path = _resolve_archives(arguments)
        expected_version = _project_version()
        _verify_wheel(wheel_path, expected_version)
        _verify_sdist(sdist_path)
    except VerificationError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    except Exception:  # noqa: BLE001 - never expose malformed archive details
        sys.stderr.write(f"{_MALFORMED_ARCHIVE_MESSAGE}\n")
        return 1
    sys.stdout.write(f"{_SUCCESS_MESSAGE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
