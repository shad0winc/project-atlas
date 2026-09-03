"use client";

import Link from "next/link";
import {
  useEffect,
  useState,
  type FormEvent
} from "react";

import { resetAtlasPassword } from "../../lib/services/auth";

function resetErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  return "Unable to reset your password. Please try again.";
}

function readRecoveryToken(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;

  const params = new URLSearchParams(hash);

  return params.get("token")?.trim() ?? "";
}

export function ResetPasswordForm(): React.ReactElement {
  const [token, setToken] = useState<string>(
    readRecoveryToken
  );
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    window.history.replaceState(
      window.history.state,
      "",
      `${window.location.pathname}${window.location.search}`
    );
  }, []);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ): Promise<void> {
    event.preventDefault();

    if (!token) {
      setErrorMessage(
        "This password reset link is missing or invalid."
      );
      return;
    }

    if (!password) {
      setErrorMessage("Enter a new password.");
      return;
    }

    if (password !== confirmation) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await resetAtlasPassword({
        token,
        newPassword: password
      });

      setPassword("");
      setConfirmation("");
      setToken("");
      setIsComplete(true);
    } catch (error: unknown) {
      setErrorMessage(resetErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isComplete) {
    return (
      <div className="auth-form">
        <p
          className="auth-success"
          role="status"
        >
          Your password has been reset successfully.
        </p>

        <Link
          className="auth-submit auth-submit-link"
          href="/login"
        >
          Return to sign in
        </Link>
      </div>
    );
  }

  if (!token) {
    return (
      <>
        <p className="auth-error" role="alert">
          This password reset link is missing or invalid.
        </p>

        <p className="auth-secondary-action">
          <Link href="/forgot-password">
            Request a new reset link
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      <form
        className="auth-form"
        noValidate
        onSubmit={handleSubmit}
      >
        <div className="auth-field">
          <label
            className="auth-label"
            htmlFor="atlas-reset-password"
          >
            New password
          </label>

          <input
            autoComplete="new-password"
            className="auth-input"
            disabled={isSubmitting}
            id="atlas-reset-password"
            name="password"
            onChange={(event) =>
              setPassword(event.target.value)
            }
            required
            type="password"
            value={password}
          />
        </div>

        <div className="auth-field">
          <label
            className="auth-label"
            htmlFor="atlas-reset-password-confirmation"
          >
            Confirm new password
          </label>

          <input
            autoComplete="new-password"
            className="auth-input"
            disabled={isSubmitting}
            id="atlas-reset-password-confirmation"
            name="password-confirmation"
            onChange={(event) =>
              setConfirmation(event.target.value)
            }
            required
            type="password"
            value={confirmation}
          />
        </div>

        {errorMessage ? (
          <p className="auth-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <button
          className="auth-submit"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting
            ? "Resetting…"
            : "Reset password"}
        </button>
      </form>

      <p className="auth-secondary-action">
        <Link href="/login">
          Back to sign in
        </Link>
      </p>
    </>
  );
}
