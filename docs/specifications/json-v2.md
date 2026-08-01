# JSON v2 Normative Specification

**Product:** `yasb-limitora` 0.2
**Review unit:** R2
**Status:** SPEC/TEST only. This document does not authorize v2 runtime code.

This contract is the machine boundary for `YASB CustomWidget -> yasb-limitora
CLI -> Limitora public API`. The companion structural support file is
[`json-v2.schema.json`](json-v2.schema.json). The v1 fixture test is
[`tests/test_v1_golden_fixtures.py`](../../tests/test_v1_golden_fixtures.py).

## 1. Normative Language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
normative. A conforming producer MUST fail closed rather than emit data that it
cannot validate. A conforming consumer MUST use field names and identities, not
array positions, to interpret data.

A producer SHOULD validate the structural schema before serialization and SHOULD
retain rejected source context only in private diagnostics that are subject to
the repository's redaction rules. A consumer SHOULD make stale evidence visible
without treating it as unavailable, and SHOULD ignore no required field. An
implementation MAY use a streaming JSON parser or a different language, but it
MUST produce the same validated values, ordering, limits, and bytes. It SHOULD
NOT silently coerce unknown states, floats, duplicate keys, or trailing data.

R2 is a specification and test unit. It MUST NOT modify `src/`, implement JSON
v2 execution, add a native YASB widget, or change the v1 runtime.

## 2. Scope and Invariants

JSON v2 is quota-focused. It preserves every safe quota quantity requested from
the public API together with the context needed to interpret that quantity. It
does **not** promise the full public Limitora snapshot.

The following public fields are explicitly excluded from 0.2 and MUST NOT be
added to the v2 envelope:

- `usage`;
- `rate_limit_reset_credits`; and
- any cost, token-history, prediction, or synthetic aggregate field.

The invariant is **preserve all safe quota evidence requested and its context**,
not "preserve the full public snapshot". Missing evidence is represented by
`null` or an explicit availability/outcome reason. It MUST NOT be represented
as zero, `0%`, or an invented window.

The contract MUST keep these concepts separate:

1. document execution state;
2. per-provider outcome;
3. exact public Limitora provider state;
4. freshness of a returned snapshot;
5. per-window availability; and
6. sanitized execution error.

## 3. Exact Envelope

The v2 document has exactly these top-level fields. Unknown fields MUST be
rejected. All fields in this table are present; nullable fields contain JSON
`null`, never an arbitrary omission.

| Field | Type | Required rule |
|-------|------|---------------|
| `version` | integer | MUST equal `2` |
| `execution_state` | string | One of `complete`, `partial`, `not_run`, `execution_error` |
| `execution_error` | object or `null` | Required; document-level sanitized error, subject to the legal matrix |
| `providers` | array | Required; exactly two provider objects, ordered `codex`, then `opencode_go` |

The v2 output is one UTF-8 JSON document followed by exactly one LF byte. A
document that cannot be represented within the limits in section 9 MUST fail
closed and MUST NOT emit a partial JSON document.

### 3.1 Provider object

Every provider object has exactly these fields:

| Field | Type | Required rule |
|-------|------|---------------|
| `provider` | string | `codex` or `opencode_go`; one of each is required |
| `outcome` | string | `snapshot`, `undetected`, `not_run`, or `execution_error` |
| `public_state` | string or `null` | Exact Limitora `ProviderState` for `snapshot`; `null` otherwise |
| `freshness` | string or `null` | `fresh` or `stale` for `snapshot`; `null` otherwise |
| `status_observed_at` | string or `null` | Canonical UTC timestamp for `snapshot`; `null` otherwise |
| `fetched_at` | string or `null` | Canonical UTC timestamp for `snapshot`; `null` otherwise |
| `data_at` | string or `null` | Canonical UTC timestamp for `snapshot`; `null` otherwise |
| `source_id` | string or `null` | Sanitized provider source identifier; `null` is legal |
| `windows` | array | Always present; zero or more window objects, never `null` |
| `execution_error` | object or `null` | Required; non-null only for provider `execution_error` |
| `not_run_reason` | string or `null` | Required; non-null only for provider `not_run` |
| `most_depleted_window` | object or `null` | Required presentation heuristic; `null` when ineligible |
| `compact_text` | string | Required bounded presentation fallback or summary |
| `alternate_text` | string | Required bounded presentation fallback or summary |
| `tooltip_text` | string | Required bounded presentation text; LF may separate lines |

`source_id` is nullable even for a snapshot because a public source reference
may be unknown to the safe allowlist. The raw reference MUST NOT be copied into
the output.

### 3.2 Window object

Every item in `windows` has exactly these fields:

| Field | Type | Required rule |
|-------|------|---------------|
| `kind` | string | Closed v2 vocabulary: `commercial_quota`, `technical_rate_limit`, `other` |
| `scope` | string | Non-empty sanitized identity string |
| `period` | string | Non-empty sanitized bounded string; open to future period names |
| `plan_id` | string or `null` | Plan identity when evidenced; explicit `null` when absent |
| `availability` | string | Closed public `ValueAvailability` vocabulary |
| `source_id` | string or `null` | Sanitized window source identifier |
| `limit` | object or `null` | Complete nullable Quantity |
| `used` | object or `null` | Complete nullable Quantity |
| `remaining` | object or `null` | Complete nullable Quantity |
| `reset_at` | string or `null` | Canonical UTC timestamp or explicit `null` |

`windows: []` is valid and means that no quota window was safely projected.
It is not a count of providers and MUST NOT be interpreted as an error by
itself.

### 3.3 Quantity object

Every non-null quantity has exactly these fields:

| Field | Type | Required rule |
|-------|------|---------------|
| `value` | string | Canonical decimal text, never a JSON number |
| `metric` | string | Closed metric vocabulary; validated against `kind` |
| `unit` | string | Non-empty sanitized unit identity |

`limit`, `used`, and `remaining` MUST each be retained when supplied. A
producer MUST NOT replace them with a percentage-only window. Each may be
`null` when the public source did not provide that quantity.

For `availability != known`, all three quantities and `reset_at` MUST be
`null`. For `availability == known`, at least one quantity MUST be non-null.
Whenever `limit` and `used` are both present, `used <= limit` MUST hold.
Whenever `limit` and `remaining` are both present, `remaining <= limit` MUST
hold. When all three are present, `used + remaining = limit` MUST hold exactly
in decimal arithmetic. A violation is invalid provider data and MUST fail
closed.

## 4. Outcomes, State, Freshness, and Errors

### 4.1 Provider outcomes

| Outcome | Meaning | Public state/freshness | Window rule |
|---------|---------|-----------------------|-------------|
| `snapshot` | A provider call returned a validated public snapshot | Both are present and exact | Preserve all safe quota windows, including an empty array when none is present |
| `undetected` | No usable provider source was detected | Both are `null`; no public provider state exists | `[]`; no snapshot context or raw detection message |
| `not_run` | No provider call was attempted | Both are `null` | `[]`; `not_run_reason` is required |
| `execution_error` | A provider call or provider-bound execution failed before a valid snapshot existed | Both are `null` | `[]`; sanitized `execution_error` is required |

