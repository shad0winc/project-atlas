"use client";

import { useCallback, useEffect, useState } from "react";

import { ATLAS_PERMISSIONS } from "../../../lib/authorization/permissions";

import { usePermission } from "../../../lib/authorization/use-permission";

import { useRequests, type RequestMutationFailure } from "../hooks/use-requests";

import type {
  MediaRequest,
  MediaRequestStatus,
  MediaRequestType,
  RequestsState
} from "../types/requests";

export type RequestsRefreshStateChange = (refresh: () => void, isBusy: boolean) => void;

export type RequestsViewProps = Readonly<{
  onRefreshStateChange?: RequestsRefreshStateChange;
}>;

export type RequestsContentProps = Readonly<{
  state: RequestsState;
  canCancel: boolean;
  pendingCancellationId: string | null;
  cancellingRequestId: string | null;
  blockedCancellationIds: readonly string[];
  mutationFailure: RequestMutationFailure | null;
  onRetry: () => void;
  onBeginCancellation: (requestId: string) => void;
  onCancelConfirmation: () => void;
  onConfirmCancellation: (requestId: string) => void | Promise<void>;
}>;

const MEDIA_TYPE_LABELS: Readonly<Record<MediaRequestType, string>> = {
  movie: "Movie",
  tv: "TV",
  anime_movie: "Anime Movie",
  anime_tv: "Anime TV",
  sports: "Sports"
};

const STATUS_LABELS: Readonly<Record<MediaRequestStatus, string>> = {
  pending: "Pending",
  submitting: "Submitting",
  approved: "Approved",
  searching: "Searching",
  downloading: "Downloading",
  importing: "Importing",
  available: "Available",
  rejected: "Rejected",
  failed: "Failed",
  cancelling: "Cancelling",
  cancelled: "Cancelled"
};

function requestSubtitle(request: MediaRequest): string {
  const details: string[] = [MEDIA_TYPE_LABELS[request.mediaType]];

  if (request.year !== undefined) {
    details.push(String(request.year));
  }

  if (request.seasonNumber !== undefined) {
    details.push(`Season ${request.seasonNumber}`);
  }

  return details.join(" · ");
}

function requestDate(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(timestamp));
}

type RequestCardProps = Readonly<{
  request: MediaRequest;
  canCancel: boolean;
  pendingCancellationId: string | null;
  cancellingRequestId: string | null;
  locallyBlocked: boolean;
  onBeginCancellation: (requestId: string) => void;
  onCancelConfirmation: () => void;
  onConfirmCancellation: (requestId: string) => void | Promise<void>;
}>;

function RequestCard({
  request,
  canCancel,
  pendingCancellationId,
  cancellingRequestId,
  locallyBlocked,
  onBeginCancellation,
  onCancelConfirmation,
  onConfirmCancellation
}: RequestCardProps): React.ReactElement {
  const isPendingConfirmation = pendingCancellationId === request.requestId;

  const isCancelling = cancellingRequestId === request.requestId;

  const anyCancellationInFlight = cancellingRequestId !== null;

  const needsAttention = request.recoveryRequired || locallyBlocked;

  return (
    <article className="request-card">
      <header className="request-card-header">
        <div>
          <p className="request-card-kind">{requestSubtitle(request)}</p>

          <h2 className="request-card-title">{request.title}</h2>
        </div>

        <span className="request-status-badge" data-status={request.status}>
          {STATUS_LABELS[request.status]}
        </span>
      </header>

      <dl className="request-card-meta">
        <div>
          <dt>Requested</dt>
          <dd>{requestDate(request.createdAt)}</dd>
        </div>

        <div>
          <dt>Provider</dt>
          <dd>{request.provider}</dd>
        </div>

        <div>
          <dt>Request ID</dt>
          <dd className="request-id-value">{request.requestId}</dd>
        </div>
      </dl>

      {needsAttention ? (
        <section aria-label="Request requires attention" className="request-recovery-warning">
          <strong>Atlas needs to confirm this request state.</strong>

          <p>
            {request.recoveryRequired
              ? "This request is in a recovery-required lifecycle state. Do not repeat the request action until Atlas reconciliation is complete."
              : "A cancellation attempt was not safely confirmed. Refresh request status before taking another cancellation action."}
          </p>
        </section>
      ) : null}

      {!needsAttention && request.canCancel && !canCancel ? (
        <p className="request-read-only">
          You can view this request, but your account does not have permission to cancel it.
        </p>
      ) : null}

      {!needsAttention && request.canCancel && canCancel ? (
        isPendingConfirmation ? (
          <div className="request-cancel-confirmation">
            <p>
              Cancel this media request? Atlas will ask the request provider to stop it when the
              lifecycle allows.
            </p>

            <div className="request-card-actions">
              <button
                className="request-cancel-button"
                disabled={anyCancellationInFlight}
                onClick={() => {
                  void onConfirmCancellation(request.requestId);
                }}
                type="button"
              >
                {isCancelling ? "Cancelling…" : "Confirm cancellation"}
              </button>

              <button
                className="request-secondary-button"
                disabled={anyCancellationInFlight}
                onClick={onCancelConfirmation}
                type="button"
              >
                Keep request
              </button>
            </div>
          </div>
        ) : (
          <div className="request-card-actions">
            <button
              aria-label={`Cancel ${request.title}`}
              className="request-cancel-button"
              disabled={anyCancellationInFlight}
              onClick={() => {
                onBeginCancellation(request.requestId);
              }}
              type="button"
            >
              Cancel request
            </button>
          </div>
        )
      ) : null}
    </article>
  );
}

