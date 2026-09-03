"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { requestAtlasPasswordRecovery } from "../../lib/services/auth";

const GENERIC_MESSAGE =
  "If an Atlas account exists for that email, a password reset link has been sent.";

function recoveryErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  return "Unable to request password recovery. Please try again.";
}

export function ForgotPasswordForm(): React.ReactElement {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ): Promise<void> {
    event.preventDefault();

    const normalizedEmail = email.trim();

    if (!normalizedEmail) {
      setErrorMessage("Enter your account email.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setMessage(null);

    try {
      await requestAtlasPasswordRecovery(normalizedEmail);

      setMessage(GENERIC_MESSAGE);
    } catch (error: unknown) {
      setErrorMessage(recoveryErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
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
            htmlFor="atlas-recovery-email"
          >
            Email
          </label>

          <input
            autoComplete="email"
            className="auth-input"
            disabled={isSubmitting}
            id="atlas-recovery-email"
            name="email"
            onChange={(event) =>
              setEmail(event.target.value)
            }
            required
            type="email"
            value={email}
          />
        </div>

        {errorMessage ? (
          <p className="auth-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        {message ? (
          <p
            className="auth-success"
            role="status"
          >
            {message}
          </p>
        ) : null}

        <button
          className="auth-submit"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting
            ? "Sending…"
            : "Send reset link"}
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