`undetected` and `not_run` MUST NOT be collapsed to public state `unavailable`.
`unavailable` is a public state inside a returned `snapshot`; it means that a
provider source was selected and produced an unavailable observation.

### 4.2 Document execution states

| Document state | Required provider outcome pattern | `execution_error` rule |
|----------------|-----------------------------------|------------------------|
| `complete` | Every provider is `snapshot` or `undetected` | MUST be `null` |
| `partial` | At least one provider is `snapshot` or `undetected`, and at least one is `not_run` or `execution_error` | MUST be `null`; provider errors remain in their provider slots |
| `not_run` | Every provider is `not_run`, with no attempted provider error | `null` for all-disabled; `guard_wait_timeout/guard_wait` for guard expiry; `deadline_exhausted/document` when deadline exhaustion prevented one or more calls |
| `execution_error` | No provider is `snapshot` or `undetected`, and at least one provider was attempted or a document/configuration failure occurred | MUST be non-null; provider-failure mixes use `provider_failed/provider` unless deadline exhaustion is the document cause |

A guard wait expiry is specifically `execution_state: "not_run"`, with every
provider outcome `not_run` and `not_run_reason: "guard_wait_timeout"`. It MUST
NOT pretend that either provider failed.

The classification algorithm is normative and removes implementation choice:

1. If the document error is `cleanup_failed`, use `execution_state:
   execution_error` and preserve every already-recorded provider outcome.
2. Otherwise, if at least one provider is `snapshot` or `undetected`, use
   `complete` when all providers are in that set, or `partial` when any other
   provider is `not_run` or `execution_error`. The top-level error is `null`.
3. Otherwise, if every provider is `not_run`, use `not_run`. The top-level error
   is `null` only when every reason is `disabled`; use guard timeout when every
   provider was blocked by the guard; otherwise use `deadline_exhausted` when
   at least one reason is deadline exhaustion. A disabled provider may coexist
   with a deadline-exhausted provider in this last case. Configuration-invalid,
   invocation-invalid, and document-aborted reasons instead use
   `execution_error` with their corresponding top-level error, even when no
   provider was attempted.
4. Otherwise, at least one provider has `execution_error`, so use
   `execution_error`. Use top-level `deadline_exhausted/document` when any
   other provider was not run because the deadline expired; otherwise use the
   deterministic aggregate `provider_failed/provider`. Provider slots retain
   their specific sanitized errors.

Therefore all of these are legal and deterministic: disabled plus provider
error (`execution_error` with `provider_failed`), snapshot plus provider error
(`partial`), undetected plus provider error (`partial`), all provider errors
(`execution_error` with `provider_failed`), snapshot plus deadline-not-run
(`partial`), and attempted provider error plus deadline-not-run
(`execution_error` with `deadline_exhausted`).

### 4.3 Safe errors and not-run reasons

An execution error has exactly `code` and `phase`:

| Field | Closed values |
|-------|---------------|
| `code` | `invocation_invalid`, `configuration_invalid`, `guard_acquisition_failed`, `guard_wait_timeout`, `deadline_exhausted`, `provider_timeout`, `provider_failed`, `ipc_failed`, `cleanup_failed`, `invalid_provider_data`, `unknown_provider_state`, `internal_error` |
| `phase` | `configuration`, `guard_wait`, `provider`, `ipc`, `cleanup`, `document` |

An execution error MUST NOT contain a message, exception text, path, provider
payload, credential, workspace ID, runner, or raw public state. A provider
`execution_error` uses the provider or IPC/cleanup phase. A document
`execution_error` uses the document or guard/configuration phase.

The code-to-phase mapping is exact:

| Error code | Only legal phase |
|------------|------------------|
| `invocation_invalid`, `configuration_invalid` | `configuration` |
| `guard_acquisition_failed`, `guard_wait_timeout` | `guard_wait` |
| `deadline_exhausted`, `internal_error` | `document` |
| `provider_timeout`, `provider_failed`, `invalid_provider_data`, `unknown_provider_state` | `provider` |
| `ipc_failed` | `ipc` |
| `cleanup_failed` | `cleanup` |

`not_run_reason` has exactly one of:

`disabled`, `invalid_configuration`, `invocation_invalid`, `document_aborted`,
`deadline_exhausted`, or `guard_wait_timeout`.

### 4.4 Exact public Limitora state mapping

For `outcome: snapshot`, `public_state` MUST preserve the current public
Limitora spelling and meaning:

| Public state | Required v2 interpretation |
|--------------|----------------------------|
| `available` | At least one usable evidence-backed quota value; preserve it and its context |
| `partial` | Usable values plus explicit absences/unsupported windows; preserve both |
| `unavailable` | The selected public source has no supported observation; do not invent numeric values |
| `unauthorized` | Required authorization cannot be used; do not reinterpret as provider failure |
| `rate_limited` | A technical rate-limit condition; only technical-rate-limit windows may be carried |
| `transient_error` | A retryable source/transport/command failure prevented a reliable observation |
| `invalid_data` | A source response was present but failed public adapter validation |

An unknown future public state MUST fail closed as provider
`execution_error` with code `unknown_provider_state`, null public state and
freshness, an empty window array, and no raw state value. It MUST NOT be mapped
to `unavailable` or emitted as an unknown string.

Freshness is independent of state. `fresh` and `stale` are computed from the
public snapshot's `fetched_at` and the configured freshness policy; stale is not
unavailable and MUST retain safe snapshot evidence.

### 4.5 Legal combinations

The following matrix is normative. "Present" means non-null and valid for the
field's type; "null" means JSON `null`.

| Outcome | State | Freshness | Snapshot timestamps/source | Windows | Execution error | Not-run reason |
|---------|-------|-----------|----------------------------|---------|------------------|-----------------|
| `snapshot` | Present | Present | Timestamps present; source nullable | Any valid array | Null | Null |
| `undetected` | Null | Null | All null | `[]` | Null | Null |
| `not_run` | Null | Null | All null | `[]` | Null | Present |
| `execution_error` | Null | Null | All null | `[]` | Present | Null |

The document matrix in section 4.2 takes precedence over any tempting
combination not listed here. Presentation strings remain present in every row,
using the fallback rules in section 10.

### 4.6 Exact document-error combinations

The following combinations are the complete legal set for document-level
failures. Provider fields not shown as variable MUST follow section 4.5.

