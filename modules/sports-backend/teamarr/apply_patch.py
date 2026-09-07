"""Apply Atlas' narrow Teamarr trusted-future-date guard.

This patch is intentionally tied to one immutable upstream Teamarr source
revision. If upstream team_matcher.py changes, the image build fails closed
instead of applying the mutation to unknown source.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


TARGET = Path(
    "/app/teamarr/consumers/matching/team_matcher.py"
)

EXPECTED_SHA256 = "931f5afcdf5fab85437628a2ffa62362244080ce26aa533b03b16e34812dfd09"

FUNCTIONS = (
    "match_single_league",
    "match_multi_league",
)

CACHE_ANCHOR = """\
        # Check cache first
        cache_result = self._check_cache(ctx)
        if cache_result:
            return cache_result
"""

GUARD = """\
        # Atlas compatibility guard: a trusted provider-local stream date
        # must not bind to an adjacent fixture before that declared date is
        # inside Teamarr's configured event look-ahead horizon.
        #
        # Convert the end of the allowed USER-local horizon into the stream
        # timezone before comparing calendar dates. This preserves legitimate
        # provider/user timezone rollover at the edge of the horizon.
        trusted_stream_date = classified.normalized.extracted_date
        if (
            trusted_stream_date is not None
            and classified.normalized.extracted_date_trusted
        ):
            compare_tz = ctx.stream_tz or ctx.user_tz
            horizon_end_user = datetime.combine(
                target_date + timedelta(days=self._days_ahead + 1),
                datetime.min.time(),
                tzinfo=ctx.user_tz,
            )
            latest_stream_date = (
                horizon_end_user - timedelta(microseconds=1)
            ).astimezone(compare_tz).date()

            if trusted_stream_date > latest_stream_date:
                return MatchOutcome.failed(
                    FailedReason.DATE_MISMATCH,
                    stream_name=ctx.stream_name,
                    stream_id=ctx.stream_id,
                    detail=(
                        f"Trusted stream date "
                        f"{trusted_stream_date.isoformat()} is beyond "
                        f"the configured +{self._days_ahead}-day "
                        f"event look-ahead horizon"
                    ),
                    parsed_team1=ctx.team1,
                    parsed_team2=ctx.team2,
                )

        # Check cache first
        cache_result = self._check_cache(ctx)
        if cache_result:
            return cache_result
"""


def sha256_text(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_function(
    source: str,
    function_name: str,
) -> str:
    start_marker = f"    def {function_name}("
    start = source.find(start_marker)

    if start < 0:
        raise SystemExit(
            f"Atlas Teamarr patch: function not found: {function_name}"
        )

    next_function = source.find(
        "\n    def ",
        start + len(start_marker),
    )

    end = (
        len(source)
        if next_function < 0
        else next_function
    )

    block = source[start:end]

    count = block.count(CACHE_ANCHOR)

    if count != 1:
        raise SystemExit(
            "Atlas Teamarr patch: expected exactly one "
            f"cache anchor in {function_name}, found {count}"
        )

    patched_block = block.replace(
        CACHE_ANCHOR,
        GUARD,
        1,
    )

    return (
        source[:start]
        + patched_block
        + source[end:]
    )


# Atlas v1 temporal-quality compatibility guard.
#
# Teamarr intentionally permits a trusted provider-local declared date to be
# one calendar day from the candidate event so real provider/user timezone
# rollovers are not rejected.
#
# For trusted date + time metadata:
# - same-date candidates must be within three hours of the declared instant;
# - adjacent-date candidates retain a six-hour allowance for legitimate
#   midnight/timezone rollover.
#
# This fails closed on clearly bad provider timestamps while preserving the
# wider adjacent-calendar-date timezone seam.
MODULE_CONSTANT_ANCHOR = (
    "ANCHOR_MATCH_TOLERANCE_SECONDS = 90 * 60\n"
)

MODULE_CONSTANT = """
# Atlas compatibility guard: true temporal skew for trusted provider timestamps.
SAME_DAY_MAX_SKEW_SECONDS = 3 * 60 * 60
ADJACENT_DAY_MAX_SKEW_SECONDS = 6 * 60 * 60
"""

TRUSTED_DATE_GATE_ANCHOR = """\
            if (
                match_result
                and stream_date_dist > 1
                and ctx.classified.normalized.extracted_date_trusted
            ):
                date_rejected += 1
                continue
