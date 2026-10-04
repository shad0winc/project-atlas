"""Bounded opt-in receipt reconciliation; never resubmits uncertain requests."""
from dataclasses import dataclass

from .models import MediaRequestStatus
from .service import MediaRequestServiceError
from .submission_recovery import SubmissionRecoveryService


@dataclass(frozen=True)
class SubmissionRecoveryOutcome:
    considered: int
    recovered: int
    needs_correlation: int
    unverified: int
    skipped: int


def reconcile_submission_receipts(service: SubmissionRecoveryService, *, limit: int = 100):
    if not isinstance(service, SubmissionRecoveryService):
        raise TypeError("Submission recovery service is required")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Submission recovery limit is invalid")
    requests = service.list_recovery_required_requests()[:limit]
    recovered = needs_correlation = unverified = skipped = 0
    for request in requests:
        if request.status is not MediaRequestStatus.SUBMITTING:
            skipped += 1
            continue
        attempt = service.repository.get_attempt(request.request_id)
        if attempt is None or attempt.receipt_id is None:
            needs_correlation += 1
            continue
        try:
            service.recover_submission(request.request_id)
            recovered += 1
        except MediaRequestServiceError:
            unverified += 1
    return SubmissionRecoveryOutcome(len(requests), recovered, needs_correlation, unverified, skipped)