| Document condition | `execution_state` | Top-level error | Allowed provider outcomes | Required provider reason/error |
|--------------------|-------------------|----------------|----------------------------|--------------------------------|
| All selected providers disabled | `not_run` | `null` | Every provider `not_run` | Every `not_run_reason: disabled` |
| Valid v2 invocation, configuration missing/malformed | `execution_error` | `configuration_invalid/configuration` | Every provider `not_run` | `not_run_reason: invalid_configuration` |
| Valid v2 selection, invalid flag combination | `execution_error` | `invocation_invalid/configuration` | Every provider `not_run` | `not_run_reason: invocation_invalid` |
| Guard wait expires | `not_run` | `guard_wait_timeout/guard_wait` | Every provider `not_run` | `not_run_reason: guard_wait_timeout` |
| All provider calls are prevented by the absolute deadline | `not_run` | `deadline_exhausted/document` | Every provider `not_run` | At least one `deadline_exhausted`; other unattempted providers may be `disabled` |
| One provider times out and another returns a snapshot/undetected result | `partial` | `null` | At least one `execution_error` and one `snapshot`/`undetected` | Timed provider has `provider_timeout/provider`; other provider follows its outcome |
| One provider is disabled and the attempted provider fails | `execution_error` | `provider_failed/provider` | One `not_run`, one `execution_error` | Disabled provider has `disabled`; attempted provider has its specific error |
| All attempted providers fail with execution errors | `execution_error` | `provider_failed/provider` | Every provider `execution_error` | Each provider has its own sanitized provider error |
| Internal/document failure before provider completion | `execution_error` | `internal_error/document` | Every provider `not_run` or `execution_error` | `document_aborted` for unattempted providers |
| An attempted provider fails and another provider is not started at deadline | `execution_error` | `deadline_exhausted/document` | One `execution_error`, one `not_run` | Attempted provider keeps its error; unattempted provider has `deadline_exhausted` |
| Mutex release or cleanup fails after provider outcomes exist | `execution_error` | `cleanup_failed/cleanup` | The already-recorded `snapshot`, `undetected`, `not_run`, and/or `execution_error` outcomes are preserved | Existing provider fields remain truthful; no provider is rewritten as unavailable |

The cleanup row is intentionally different from the ordinary document-error
row. A top-level `execution_error` does **not** imply zero snapshots. When
cleanup or mutex release fails after a provider result was validated, the
producer MUST preserve that provider's complete snapshot, freshness, windows,
timestamps, source, and presentation fields, while setting the explicit
top-level `cleanup_failed` error. A valid `undetected` or provider
`execution_error` result is preserved in the same way.

## 5. Window Identity and Compatibility

The identity of a window is exactly:

```text
(kind, scope, period)
```

A provider MUST NOT emit two windows with the same identity, even when their
plans or sources differ. Consumers MUST NOT assume a fixed number, name, or
order of provider windows. An open/future `period` is valid when it meets the
sanitized string limits; unknown period names MUST NOT be rejected merely
because they are new.

Mathematical cross-provider compatibility requires equal:

```text
(kind, scope, period, plan_id, unit)
```

For `kind: commercial_quota` with `plan_id: null`, compatibility additionally
requires equal non-null sanitized `source_id` values on the compared windows.
If either source is `null`, the windows are preserved but are ineligible for
planless commercial cross-provider comparison. `source_id` is context, not a
substitute for plan identity.

`metric` remains in every Quantity. It is not an independent compatibility key:
for comparable kinds, Limitora validates that metric against the window kind.
The v2 rules are:

| Window kind | Required quantity metric |
|-------------|--------------------------|
| `commercial_quota` | `commercial_quota` |
| `technical_rate_limit` | `technical_rate_limit` |
| `other` | `commercial_quota` or `technical_rate_limit`, but never a cross-provider comparison target |

All non-null quantities in one window MUST use the same metric and unit.
`other` is retained as safe quota evidence but has no v2 aggregation target.
`tokens` and `balance` remain listed closed public metric values so an unknown
or excluded public value is handled deterministically, but any Quantity using
either metric is outside the 0.2 quota contract and MUST fail closed. No
`UsageSnapshot` is represented by v2.
There is no incompatible cross-provider minimum and no synthetic window.

## 6. Vocabularies and Sanitization

The v2 vocabularies are closed. Unknown values fail closed; they MUST NOT be
passed through as future enum strings.

| Vocabulary | Supported values |
|------------|------------------|
| Provider | `codex`, `opencode_go` |
| Outcome | `snapshot`, `undetected`, `not_run`, `execution_error` |
| Public state | `available`, `partial`, `unavailable`, `unauthorized`, `rate_limited`, `transient_error`, `invalid_data` |
| Freshness | `fresh`, `stale` |
| Window kind | `commercial_quota`, `technical_rate_limit`, `other` |
| Metric | `commercial_quota`, `technical_rate_limit`, `tokens`, `balance` |
| Availability | `known`, `unlimited`, `disabled`, `unavailable`, `unknown`, `not_authorized`, `not_applicable`, `invalid`, `error` |

All identity strings (`scope`, `period`, `plan_id`, and `unit`) MUST be trimmed,
NFC-normalized Unicode with no control characters, no leading/trailing
whitespace, and 1-64 Unicode scalar values. `period` is open within those
bounds. Text fields MUST be valid Unicode without lone surrogates. Presentation
control rules are exact:

| Field | Allowed controls |
|-------|------------------|
| `compact_text` | None: reject every C0 code point U+0000-U+001F and DEL U+007F |
| `alternate_text` | None: reject every C0 code point U+0000-U+001F and DEL U+007F |
| `tooltip_text` | LF U+000A only; reject U+0000-U+0009, U+000B-U+001F, and U+007F |

CR, TAB, other C0 controls, and DEL MUST NOT be silently removed or replaced.
The schema enforces these rules with an ECMA-compatible start-anchored negative
lookahead over `[\\s\\S]`; it does not rely on `$` alone, because JSON Schema
`pattern` uses search semantics and `$` may match immediately before a final LF.

`source_id` is nullable and MUST be produced by this exact safe rule:

1. Convert the public source reference to NFC and trim it.
2. Emit it only when it is exactly one of the current allowlisted IDs
   `codex-app-server-v2` or `opencode-go-dashboard`.
3. Emit JSON `null` for every other value. Never emit the raw rejected value.

The provider source and each window source are sanitized independently. A
future source requires a reviewed allowlist update; it is not automatically
accepted by a generic identifier regex.

## 7. Quantities and Decimal Canonicalization

Quantity values MUST be finite Decimal values serialized as JSON strings. JSON
numbers, binary floats, `NaN`, and infinities MUST be rejected at the v2
boundary. Limitora quantities are non-negative; negative quantities fail
closed. `-0` is normalized to `0`.

The canonical decimal renderer is parameterized by the value being rendered.
For an original quantity it is:

- fixed-point text only; exponent notation is forbidden;
- no leading `+`;
- integer zero is `0`, not `00`;
- trailing fractional zeroes and a trailing decimal point are removed;
- the original supplied quantity is never rounded or replaced by a derived
  percentage;
- at most 128 significant digits;
- at most 256 rendered ASCII characters, including sign and decimal dot.

Original quantities exceeding either quantity limit, or values that cannot be
rendered exactly under these rules, are invalid provider data and fail closed.
The larger exact quantity budget preserves provider evidence without confusing
it with the precision budget used for derived arithmetic.

Derived percentages MUST use a local Decimal context with precision `34` and
`ROUND_HALF_EVEN` (decimal128-style precision). The exact formula is:

```text
remaining_percentage = remaining.value / limit.value * 100
```

