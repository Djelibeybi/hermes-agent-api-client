# Hermes Capability Identity Contract Design

**Date:** 2026-07-16\
**Status:** Approved for implementation\
**Repository:** `hermes-agent-api-client`

## Purpose

Extend the published client boundary so consumers can obtain Hermes Agent's
advertised API/profile name and distinguish an endpoint that is not Hermes from
a valid Hermes endpoint that lacks required Chat Completions support. Protocol
wire models, parsing, fixtures, classification, and sanitization remain owned by
this package. The Hermes Conversation repository is out of scope.

## Evidence and compatibility baseline

The compatibility baseline is the latest tagged Hermes Agent release available
on 2026-07-16:

- tag: `v2026.7.7.2`
- commit: `9de9c25f620ff7f1ce0fd5457d596052d5159596`
- release: <https://github.com/NousResearch/hermes-agent/releases/tag/v2026.7.7.2>
- handler: `gateway/platforms/api_server.py`, lines 1457-1535 at that tag

The tagged handler returns top-level `object`, `platform`, and `model` fields,
an `auth` object, and a `features` object. Its advertised model is resolved in
this order: explicit API-server model override, non-default active profile, or
the `hermes-agent` fallback. The same tagged handler advertises both
`chat_completions` and `chat_completions_streaming` as true.

The capability fixture will be recaptured from an immutable checkout of this
tag by invoking the tagged handler with a configured bearer key and the
`hermes-agent` fallback model. It will not be copied from `main`, manually
synthesized, or inferred from prose. Provenance will record the tag, commit,
source URL, capture procedure and configuration, capture date, and SHA-256 of
the exact fixture bytes.

The current locked direct dependencies are already the latest compatible
versions. The existing user-owned migration from pyright to basedpyright is
part of the working-tree baseline and must be completed in the hook and CI
commands without overwriting the existing `pyproject.toml` or `uv.lock` edits.

## Public model contract

`HermesCapabilities` remains a strict, frozen Pydantic model and gains:

```python
model: str
```

The value is the exact top-level `model` value advertised by Hermes. The client
does not trim, normalize, replace, or truncate it. A valid value must:

- be an actual string under strict validation;
- contain at least one non-whitespace character;
- contain between 1 and 255 Unicode code points, inclusive.

The 255-character maximum is intentionally much smaller than the 65,536-byte
capability-document budget. It is large enough for the upstream environment
override and active-profile sources while remaining a conventional bounded
identifier suitable for downstream display titles and storage. Values over the
limit are rejected rather than truncated.

Leading, trailing, and internal whitespace are preserved when the string is not
whitespace-only. Current tagged Hermes normally strips an explicit override
before advertising it, but the client does not silently reproduce that
normalization for arbitrary endpoints.

## Public failure contract

Add and export these exception types:

```python
class HermesIdentityError(HermesProtocolError): ...
class HermesCapabilityError(HermesProtocolError): ...
```

Both retain the existing protocol failure metadata and behavior:

- `category is FailureCategory.PROTOCOL`
- `status_code is None`
- `retryable is False`
- no additional instance attributes or state
- deterministic metadata-only `args`, `str`, and `repr`

Existing callers catching `HermesProtocolError` or `HermesContractError`
continue to catch both subclasses.

### Classification precedence

Classification is staged and deterministic:

| Wire condition | Public exception |
| --- | --- |
| Top-level document is not a mapping | `HermesProtocolError` |
| Missing or non-exact `object` discriminator | `HermesIdentityError` |
| Missing or non-exact `platform` discriminator | `HermesIdentityError` |
| Valid identity, but `features` is missing or not a mapping | `HermesCapabilityError` |
| Valid identity, but `features.chat_completions` is missing, false, or not the literal boolean `True` | `HermesCapabilityError` |
| Invalid or missing `model` | `HermesProtocolError` |
| Invalid or missing bearer authentication contract | `HermesProtocolError` |
| Missing, false, or invalid `chat_completions_streaming` | `HermesProtocolError` |
| Malformed JSON, oversized body, or another unrelated schema failure | `HermesProtocolError` |
| Existing authentication HTTP status | `HermesAuthenticationError` |
| Existing non-authentication HTTP status | `HermesHttpStatusError` |
| Existing request, timeout, read, or cleanup transport failure | `HermesTransportError` |

