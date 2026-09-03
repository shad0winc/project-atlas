import type { Metadata } from "next";
import Image from "next/image";

import { GuestOnly } from "../../components/auth/GuestOnly";
import { ResetPasswordForm } from "../../components/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset password",
  description: "Set a new password for your Project Atlas account."
};

export default function ResetPasswordPage(): React.ReactElement {
  return (
    <GuestOnly>
      <main className="auth-page">
        <section
          aria-labelledby="atlas-reset-password-heading"
          className="auth-panel"
        >
          <div className="auth-brand">
            <Image
              alt="Project Atlas"
              height={56}
              priority
              src="/atlas-logo.svg"
              width={56}
            />

            <div>
              <p className="auth-eyebrow">
                Project Atlas
              </p>

              <h1
                className="auth-title"
                id="atlas-reset-password-heading"
              >
                Reset password
              </h1>
            </div>
          </div>

          <p className="auth-description">
            Choose a new password for your Atlas account.
          </p>

          <ResetPasswordForm />

          <p className="auth-help">
            Reset links expire after 60 minutes and can only be
            used once.
          </p>
        </section>
      </main>
    </GuestOnly>
  );
}
