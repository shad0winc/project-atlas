"""Bounded opt-in receipt reconciliation; never resubmits uncertain requests."""
from dataclasses import dataclass

from .models import MediaRequestStatus
from .service import MediaRequestServiceError
from .repository import MediaRequestRepositoryError
from .submission_batches import submission_batch
from .submission_recovery import SubmissionRecoveryService


@dataclass(frozen=True)
class SubmissionRecoveryOutcome:
    considered: int
    recovered: int
    needs_correlation: int
    unverified: int
    skipped: int


def reconcile_submission_receipts(service: SubmissionRecoveryService, *, limit: int = 100, offset: int = 0):
    if not isinstance(service, SubmissionRecoveryService):
        raise TypeError("Submission recovery service is required")
    requests = submission_batch(service.list_recovery_required_requests(), limit=limit, offset=offset)
    recovered = needs_correlation = unverified = skipped = 0
    for request in requests:
        if request.status is not MediaRequestStatus.SUBMITTING:
            skipped += 1
            continue
        try:
            attempt = service.repository.get_attempt(request.request_id)
            if attempt is None or attempt.receipt_id is None:
                needs_correlation += 1
                continue
            service.recover_submission(request.request_id)
            recovered += 1
        except (MediaRequestServiceError, MediaRequestRepositoryError):
            unverified += 1
    return SubmissionRecoveryOutcome(len(requests), recovered, needs_correlation, unverified, skipped)
