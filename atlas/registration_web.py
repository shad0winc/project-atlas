"""Dependency-free WSGI portal for invitation-based Atlas registration."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qs

from atlas.invitations import InvitationError, InvitationStore
from atlas.registration import RegistrationError, RegistrationService

StartResponse = Callable[[str, list[tuple[str, str]]], Any]
_TEMPLATE_DIR = Path(__file__).with_name("templates") / "registration"
_MAX_FORM_BYTES = 32 * 1024


@dataclass(frozen=True)
class RegistrationPortal:
    """Small WSGI application that delegates registration to Atlas services."""

    invitations: InvitationStore
    registrations: RegistrationService
    continue_url: str = "/"

    def __call__(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if path == "/health" and method == "GET":
            return self._respond(start_response, "200 OK", b"healthy\n", "text/plain; charset=utf-8")
        if path != "/register":
            return self._page(start_response, "404 Not Found", "error.html", title="Not found", message="The requested page was not found.")
        if method == "GET":
            return self._get_register(environ, start_response)
        if method == "POST":
            return self._post_register(environ, start_response)
        return self._page(start_response, "405 Method Not Allowed", "error.html", title="Method not allowed", message="This request method is not supported.", extra_headers=[("Allow", "GET, POST")])

    def _get_register(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        token = _single(parse_qs(str(environ.get("QUERY_STRING", ""))), "token")
        if not token:
            return self._page(start_response, "400 Bad Request", "error.html", title="Invalid invitation", message="This invitation link is missing its token.")
        try:
            invitation = self.invitations.verify_token(token)
        except InvitationError as exc:
            return self._page(start_response, "410 Gone", "error.html", title="Invitation unavailable", message=str(exc))
        return self._page(
            start_response,
            "200 OK",
            "register.html",
            token=token,
            email=invitation.get("email") or "Not specified",
            role=invitation["role"],
            username="",
            display_name="",
            error="",
        )

    def _post_register(self, environ: Mapping[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        try:
            form = _read_form(environ)
        except ValueError as exc:
            return self._page(start_response, "400 Bad Request", "error.html", title="Invalid request", message=str(exc))

        token = _single(form, "token")
        username = _single(form, "username").strip()
        display_name = _single(form, "display_name").strip() or None
        password = _single(form, "password")
        confirmation = _single(form, "confirm_password")
        if not token or not username or not password:
            return self._form_error(start_response, token, username, display_name, "Token, username, and password are required.")
        if password != confirmation:
            return self._form_error(start_response, token, username, display_name, "Passwords do not match.")
        try:
            result = self.registrations.register(token=token, username=username, password=password, display_name=display_name)
        except RegistrationError as exc:
            message = str(exc)
            if exc.rollback_errors:
                message += " An administrator should review rollback errors."
            return self._form_error(start_response, token, username, display_name, message)
        return self._page(
            start_response,
            "201 Created",
            "success.html",
            display_name=result.profile.get("display_name") or result.profile["username"],
            username=result.profile["username"],
            continue_url=self.continue_url,
            event_warning="Registration completed, but audit event delivery failed." if result.event_error else "",
        )

    def _form_error(self, start_response: StartResponse, token: str, username: str, display_name: str | None, message: str) -> Iterable[bytes]:
        email = "Not specified"
        role = "user"
        try:
            invitation = self.invitations.verify_token(token)
            email = invitation.get("email") or email
            role = invitation["role"]
        except InvitationError:
            pass
        return self._page(start_response, "400 Bad Request", "register.html", token=token, email=email, role=role, username=username, display_name=display_name or "", error=message)

    @staticmethod
    def _respond(start_response: StartResponse, status: str, body: bytes, content_type: str, extra_headers: list[tuple[str, str]] | None = None) -> Iterable[bytes]:
        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"),
        ]
        headers.extend(extra_headers or [])
        start_response(status, headers)
        return [body]

    def _page(self, start_response: StartResponse, status: str, template: str, extra_headers: list[tuple[str, str]] | None = None, **context: Any) -> Iterable[bytes]:
        body = _render(template, context).encode("utf-8")
        return self._respond(start_response, status, body, "text/html; charset=utf-8", extra_headers)


def _read_form(environ: Mapping[str, Any]) -> dict[str, list[str]]:
    content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise ValueError("form content type must be application/x-www-form-urlencoded")
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError as exc:
        raise ValueError("invalid content length") from exc
    if length < 0 or length > _MAX_FORM_BYTES:
        raise ValueError("registration form is too large")
    stream = environ.get("wsgi.input")
    if stream is None:
        raise ValueError("request body is unavailable")
    return parse_qs(stream.read(length).decode("utf-8"), keep_blank_values=True)


def _single(values: Mapping[str, list[str]], name: str) -> str:
    items = values.get(name, [])
    return items[0] if len(items) == 1 else ""


def _render(name: str, context: Mapping[str, Any]) -> str:
    template = (_TEMPLATE_DIR / name).read_text(encoding="utf-8")
    escaped = {key: html.escape(str(value), quote=True) for key, value in context.items()}
    for key, value in escaped.items():
        template = template.replace("{{ " + key + " }}", value)
    return template
