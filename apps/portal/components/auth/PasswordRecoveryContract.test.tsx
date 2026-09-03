import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return fs.readFileSync(
    path.resolve(process.cwd(), relativePath),
    "utf8"
  );
}

describe("password recovery Portal contract", () => {
  it("exposes Forgot password from login", () => {
    const login = source(
      "components/auth/LoginForm.tsx"
    );

    expect(login).toContain(
      'href="/forgot-password"'
    );
    expect(login).toContain(
      "Forgot password?"
    );
  });

  it("keeps account enumeration messaging generic", () => {
    const forgot = source(
      "components/auth/ForgotPasswordForm.tsx"
    );

    expect(forgot).toContain(
      "If an Atlas account exists for that email"
    );
    expect(forgot).not.toContain(
      "Account not found"
    );
  });

  it("captures recovery token from the URL fragment", () => {
    const reset = source(
      "components/auth/ResetPasswordForm.tsx"
    );

    expect(reset).toContain(
      "window.location.hash"
    );
    expect(reset).toContain(
      'params.get("token")'
    );
    expect(reset).toContain(
      "readRecoveryToken"
    );
  });

  it("removes the recovery fragment immediately", () => {
    const reset = source(
      "components/auth/ResetPasswordForm.tsx"
    );

    expect(reset).toContain(
      "window.history.replaceState"
    );
    expect(reset).toContain(
      "`${window.location.pathname}${window.location.search}`"
    );
  });

  it("requires password confirmation before reset", () => {
    const reset = source(
      "components/auth/ResetPasswordForm.tsx"
    );

    expect(reset).toContain(
      "password !== confirmation"
    );
    expect(reset).toContain(
      "Passwords do not match."
    );
  });

  it("does not render the reset token into the UI", () => {
    const reset = source(
      "components/auth/ResetPasswordForm.tsx"
    );

    expect(reset).not.toContain(
      "{token}"
    );
    expect(reset).not.toContain(
      'value={token}'
    );
  });
});