"""

TRUSTED_TEMPORAL_GUARD = """\
            if (
                match_result
                and stream_date_dist in (0, 1)
                and ctx.classified.normalized.extracted_date_trusted
                and ctx.classified.normalized.extracted_date is not None
                and ctx.classified.normalized.extracted_time is not None
            ):
                time_tz = ctx.stream_tz or ctx.user_tz
                declared_stream_dt = datetime.combine(
                    ctx.classified.normalized.extracted_date,
                    ctx.classified.normalized.extracted_time,
                    tzinfo=time_tz,
                )
                event_dt_in_stream_tz = event.start_time.astimezone(time_tz)
                temporal_skew = abs(
                    int(
                        (
                            event_dt_in_stream_tz
                            - declared_stream_dt
                        ).total_seconds()
                    )
                )
                temporal_limit = (
                    SAME_DAY_MAX_SKEW_SECONDS
                    if stream_date_dist == 0
                    else ADJACENT_DAY_MAX_SKEW_SECONDS
                )

                if temporal_skew > temporal_limit:
                    date_rejected += 1
                    continue
"""


raw = TARGET.read_bytes()

actual = sha256_text(raw)

if actual != EXPECTED_SHA256:
    raise SystemExit(
        "Atlas Teamarr patch: upstream source checksum mismatch: "
        f"expected={EXPECTED_SHA256} actual={actual}"
    )

source = raw.decode("utf-8")

if source.count(MODULE_CONSTANT_ANCHOR) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: module constant anchor count mismatch"
    )

for atlas_constant in (
    "SAME_DAY_MAX_SKEW_SECONDS",
    "ADJACENT_DAY_MAX_SKEW_SECONDS",
):
    if atlas_constant in source:
        raise SystemExit(
            "Atlas Teamarr patch: temporal constant already present: "
            f"{atlas_constant}"
        )

source = source.replace(
    MODULE_CONSTANT_ANCHOR,
    MODULE_CONSTANT_ANCHOR + MODULE_CONSTANT,
    1,
)

if source.count(
    "SAME_DAY_MAX_SKEW_SECONDS = 3 * 60 * 60"
) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: generated same-day constant count mismatch"
    )

if source.count(
    "ADJACENT_DAY_MAX_SKEW_SECONDS = 6 * 60 * 60"
) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: generated adjacent-day constant count mismatch"
    )

marker = "Atlas compatibility guard: a trusted provider-local stream date"

if marker in source:
    raise SystemExit(
        "Atlas Teamarr patch: guard already present before patching"
    )

for function_name in FUNCTIONS:
    source = patch_function(
        source,
        function_name,
    )

if source.count(marker) != len(FUNCTIONS):
    raise SystemExit(
        "Atlas Teamarr patch: unexpected guard count after patching"
    )

if source.count(
    "trusted_stream_date > latest_stream_date"
) != len(FUNCTIONS):
    raise SystemExit(
        "Atlas Teamarr patch: horizon comparison count mismatch"
    )

if source.count(TRUSTED_DATE_GATE_ANCHOR) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: trusted-date gate anchor count mismatch"
    )

source = source.replace(
    TRUSTED_DATE_GATE_ANCHOR,
    TRUSTED_DATE_GATE_ANCHOR + TRUSTED_TEMPORAL_GUARD,
    1,
)

if source.count(
    "stream_date_dist in (0, 1)"
) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: trusted temporal date-distance guard count mismatch"
    )

if source.count(
    "temporal_skew > temporal_limit"
) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: trusted temporal skew guard count mismatch"
    )

if source.count(
    "SAME_DAY_MAX_SKEW_SECONDS"
) != 2:
    raise SystemExit(
        "Atlas Teamarr patch: same-day constant reference count mismatch"
    )

if source.count(
    "ADJACENT_DAY_MAX_SKEW_SECONDS"
) != 2:
    raise SystemExit(
        "Atlas Teamarr patch: adjacent-day constant reference count mismatch"
    )

if source.count(
    "declared_stream_dt = datetime.combine("
) != 1:
    raise SystemExit(
        "Atlas Teamarr patch: declared stream datetime count mismatch"
    )


# Syntax validation before replacing upstream source.
compile(
    source,
    str(TARGET),
    "exec",
)

TARGET.write_text(
    source,
    encoding="utf-8",
)

print(
    "ATLAS_TEAMARR_TRUSTED_DATE_SAFETY_V3_PATCH=PASS"
)

print(
    "patched_team_matcher_sha256=",
    sha256_text(
        TARGET.read_bytes()
    ),
)
