# Maintenance validation warning review

The corrected feature Core suite passed 5,735 tests and 1,778 subtests with 12
skips. The remaining checks passed 963 API tests and 32 subtests, five Sports
integrations, and 667 Portal tests across 119 files, plus typecheck and build.
All evidence and production preservation checks passed. These are private source
validation results; production activation, public acceptance and ownership release
remain pending.

The 14 API warnings all report Starlette's deprecation of the symbolic name
HTTP_422_UNPROCESSABLE_ENTITY. They occur in validation-rejection cases; those
cases still pass with HTTP 422. No warning filter, dependency upgrade or API
behavior change is introduced here. Replacing the symbol across the supported
FastAPI dependency range remains a compatibility follow-up. These warnings stay
visible in the accepted API log; this review does not represent a warning-free
API result or acceptance of future warning classes.

The Portal lint warning misidentified terminalRelease.current(), a closure-backed
method on a stable tracker, as React ref.current. Cleanup now captures the accessor
method before returning the cleanup callback and invokes it at cleanup time. It
continues to read the tracker's latest owned session, rather than taking an early
session snapshot. Release ownership, retry behavior and the release callback are
unchanged. Revalidation requires full Portal lint with zero warnings, typecheck,
tests (including the six maintenance console cases), and build.

Only the Portal component and this document change in this step. Core Python,
API, native shell and Sports implementation bytes remain the accepted versions;
those completed suites and media canaries are not rerun. The final validation
record must retain both accepted Core/API source evidence and this subsequent
Portal postimage evidence, without calling them one unchanged whole-source run.
The twelve Core skips are not waived by this warning review; identity/privileged
acceptance and remaining deployment/release gates still need explicit closure.