The division and multiplication occur in that Decimal context, followed by the
percentage renderer: fixed-point, no exponent, at most 34 significant digits,
and at most 128 rendered ASCII characters. A derived percentage MUST be in the
closed interval `[0, 100]`; a result below 0 or above 100 is invalid provider
data and MUST fail closed, never clamped. A window with a missing `limit`, a
missing `remaining`, or `limit == 0` is not eligible for a derived percentage
and MUST produce `most_depleted_window: null` for that window. No binary
floating-point operation is permitted. Provided `limit`, `used`, and
`remaining` values are never recomputed from a percentage.

## 8. Timestamps

`status_observed_at`, `fetched_at`, `data_at`, and `reset_at` use the exact
canonical form:

```text
YYYY-MM-DDTHH:MM:SS.ffffffZ
```

The precision is six fractional decimal digits (microseconds), including
trailing zeroes. The timestamp MUST represent UTC and MUST end in literal `Z`;
offset spellings such as `+00:00` are not canonical. A timezone-aware public
timestamp is converted to UTC without changing its instant. A timestamp with
more than six fractional digits, no timezone, or an invalid calendar value
fails closed.

For a snapshot, `status_observed_at <= fetched_at` and `data_at <= fetched_at`.
`reset_at` is nullable and may be before or after fetch time because it is the
provider's window evidence.

## 9. Determinism, Cardinality, and Frames

The following limits are normative and derive from the existing bounded Codex
IPC (`CONTROL_MAX_BYTES = 16 KiB`, `RESPONSE_MAX_BYTES = 64 KiB`):

| Limit | Maximum |
|-------|---------|
| Providers | Exactly 2 |
| Windows per provider | 32 |
| Identity strings | 64 Unicode scalar values each |
| `compact_text` / `alternate_text` | 128 Unicode scalar values each |
| `tooltip_text` | 4096 Unicode scalar values |
| Original quantity text | 256 ASCII characters and 128 significant digits |
| Derived percentage text | 128 ASCII characters and 34 significant digits |
| v2 JSON stdout document including final LF | 65,536 bytes |
| v2 response/frame JSON payload excluding its 4-byte length prefix | 65,536 bytes |
| Existing control/request frame payload | 16,384 bytes; unchanged |

The v2 implementation MUST NOT increase the existing IPC limits to fit a large
document. If 64 KiB is insufficient, it must fail closed or revise the
contract in a separately reviewed version.

JSON input and output MUST be UTF-8 without a BOM. Parsers MUST reject invalid
UTF-8, duplicate object keys, non-finite JSON constants, trailing JSON data,
unknown fields, and invalid Unicode scalar sequences. Canonical output uses
compact separators, deterministic object-key order, no ASCII-only escaping for
valid Unicode, and one final LF.

The canonical object-key order is the order shown in sections 3.1-3.3 and the
top-level order shown in section 3. Window arrays are sorted by:

```text
(kind-order, scope, period, plan_id-null-first, plan_id, source_id-null-first, source_id)
```

where `kind-order` is `commercial_quota`, `technical_rate_limit`, `other`.
Provider arrays are always `codex`, then `opencode_go`. Arrays are deterministic
serialization details only. Consumers MUST locate providers by `provider` and
windows by `(kind, scope, period)`, not by position.

## 10. Presentation Fields

Presentation fields are bounded, sanitized text for CustomWidget. They MUST NOT
create a second state machine. `compact_text`, `alternate_text`, and
`tooltip_text` are always present, even for an undetected, not-run, or error
provider.

The per-provider `most_depleted_window` is either `null` or this exact object:

| Field | Type |
|-------|------|
| `kind` | Window kind |
| `scope` | Window scope |
| `period` | Window period |
| `plan_id` | String or `null` |
| `unit` | Quantity unit |
| `source_id` | Sanitized string or `null` |
| `remaining_percentage` | Canonical Decimal string |

The object is a heuristic basis identity, not a synthetic window. An eligible
window MUST be a `snapshot` window with `availability: known`, non-null
`limit` and `remaining`, `limit.value > 0`, and a matching metric/unit. Stale
windows remain eligible but their text MUST identify stale evidence. The
heuristic chooses the lowest derived remaining percentage. Ties are broken by
the window sort key from section 9. Cross-provider minima are forbidden.

Fallback strings are exact:

| Provider condition | `compact_text` fallback |
|--------------------|-------------------------|
| No eligible window in a snapshot | `Quota unavailable` |
| `undetected` | `Quota not detected` |
| `not_run` | `Quota not run` |
| `execution_error` | `Quota error` |

`alternate_text` and `tooltip_text` MUST use the same condition and remain
bounded. A snapshot with no windows MUST use `Quota unavailable`; it MUST NOT
invent a window or report a count inconsistent with `windows: []`.

When the document has `execution_error.code: cleanup_failed`, provider
presentation fields MUST NOT be replaced by `Quota error` merely because the
document failed during cleanup. Snapshot text, stale indication, undetected
fallback, and provider-error fallback remain exactly tied to each provider's
recorded outcome. A CustomWidget configuration that presents one document-wide
fallback MUST use the literal `Document error: cleanup_failed` from the
top-level error; a configuration that presents provider fields MUST preserve
the provider text. This exposes the cleanup failure without falsifying valid
provider evidence.

The presentation contract has no `severity`, `refreshing`, dynamic CSS,
interactive progress, native popover, tab, or global minimum field.

## 11. Frozen JSON v1

v1 is semantically and byte-for-byte frozen. Its existing envelope remains:

```json
{"version":1,"providers":[{"provider":"codex","state":"success"},{"provider":"opencode_go","state":"unavailable"}]}
```

The current v1 serializer uses compact JSON, preserves Unicode labels without
ASCII escaping, emits provider order `codex`, then `opencode_go`, and appends
one terminating LF. Its state vocabulary remains `loading`, `success`,
`unavailable`, and `safe_error`; its error object remains `{"code": ...}`.

The no-argument v1 invocation MUST retain all-disabled behavior: both providers
are `unavailable`, exit code is `0`, stderr is empty, and no default config path
or named config environment variable is consulted. Explicit v1 `--config`, `-c`,
and `--config=PATH` retain their current semantics.

R2 adds four byte fixtures and tests only: representative success, all-disabled
unavailable, safe-error, and Unicode-label states. The tests compare exact bytes
including the final LF and do not change runtime implementation. A fixture
failure is a contract failure, not permission to update the fixture casually.

## 12. Explicit v2 Selection and Configuration

V2 is never selected implicitly. The exact output selector is:

```text
--output-version 2
--output-version=2
```

`--output-version 1` and `--output-version=1` explicitly select frozen v1. No
selector means v1. The v1 path MUST NOT consult a default config path or
`YASB_LIMITORA_CONFIG`.

### 12.1 Parsing order

The v2 implementation MUST start the absolute deadline at CLI entry, before
version scanning, environment lookup, path canonicalization, file open, file
read, or JSON parse. The sequence is:

1. Capture argv and streams, record `T0` immediately, and establish the
   provisional minimum deadline described in section 13.
2. Determine the output version from the exact selector forms.
3. Reject a duplicate selector, missing selector value, non-integer selector,
   or selector other than `1` or `2`.
4. Parse the remaining flags left-to-right. Accept only `--config PATH`,
   `-c PATH`, and `--config=PATH`; reject duplicate config flags, empty paths,
   unknown flags, missing values, secret-like argv text, and positional args.
