import type { Metadata } from "next";
import Image from "next/image";

import { LoginForm } from "../../components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to the private Project Atlas Portal."
};

export default function LoginPage(): React.ReactElement {
  return (
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

        <LoginForm />

        <p className="auth-help">
          Your Atlas credentials are verified securely through the configured identity provider.
        </p>
      </section>
    </main>
  );
}
