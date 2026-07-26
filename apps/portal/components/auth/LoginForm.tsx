"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useAuth } from "../../lib/auth/use-auth";

function authenticationErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  return "Unable to sign in. Please try again.";
}

export function LoginForm(): React.ReactElement {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, status } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isSubmitting = status === "loading";

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const normalizedUsername = username.trim();

    if (!normalizedUsername || !password) {
      setErrorMessage("Enter your username and password.");
      return;
    }

    setErrorMessage(null);

    try {
      await login({
        username: normalizedUsername,
        password
      });

      const requestedPath = searchParams.get("next");
      const destination =
        requestedPath?.startsWith("/") && !requestedPath.startsWith("//")
          ? requestedPath
          : "/portal";

      router.replace(destination);
      router.refresh();
    } catch (error: unknown) {
      setErrorMessage(authenticationErrorMessage(error));
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="auth-field">
        <label className="auth-label" htmlFor="atlas-login-username">
          Username
        </label>

        <input
          autoComplete="username"
          className="auth-input"
          disabled={isSubmitting}
          id="atlas-login-username"
          name="username"
          onChange={(event) => setUsername(event.target.value)}
          required
          type="text"
          value={username}
        />
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor="atlas-login-password">
          Password
        </label>

        <input
          autoComplete="current-password"
          className="auth-input"
          disabled={isSubmitting}
          id="atlas-login-password"
          name="password"
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
      </div>

      {errorMessage ? (
        <p className="auth-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <button className="auth-submit" disabled={isSubmitting} type="submit">
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
