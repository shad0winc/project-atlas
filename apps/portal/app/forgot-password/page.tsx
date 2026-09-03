import type { Metadata } from "next";
import Image from "next/image";

import { GuestOnly } from "../../components/auth/GuestOnly";
import { ForgotPasswordForm } from "../../components/auth/ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Forgot password",
  description: "Request a Project Atlas password reset link."
};

export default function ForgotPasswordPage(): React.ReactElement {
  return (
    <GuestOnly>
      <main className="auth-page">
        <section
          aria-labelledby="atlas-forgot-password-heading"
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
                id="atlas-forgot-password-heading"
              >
                Forgot password?
              </h1>
            </div>
          </div>

          <p className="auth-description">
            Enter the email associated with your Atlas account.
            If the account is eligible for recovery, Atlas will
            send a secure reset link.
          </p>

          <ForgotPasswordForm />

          <p className="auth-help">
            For security, Atlas does not reveal whether an email
            address belongs to an account.
          </p>
        </section>
      </main>
    </GuestOnly>
  );
}