5. For v2 only, resolve and canonically normalize the effective config path
   using section 12.2.
6. Read and validate UTF-8 JSON configuration using the same absolute deadline,
   rejecting duplicate keys, unknown fields, credential-like keys, malformed
   values, and trailing data.
7. Establish the guard scope and continue all execution phases against the
   same absolute deadline. No provider call may begin before these steps
   succeed.

If the selector itself is invalid, version selection is not trusted and the
result is the frozen v1 `invocation_invalid` envelope, stderr
`yasb-limitora: invocation_invalid\n`, and exit code `2`. A valid v2 selector
causes all later invocation/configuration errors to use the v2 safe envelope.

### 12.2 Exact v2 configuration grammar

The v2 configuration is one UTF-8 JSON object. Its only top-level keys are
`deadline_seconds`, `codex`, and `opencode_go`. `codex` and `opencode_go` are
optional; an omitted provider object is equivalent to its default empty object.
Every object key is case-sensitive. Unknown keys and duplicate JSON member
names at any level are configuration errors. A JSON `null` provider object is
not equivalent to omission and is invalid.

| Location/key | JSON type | Default | Constraint |
|--------------|-----------|---------|------------|
| top-level `deadline_seconds` | finite JSON number, not boolean | `7` | Inclusive range `1 <= value <= 120`; no string, `null`, NaN, or infinity |
| top-level `codex` | object | `{}` | Only the provider keys in the next table |
| top-level `opencode_go` | object | `{}` | Only the provider keys in the next table |
| provider `enabled` | boolean | `false` | Required only when supplied; no numeric/string coercion |
| Codex `runner` | string or `null` | `null` | Absolute Windows drive or UNC path; required when Codex is enabled; empty/relative is invalid |
| provider `timeout_seconds` | finite JSON number, not boolean | `7` | Exclusive lower bound `0`, inclusive upper bound `120`; it is only an upper hint and cannot extend the document deadline |
| provider `workspace_id` | string or `null` | `null` | When non-null, non-empty after trimming; local-only and never projected |

The exact provider key sets are:

| Provider object | Allowed keys |
|-----------------|--------------|
| `codex` | `enabled`, `runner`, `timeout_seconds`, `workspace_id` |
| `opencode_go` | `enabled`, `timeout_seconds`, `workspace_id` |

The v2 environment-only OpenCode Go credential remains `LIMITORA_AUTH_COOKIE`;
it is not a configuration key. Credential-like keys are rejected recursively.
Provider defaults are applied before validation of dependent rules: an enabled
Codex with omitted `runner` is invalid, while an omitted/disabled provider is a
legal `not_run` provider.

### 12.3 v1 explicit-config compatibility

When v1 is selected, the existing explicit-config grammar remains unchanged:
the top-level keys are only `codex` and `opencode_go`, the provider keys are the
same current keys, omitted providers use current defaults, and
`deadline_seconds` is not a v1 key. V1 continues to accept exactly one
`--config PATH`, `-c PATH`, or `--config=PATH`; it does not consult
`YASB_LIMITORA_CONFIG` or `%LOCALAPPDATA%`. Existing v1 JSON duplicate-member
last-wins behavior is retained for compatibility; v2 rejects duplicate members.
No v1 output bytes or no-argument behavior change is authorized.

### 12.4 v2 config precedence

Only v2 applies this precedence, from highest to lowest:

1. explicit `--config PATH` or `-c PATH`;
2. named environment path `YASB_LIMITORA_CONFIG`; and
3. `%LOCALAPPDATA%\\yasb-limitora\\config.json`.

The environment value is a path, not JSON and not a credential. An empty
`YASB_LIMITORA_CONFIG` is a configuration error, not permission to fall back.
If `%LOCALAPPDATA%` is missing, the v2 default is a configuration error.

The effective path MUST be canonicalized before guard scoping using Windows
full-path resolution with normalized separators, removal of non-root trailing
separators, and case-insensitive comparison. The canonical path MAY refer to a
missing file. A missing selected file is `configuration_invalid`, not an
all-disabled success.

The configured `deadline_seconds` is measured from the same `T0`; it never
starts after configuration parsing. Before the file is parsed, the producer
uses the minimum legal one-second deadline as a provisional bound. The cleanup
reserve is `min(0.25 seconds, deadline / 4)`, so configuration I/O and parsing
may consume at most `1.0 - 0.25 = 0.75` seconds before a configured deadline is
known. If this provisional bound expires, the producer emits a bounded
configuration/document deadline error rather than blocking CustomWidget.

The effective configuration path MUST be at most 32,767 UTF-16 code units after
normalization. V2 MUST reject device paths and UNC/network paths before file
open; v1 explicit paths retain their current behavior. V2 configuration files
MUST be regular local files no larger than 16,384 UTF-8 bytes. The producer
MUST obtain size without reading an unbounded stream and MUST read at most
16,385 bytes, rejecting the extra byte. It MUST use bounded/cancellable file
operations: lexical path normalization MUST perform no network or existence
lookup, and file open/read/close operations MUST receive only the remaining
deadline budget. An overlapped/cancellable read (or an equivalent bounded
primitive) MUST be cancelled at expiry. Blocking `read_text`, unbounded file
reads, network path resolution, and retries without a deadline are non-
conforming. If cancellation/close cannot complete within the deadline, the
document fails closed and the process cleanup path remains bounded by the same
deadline.

The legal flag combinations are:

| Selector | Config flags | Resolution |
|----------|--------------|------------|
| none | none | Frozen v1 all-disabled behavior |
| none | exactly one supported config flag | Frozen v1 explicit config |
| `--output-version 1` or `=1` | none or exactly one supported config flag | Frozen v1 |
| `--output-version 2` or `=2` | none | v2 env path, then per-user default |
| `--output-version 2` or `=2` | exactly one supported config flag | v2 explicit config |

The selector and config flag may appear in either argv order. A duplicate
selector, duplicate config flag, selector plus a second config spelling,
unknown flag, missing value, positional argument, or empty path is invalid. No
other combination is legal.

### 12.5 Exact streams and exits

| Condition | stdout | stderr | Exit |
|-----------|--------|--------|------:|
| v1 success or unavailable-only result | Exact v1 JSON plus LF | Empty | 0 |
| v1 safe runtime error | Exact v1 JSON plus LF | `yasb-limitora: runtime_error\n` | 1 |
| v1 invocation/config error | Exact v1 safe-error JSON plus LF | `yasb-limitora: invocation_invalid\n` or `yasb-limitora: configuration_invalid\n` | 2 |
| v2 successful snapshot/undetected/disabled result | Canonical v2 JSON plus LF | Empty | 0 |
| v2 provider/document execution failure | Canonical v2 safe envelope plus LF | `yasb-limitora: runtime_error\n` | 1 |
| v2 guard wait expiry | Canonical v2 `not_run` document plus LF | `yasb-limitora: guard_wait_timeout\n` | 1 |
| v2 invocation/configuration error | Canonical v2 safe envelope plus LF | `yasb-limitora: invocation_invalid\n` or `yasb-limitora: configuration_invalid\n` | 2 |