Identity classification wins when either discriminator is missing or wrong,
even if feature or schema fields are also invalid. Capability classification is
considered only after both identity discriminators are valid. The remaining
full schema validation runs only after required Chat Completions support has
been established.

## Parsing and sanitization architecture

The protocol layer will use three phases without inspecting or exporting
Pydantic error text:

1. A discriminator check reduces raw identity state to a safe internal result.
2. A required-feature check reduces Chat Completions support to a safe internal
   result.
3. The complete strict Pydantic wire model validates model, authentication,
   streaming, and all existing required semantics.

The internal parser returns either a validated wire model or a private failure
kind containing no raw value. `validate_capabilities()` clears its reference to
the caller-owned input before a dedicated raw-input-free helper raises the
corresponding public exception.

The HTTP payload parser similarly returns a validated capability value or a
private failure kind. `_read_capabilities_body()` retains that kind while it
closes and scrubs the response, bytes, headers, endpoint, and intermediate
objects, then raises a fresh typed exception from a safe frame. It must not
collapse identity and capability failures back into `HermesProtocolError`.

No new failure path may retain response bodies, invalid discriminator or model
values, bearer keys, URLs, HTTP objects, Pydantic validation details, raw
exceptions, chained causes or contexts, or caller-owned objects through public
state, exception rendering, traceback frames, or captured locals.

## Package surface

The package root and `__all__` will export:

- `HermesIdentityError`
- `HermesCapabilityError`
- the extended `HermesCapabilities`

Consumers will not import private wire models, validation helpers, or raw
capability documents. Public type verification, explicit imports, and star
imports must all expose the new types correctly.

## Tests

Implementation follows red-green-refactor. Tests are added before production
changes and each focused group is observed failing for the intended reason.

Coverage includes:

- immutable-tag capture provenance and exact fixture digest;
- successful `model` parsing and frozen behavior;
- additive and reordered capability documents;
- missing, empty, whitespace-only, non-string, 255-character, and
  256-character model values;
- identity precedence for missing and incorrect `object` and `platform`;
- capability classification for absent/invalid `features` and missing, false,
  or non-boolean `chat_completions`;
- protocol classification for authentication, model, streaming, JSON, size,
  and unrelated schema failures;
- metadata, `args`, `str`, `repr`, `vars`, traceback rendering, package-frame
  locals, caller-object identity, cause, and context sanitization for both new
  failures;
- transport probe success returning `model` and propagating the exact typed
  errors through both internal and public clients;
- package-root exports, `__all__`, star import, built-wheel imports, and public
  type verification;
- unchanged authentication, HTTP status, transport, retryability, streaming,
  and generic protocol behavior;
- 100% branch coverage.

## Documentation and release behavior

README usage will show package-root-only imports, use `capabilities.model`, and
document the supported capability shape, 255-character model rule, exact
failure taxonomy, and compatibility tag. The changelog receives an Unreleased
entry describing the additive public feature.

The feature commit uses a conventional `feat:` subject so the repository's
pre-1.0 semantic-release policy selects the next version. The implementation
does not manually choose or write the next version or changelog release
heading. Instead, `__version__` will derive from installed distribution
metadata and `scripts/verify_dist.py` will derive its expected version from the
current project metadata. This removes the duplicated `0.1.0` literals that
would otherwise become stale when semantic-release updates `pyproject.toml`.
The semantic-release build command will verify the newly built artifacts after
the generated version update. The existing release workflow owns that update
and publishes only after merge.

## Verification and delivery

The implementation will run:

1. `uv sync --locked --all-groups --no-editable`
2. `uv lock --check`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. the completed basedpyright project check
6. the completed basedpyright `--verifytypes` check
7. `uv run pytest` with pytest-cov and 100% coverage
8. `uv build`
9. `uv run python scripts/verify_dist.py` against the wheel and sdist
10. isolated wheel installation and package-root import/type checks
11. `uv run prek validate-config prek.toml` and installed-hook verification

The final implementation commit will be conventional, DCO-signed, and GPG
signed. A merge-ready PR will be pushed without publishing from the feature
branch. After merge, the release workflow must create and publish the version;
the handoff will verify the GitHub release, PyPI artifact, public imports, and
artifact SHA-256 values before reporting completion.

The untracked `.idea/` directory remains user-owned and excluded from all
staging, builds, commits, and release artifacts.
