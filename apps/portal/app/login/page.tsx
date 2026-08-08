import type { Metadata } from "next";
import Image from "next/image";
import { Suspense } from "react";

import { GuestOnly } from "../../components/auth/GuestOnly";
import { LoginForm } from "../../components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to the private Project Atlas Portal."
};

function LoginFormFallback(): React.ReactElement {
  return (
    <div aria-busy="true" aria-live="polite" className="auth-form">
      <div className="auth-field">
        <label className="auth-label" htmlFor="atlas-login-username-loading">
          Username
        </label>

        <input className="auth-input" disabled id="atlas-login-username-loading" type="text" />
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor="atlas-login-password-loading">
          Password
        </label>

        <input className="auth-input" disabled id="atlas-login-password-loading" type="password" />
      </div>

      <button className="auth-submit" disabled type="button">
        Loading…
      </button>
    </div>
  );
}

export default function LoginPage(): React.ReactElement {
  return (
    <GuestOnly>
      <main className="auth-page">
        <section aria-labelledby="atlas-login-heading" className="auth-panel">
          <div className="auth-brand">
            <Image alt="Project Atlas" height={56} priority src="/atlas-logo.svg" width={56} />

            <div>
              <p className="auth-eyebrow">Project Atlas</p>

              <h1 className="auth-title" id="atlas-login-heading">
                Welcome back
              </h1>
            </div>
          </div>

          <p className="auth-description">
            Sign in with your Atlas account to access your private media platform.
          </p>

          <Suspense fallback={<LoginFormFallback />}>
            <LoginForm />
          </Suspense>

          <p className="auth-help">
            Your Atlas credentials are verified securely through the configured identity provider.
          </p>
        </section>
      </main>
    </GuestOnly>
  );
}