Stdout MUST contain only one JSON document and its final LF. Stderr MUST never
contain paths, config contents, provider payloads, credentials, workspace IDs,
runner paths, raw exceptions, or unknown state strings.

## 13. Absolute Deadline and Cross-Process Execution Guard

The guard is called a **cross-process execution guard**, never `single-flight`.
It serializes executions; it does not coalesce one caller's result into another
caller.

The named mutex scope is the tuple `(Windows user identity, canonical effective
config path)`. The mutex name MUST be derived from a stable, non-secret hash of
that tuple so that a path or user identity does not leak in diagnostics. There
is no global provider-only mutex.

The guard rules are:

- Create/open failure is document-level `execution_error` with
  `guard_acquisition_failed`; all providers are `not_run`.
- Wait is bounded by `min(250 ms, remaining budget after cleanup reserve)`.
  There is no unbounded waiter queue.
- A normal acquisition enters the critical section.
- An abandoned mutex acquisition is treated as successful ownership. It does
  not reuse the abandoned process's data and is recorded only through safe
  internal diagnostics.
- Wait timeout produces document `not_run`, top-level
  `guard_wait_timeout`, and all providers `not_run` with
  `guard_wait_timeout`. It MUST NOT emit provider failure states.
- The owner MUST attempt release in a `finally` path. Release failure becomes
  sanitized document `cleanup_failed` and prevents a success result.

One absolute monotonic wall-clock deadline starts at CLI entry as `T0`, before
configuration path resolution/read/parse, and covers configuration I/O, guard
wait, provider calls, Limitora IPC, response validation, process termination,
Job Object cleanup, mutex release, and output preparation. Each phase receives
only the remaining budget. A provider that has not started when the budget is
exhausted is `not_run: deadline_exhausted`; a provider call that started and
exceeded its remaining budget is provider `execution_error` with
`provider_timeout`. No phase may reset or extend the deadline, and no path or
file operation may stall CustomWidget beyond the document deadline.

Configuration path and file I/O use the bounded rules in section 12.4. The
cleanup reserve is withheld from guard/provider work and is available to
termination, Job Object cleanup, mutex release, and final bounded output
preparation. If all providers are prevented from starting by expiry, the exact
document is `not_run` with top-level `deadline_exhausted/document` and every
provider `not_run_reason: deadline_exhausted`.

Cleanup means bounded eventual termination within the absolute deadline. It
does not mean instantaneous process death when YASB closes CustomWidget. The
current CustomWidget `stop()` behavior is not a process-termination primitive.

## 14. YASB Validation

R9 has two separate proofs; passing one does not substitute for the other.

### 14.1 Deterministic integration

Run the real pinned YASB v2.0.5, its real `CustomWidget`, and a deterministic
fixture executable. The fixture MUST cover:

- complete snapshot;
- partial snapshot;
- stale snapshot;
- window disappearance and reappearance;
- invalid JSON;
- overlapping invocations and guard wait expiry.

#### 14.1.1 Malformed JSON fallback

The invalid-JSON case MUST use only stock pinned CustomWidget behavior and this
copy-ready configuration. The fixture executable path contains no spaces so it
is compatible with the pinned `run_cmd.split(" ")` behavior.

```yaml
class_name: limitora-r2-invalid-json
label: "Quota: {data}"
label_alt: "Quota: {data}"
label_placeholder: "Loading..."
tooltip: true
tooltip_label: "Quota: {data}"
exec_options:
  run_cmd: "fixture-invalid-json"
  run_once: true
  run_interval: 120000
  return_format: json
  hide_empty: true
  use_shell: false
```

The fixture MUST run in this order and the integration test MUST assert each
result:

| Step | Fixture stdout | `_exec_data` | Active label | Tooltip | Visibility |
|------|----------------|--------------|--------------|---------|------------|
| Valid seed | `{"status":"ok"}` | `{"status":"ok"}` | `Quota: {'status': 'ok'}` | Set to `Quota: {'status': 'ok'}` | Visible |
| Malformed output | `not-json\n` | `None` | `Quota: None` | Previous tooltip remains unchanged because stock `_update_tooltip` returns for falsy data | Hidden because `hide_empty: true` |
| Valid recovery | `{"status":"recovered"}` | `{"status":"recovered"}` | `Quota: {'status': 'recovered'}` | Replaced with `Quota: {'status': 'recovered'}` | Visible |

Malformed JSON therefore clears the worker's stored data; it does not retain
the previous data object. The pinned widget does not clear an already-installed
tooltip when the new data is `None`, so the test MUST assert retention rather
than claim tooltip clearing. If malformed JSON is the first result, no tooltip
is installed. This contract intentionally uses the stock literal `None` and
visibility behavior; it does not promise dynamic CSS, an intermediate
`refreshing` state, custom error parsing, or subprocess cancellation.

The proof MUST assert JSON parsing, labels, alternate labels, multiline
tooltip, refresh interval/manual callback behavior, fixed provider order,
bounded stdout/stderr, exit codes, no secret leakage, and bounded eventual
process termination. "No orphan" means all descendants terminate within the
document deadline; it does not mean instantaneous death on widget close.

The evidence record MUST include the exact YASB tag/commit (`v2.0.5`), installed
package versions, Python and Windows versions, CustomWidget configuration,
fixture command, stdout/stderr bytes, exit code, process-tree observations, and
termination duration. The claim is pinned-version evidence, not indefinite
compatibility.

### 14.2 Live-provider smoke

A separate opt-in smoke may use current Codex and OpenCode Go credentials. It
MUST NOT be required for deterministic fixture proof and MUST NOT store or
print credentials, cookies, workspace IDs, raw payloads, or private diagnostics.

## 15. Explicit Exclusions

R2 excludes:

- native or upstream YASB work, plugin/extension maintainer approval, and native
  popovers or tabs;
- fixed assumptions about provider window count or names;
- absent-as-zero, percentages as a replacement for quantities, and incompatible
  cross-provider minima;
- Claude and Gemini;
- costs, tokens, history, predictions, `usage`, and
  `rate_limit_reset_credits`; and
- any R3 runtime implementation.

## 16. Acceptance Criteria

Each user rule is mapped to a reviewable acceptance criterion.