export function RequestsContent({
  state,
  canCancel,
  pendingCancellationId,
  cancellingRequestId,
  blockedCancellationIds,
  mutationFailure,
  onRetry,
  onBeginCancellation,
  onCancelConfirmation,
  onConfirmCancellation
}: RequestsContentProps): React.ReactElement {
  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading requests" className="requests-grid">
        {Array.from(
          {
            length: 3
          },
          (_, index) => (
            <article className="request-card request-card-loading" key={index}>
              <span className="request-loading-line request-loading-line-short" />
              <span className="request-loading-line request-loading-line-title" />
              <span className="request-loading-line" />
            </article>
          )
        )}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section
        aria-labelledby="requests-error-title"
        className="requests-message-panel"
        role="alert"
      >
        <p className="portal-page-eyebrow">Requests unavailable</p>

        <h2 id="requests-error-title">Atlas could not load your requests</h2>

        <p>{state.error.message}</p>

        <button className="requests-refresh-button" onClick={onRetry} type="button">
          Try again
        </button>
      </section>
    );
  }

  if (!state.data.length) {
    return (
      <section aria-labelledby="requests-empty-title" className="requests-message-panel">
        <p className="portal-page-eyebrow">No requests yet</p>

        <h2 id="requests-empty-title">Your request history is empty</h2>

        <p>Media requested from supported Atlas experiences will appear here.</p>
      </section>
    );
  }

  return (
    <div className="requests-view">
      {mutationFailure ? (
        <section
          aria-labelledby="requests-mutation-error-title"
          className="requests-mutation-error"
          role="alert"
        >
          <h2 id="requests-mutation-error-title">
            {mutationFailure.reconciliationRequired
              ? "Request requires reconciliation"
              : "Cancellation was not confirmed"}
          </h2>

          <p>{mutationFailure.error.message}</p>

          <p>
            {mutationFailure.reconciliationRequired
              ? "Do not repeat the cancellation. Refresh only to inspect the latest Atlas state."
              : "Refresh the request list before attempting another cancellation."}
          </p>
        </section>
      ) : null}

      <section aria-label="Your media requests" className="requests-grid">
        {state.data.map((request) => (
          <RequestCard
            canCancel={canCancel}
            cancellingRequestId={cancellingRequestId}
            key={request.requestId}
            locallyBlocked={blockedCancellationIds.includes(request.requestId)}
            onBeginCancellation={onBeginCancellation}
            onCancelConfirmation={onCancelConfirmation}
            onConfirmCancellation={onConfirmCancellation}
            pendingCancellationId={pendingCancellationId}
            request={request}
          />
        ))}
      </section>
    </div>
  );
}

export function RequestsView({ onRefreshStateChange }: RequestsViewProps = {}): React.ReactElement {
  const { can } = usePermission();

  const {
    state,
    refresh,
    cancelRequest,
    cancellingRequestId,
    blockedCancellationIds,
    mutationFailure
  } = useRequests();

  const [pendingCancellationId, setPendingCancellationId] = useState<string | null>(null);

  const canCancel = can(ATLAS_PERMISSIONS.requestsCancel);

  const isBusy = state.status === "loading" || cancellingRequestId !== null;

  const handleRefresh = useCallback((): void => {
    // Refresh is observational. Discard any prior mutation intent so a newly
    // loaded lifecycle state always requires a fresh Cancel -> Confirm action.
    setPendingCancellationId(null);
    refresh();
  }, [refresh]);

  useEffect(() => {
    onRefreshStateChange?.(handleRefresh, isBusy);
  }, [handleRefresh, isBusy, onRefreshStateChange]);

  const handleConfirmCancellation = useCallback(
    async (requestId: string): Promise<void> => {
      await cancelRequest(requestId);

      // Whether cancellation succeeds or fails, the confirmation intent is
      // consumed. Failures remain blocked by useRequests until a safe GET.
      setPendingCancellationId(null);
    },
    [cancelRequest]
  );

  return (
    <RequestsContent
      blockedCancellationIds={blockedCancellationIds}
      canCancel={canCancel}
      cancellingRequestId={cancellingRequestId}
      mutationFailure={mutationFailure}
      onBeginCancellation={setPendingCancellationId}
      onCancelConfirmation={() => {
        setPendingCancellationId(null);
      }}
      onConfirmCancellation={handleConfirmCancellation}
      onRetry={handleRefresh}
      pendingCancellationId={pendingCancellationId}
      state={state}
    />
  );
}