| Rule | Acceptance criterion |
|------|----------------------|
| 1 | Scope section states quota focus, excludes `usage` and `rate_limit_reset_credits`, and states the safe-evidence invariant. |
| 2 | Envelope, provider, window, outcome, freshness, and error tables plus the legal-combination matrix keep concepts separate, including document cleanup failure. |
| 3 | Exact envelope examples distinguish `snapshot`, `undetected`, `not_run`, `execution_error`, disabled, configuration, invocation, guard, provider-timeout, all-failure, deadline attempted/not-attempted, internal, and cleanup outcomes. |
| 4 | State mapping lists all seven current public states and defines fail-closed handling for an unknown future state. |
| 5 | Exact fields require `windows` on every provider, explicit nulls, fixed codex/opencode_go order, and no positional semantics. |
| 6 | Identity and compatibility are stated mathematically; metric is not an independent key; open period and closed vocabulary rules are present. |
| 7 | Source allowlist/normalization, null behavior, and planless commercial ineligibility are normative and tested by review. |
| 8 | Quantity fields, reset, plan, availability, and non-percentage preservation rules are exact. |
| 9 | Quantity invariants, fixed-point rendering, separate 128-digit original quantities, 34-digit derived percentages, exact formula, zero-limit eligibility, and fail-closed overflow behavior are explicit. |
| 10 | All four required timestamp fields use six-digit UTC precision and `Z`. |
| 11 | Cardinalities, string lengths, separate decimal bounds, byte/frame limits, duplicate-key/trailing-data/UTF-8 rules, and deterministic ordering are explicit. |
| 12 | v1 rules and four exact-byte golden fixtures/tests exist; no runtime source file changes are present. |
| 13 | Exact top-level/provider config grammar, v1 compatibility, explicit selectors, v2-only config precedence, environment variable, canonical path, legal flag combinations, parsing order, missing-file behavior, and stream/exit table are present. |
| 14 | One absolute deadline starts at CLI entry, bounds path/config I/O, reserves cleanup, and defines guard timeout, provider timeout, all-deadline, mixed deadline/provider failure, document, and cleanup failures. |
| 15 | The guard is named correctly and its user/path scope, bounded wait, abandonment, failures, release, and no-coalescing rules are explicit. |
| 16 | Presentation fields, control-character rules, fallback strings, cleanup preservation, depleted-window formula/eligibility/ties, empty-window behavior, and excluded UI features are explicit. |
| 17 | Deterministic pinned-YASB and separate live-provider proofs, malformed-JSON `None` behavior/assertions, fixture scenarios, evidence, and bounded termination are explicit. |
| 18 | The exclusion section names every requested native, provider, metric, and R3 exclusion. |

## 17. R2 Review Gate

R2 is ready for final technical review only when:

- this specification and its schema are internally consistent;
- the schema and fixture files parse as UTF-8 JSON;
- focused existing tests and the new golden fixture tests pass;
- `git diff --check` is clean;
- no `src/` behavior changed; and
- the reviewer can trace every rule in section 16 to a document, schema, test,
  or explicit manual proof.

**R3 BLOCKED:** no v2 runtime implementation may begin until this gate passes,
including acceptance of the v1 fixtures and a final technical review pass.

## 18. Complete Examples

The following examples are complete v2 documents. They are normative examples
of shape and legal combinations, not provider fixtures or runtime output from
this R2 unit.

### 18.1 Completed snapshot

```json
{
  "version": 2,
  "execution_state": "complete",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "snapshot",
      "public_state": "available",
      "freshness": "fresh",
      "status_observed_at": "2026-08-01T12:00:00.000000Z",
      "fetched_at": "2026-08-01T12:00:00.100000Z",
      "data_at": "2026-08-01T12:00:00.000000Z",
      "source_id": "codex-app-server-v2",
      "windows": [
        {
          "kind": "commercial_quota",
          "scope": "account",
          "period": "five_hour",
          "plan_id": "plus",
          "availability": "known",
          "source_id": "codex-app-server-v2",
          "limit": {"value": "100", "metric": "commercial_quota", "unit": "percentage_points"},
          "used": {"value": "25", "metric": "commercial_quota", "unit": "percentage_points"},
          "remaining": {"value": "75", "metric": "commercial_quota", "unit": "percentage_points"},
          "reset_at": "2026-08-01T16:00:00.000000Z"
        }
      ],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": {
        "kind": "commercial_quota",
        "scope": "account",
        "period": "five_hour",
        "plan_id": "plus",
        "unit": "percentage_points",
        "source_id": "codex-app-server-v2",
        "remaining_percentage": "75"
      },
      "compact_text": "five_hour: 75% remaining",
      "alternate_text": "account / five_hour: 75% remaining",
      "tooltip_text": "commercial_quota / account / five_hour / plus: 75% remaining\nResets at 2026-08-01T16:00:00.000000Z"
    },
    {
      "provider": "opencode_go",
      "outcome": "snapshot",
      "public_state": "available",
      "freshness": "fresh",
      "status_observed_at": "2026-08-01T12:00:01.000000Z",
      "fetched_at": "2026-08-01T12:00:01.000000Z",
      "data_at": "2026-08-01T12:00:01.000000Z",
      "source_id": "opencode-go-dashboard",
      "windows": [
        {
          "kind": "commercial_quota",
          "scope": "account",
          "period": "weekly",
          "plan_id": null,
          "availability": "known",
          "source_id": "opencode-go-dashboard",
          "limit": {"value": "100", "metric": "commercial_quota", "unit": "percentage_points"},
          "used": {"value": "40", "metric": "commercial_quota", "unit": "percentage_points"},
          "remaining": {"value": "60", "metric": "commercial_quota", "unit": "percentage_points"},
          "reset_at": "2026-08-08T12:00:01.000000Z"
        }
      ],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": {
        "kind": "commercial_quota",
        "scope": "account",
        "period": "weekly",
        "plan_id": null,
        "unit": "percentage_points",
        "source_id": "opencode-go-dashboard",
        "remaining_percentage": "60"
      },
      "compact_text": "weekly: 60% remaining",
      "alternate_text": "account / weekly: 60% remaining",
      "tooltip_text": "commercial_quota / account / weekly: 60% remaining\nResets at 2026-08-08T12:00:01.000000Z"
    }
  ]
}
```

### 18.2 Partial and stale snapshot

```json
{
  "version": 2,
  "execution_state": "complete",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "snapshot",
      "public_state": "partial",
      "freshness": "stale",
      "status_observed_at": "2026-08-01T10:00:00.000000Z",
      "fetched_at": "2026-08-01T10:00:00.000000Z",
      "data_at": "2026-08-01T10:00:00.000000Z",
      "source_id": "codex-app-server-v2",
      "windows": [
        {
          "kind": "commercial_quota",
          "scope": "account",
          "period": "five_hour",
          "plan_id": "plus",
          "availability": "known",
          "source_id": "codex-app-server-v2",
          "limit": {"value": "100", "metric": "commercial_quota", "unit": "percentage_points"},
          "used": {"value": "90", "metric": "commercial_quota", "unit": "percentage_points"},
          "remaining": {"value": "10", "metric": "commercial_quota", "unit": "percentage_points"},
          "reset_at": "2026-08-01T14:00:00.000000Z"
        },
        {
          "kind": "commercial_quota",
          "scope": "account",
          "period": "weekly",
          "plan_id": "plus",
          "availability": "unavailable",
          "source_id": "codex-app-server-v2",
          "limit": null,
          "used": null,
          "remaining": null,
          "reset_at": null
        }
      ],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": {
        "kind": "commercial_quota",
        "scope": "account",
        "period": "five_hour",
        "plan_id": "plus",
        "unit": "percentage_points",
        "source_id": "codex-app-server-v2",
        "remaining_percentage": "10"
      },
      "compact_text": "five_hour: 10% remaining (stale)",
      "alternate_text": "account / five_hour: 10% remaining (stale)",
      "tooltip_text": "STALE\ncommercial_quota / account / five_hour / plus: 10% remaining\ncommercial_quota / account / weekly / plus: unavailable"
    },
    {
      "provider": "opencode_go",
      "outcome": "undetected",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota not detected",
      "alternate_text": "Quota not detected",
      "tooltip_text": "Quota not detected"
    }
  ]
}
```

### 18.3 Undetected providers

```json
{
  "version": 2,
  "execution_state": "complete",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "undetected",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota not detected",
      "alternate_text": "Quota not detected",
      "tooltip_text": "Quota not detected"
    },
    {
      "provider": "opencode_go",
      "outcome": "undetected",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota not detected",
      "alternate_text": "Quota not detected",
      "tooltip_text": "Quota not detected"
    }
  ]
}
```

### 18.4 Not run because the guard deadline expired

```json
{
  "version": 2,
  "execution_state": "not_run",
  "execution_error": {"code": "guard_wait_timeout", "phase": "guard_wait"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "guard_wait_timeout",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: execution guard wait expired"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "guard_wait_timeout",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: execution guard wait expired"
    }
  ]
}
```

### 18.5 Provider execution error

```json
{
  "version": 2,
  "execution_state": "partial",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_timeout", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    },
    {
      "provider": "opencode_go",
      "outcome": "snapshot",
      "public_state": "rate_limited",
      "freshness": "fresh",
      "status_observed_at": "2026-08-01T12:02:00.000000Z",
      "fetched_at": "2026-08-01T12:02:00.000000Z",
      "data_at": "2026-08-01T12:02:00.000000Z",
      "source_id": "opencode-go-dashboard",
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota unavailable",
      "alternate_text": "Quota unavailable",
      "tooltip_text": "Quota unavailable"
    }
  ]
}
```

### 18.6 All providers disabled

```json
{
  "version": 2,
  "execution_state": "not_run",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "disabled",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: provider disabled"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "disabled",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: provider disabled"
    }
  ]
}
```

### 18.7 Configuration error

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "configuration_invalid", "phase": "configuration"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "invalid_configuration",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: configuration invalid"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "invalid_configuration",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: configuration invalid"
    }
  ]
}
```

### 18.8 Invocation error after v2 selection

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "invocation_invalid", "phase": "configuration"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "invocation_invalid",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: invocation invalid"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "invocation_invalid",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: invocation invalid"
    }
  ]
}
```

### 18.9 All-provider deadline exhaustion

```json
{
  "version": 2,
  "execution_state": "not_run",
  "execution_error": {"code": "deadline_exhausted", "phase": "document"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "deadline_exhausted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document deadline exhausted"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "deadline_exhausted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document deadline exhausted"
    }
  ]
}
```

### 18.10 Internal/document error before provider completion

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "internal_error", "phase": "document"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "document_aborted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document execution aborted"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "document_aborted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document execution aborted"
    }
  ]
}
```

### 18.11 Cleanup failure after truthful provider outcomes

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "cleanup_failed", "phase": "cleanup"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "snapshot",
      "public_state": "available",
      "freshness": "fresh",
      "status_observed_at": "2026-08-01T12:03:00.000000Z",
      "fetched_at": "2026-08-01T12:03:00.000000Z",
      "data_at": "2026-08-01T12:03:00.000000Z",
      "source_id": "codex-app-server-v2",
      "windows": [
        {
          "kind": "commercial_quota",
          "scope": "account",
          "period": "five_hour",
          "plan_id": "plus",
          "availability": "known",
          "source_id": "codex-app-server-v2",
          "limit": {"value": "100", "metric": "commercial_quota", "unit": "percentage_points"},
          "used": {"value": "25", "metric": "commercial_quota", "unit": "percentage_points"},
          "remaining": {"value": "75", "metric": "commercial_quota", "unit": "percentage_points"},
          "reset_at": "2026-08-01T16:03:00.000000Z"
        }
      ],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": {
        "kind": "commercial_quota",
        "scope": "account",
        "period": "five_hour",
        "plan_id": "plus",
        "unit": "percentage_points",
        "source_id": "codex-app-server-v2",
        "remaining_percentage": "75"
      },
      "compact_text": "five_hour: 75% remaining",
      "alternate_text": "account / five_hour: 75% remaining",
      "tooltip_text": "commercial_quota / account / five_hour / plus: 75% remaining\nResets at 2026-08-01T16:03:00.000000Z"
    },
    {
      "provider": "opencode_go",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_failed", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    }
  ]
}
```

In the cleanup example the Codex snapshot remains usable evidence and the
OpenCode Go provider error remains a provider error. The document-level
`cleanup_failed` is independently visible; it does not erase, relabel, or
replace either provider result.

### 18.12 Disabled provider plus attempted provider error

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "provider_failed", "phase": "provider"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "disabled",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: provider disabled"
    },
    {
      "provider": "opencode_go",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_failed", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    }
  ]
}
```

### 18.13 Undetected provider plus attempted provider error

```json
{
  "version": 2,
  "execution_state": "partial",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "undetected",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota not detected",
      "alternate_text": "Quota not detected",
      "tooltip_text": "Quota not detected"
    },
    {
      "provider": "opencode_go",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_failed", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    }
  ]
}
```

### 18.14 All providers fail after attempted calls

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "provider_failed", "phase": "provider"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_timeout", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    },
    {
      "provider": "opencode_go",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "ipc_failed", "phase": "ipc"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    }
  ]
}
```

### 18.15 Snapshot plus deadline-not-run provider

```json
{
  "version": 2,
  "execution_state": "partial",
  "execution_error": null,
  "providers": [
    {
      "provider": "codex",
      "outcome": "snapshot",
      "public_state": "unavailable",
      "freshness": "fresh",
      "status_observed_at": "2026-08-01T12:04:00.000000Z",
      "fetched_at": "2026-08-01T12:04:00.000000Z",
      "data_at": "2026-08-01T12:04:00.000000Z",
      "source_id": "codex-app-server-v2",
      "windows": [],
      "execution_error": null,
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota unavailable",
      "alternate_text": "Quota unavailable",
      "tooltip_text": "Quota unavailable"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "deadline_exhausted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document deadline exhausted"
    }
  ]
}
```

### 18.16 Attempted provider error plus deadline-not-run provider

```json
{
  "version": 2,
  "execution_state": "execution_error",
  "execution_error": {"code": "deadline_exhausted", "phase": "document"},
  "providers": [
    {
      "provider": "codex",
      "outcome": "execution_error",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": {"code": "provider_timeout", "phase": "provider"},
      "not_run_reason": null,
      "most_depleted_window": null,
      "compact_text": "Quota error",
      "alternate_text": "Quota error",
      "tooltip_text": "Quota error"
    },
    {
      "provider": "opencode_go",
      "outcome": "not_run",
      "public_state": null,
      "freshness": null,
      "status_observed_at": null,
      "fetched_at": null,
      "data_at": null,
      "source_id": null,
      "windows": [],
      "execution_error": null,
      "not_run_reason": "deadline_exhausted",
      "most_depleted_window": null,
      "compact_text": "Quota not run",
      "alternate_text": "Quota not run",
      "tooltip_text": "Quota not run: document deadline exhausted"
    }
  ]
}
```
