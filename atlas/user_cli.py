"""Command-line interface for Atlas user profiles."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from atlas.media.jellyfin import default_jellyfin_provider
from atlas.media.provider import MediaProviderError
from atlas.user_profiles import UserProfileError, UserProfileStore, default_store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas user")
    parser.add_argument("--users-directory")
    subparsers = parser.add_subparsers(dest="action", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("identifier")

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("username")
    _add_profile_options(create_parser, include_status=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("identifier")
    _add_profile_options(update_parser, include_status=False)
    update_parser.add_argument("--username")

    for action in ("enable", "disable"):
        action_parser = subparsers.add_parser(action)
        action_parser.add_argument("identifier")

    link_parser = subparsers.add_parser("link-jellyfin")
    link_parser.add_argument("identifier")
    link_parser.add_argument("jellyfin_user_id")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("identifier", nargs="?")
    return parser


def _add_profile_options(parser: argparse.ArgumentParser, *, include_status: bool) -> None:
    parser.add_argument("--display-name")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--email")
    parser.add_argument("--birthday")
    parser.add_argument("--role", choices=("admin", "user"))
    parser.add_argument("--jellyfin-user-id")
    if include_status:
        parser.add_argument("--status", choices=("active", "disabled"))


def _store(args: argparse.Namespace) -> UserProfileStore:
    if args.users_directory:
        from pathlib import Path
        return UserProfileStore(Path(args.users_directory).expanduser().resolve())
    return default_store()


def _provided(args: argparse.Namespace, names: Sequence[str]) -> dict[str, Any]:
    return {name: getattr(args, name) for name in names if getattr(args, name, None) is not None}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = _store(args)
    try:
        if args.action == "list":
            users = store.list_users()
            if args.json:
                print(json.dumps(users, indent=2, sort_keys=True))
            else:
                print("USERNAME\tROLE\tSTATUS\tJELLYFIN\tDISPLAY NAME")
                for profile in users:
                    linked = "linked" if profile["jellyfin_user_id"] else "unlinked"
                    print(
                        f"{profile['username']}\t{profile['role']}\t{profile['status']}\t"
                        f"{linked}\t{profile['display_name']}"
                    )
            return 0

        if args.action == "show":
            print(json.dumps(store.get_user(args.identifier), indent=2, sort_keys=True))
            return 0

        if args.action == "create":
            values = _provided(
                args,
                ("display_name", "first_name", "last_name", "email", "birthday",
                 "role", "status", "jellyfin_user_id"),
            )
            print(json.dumps(store.create_user(args.username, **values), indent=2, sort_keys=True))
            return 0

        if args.action == "update":
            changes = _provided(
                args,
                ("username", "display_name", "first_name", "last_name", "email",
                 "birthday", "role", "jellyfin_user_id"),
            )
            if not changes:
                raise UserProfileError("no profile changes were provided")
            print(json.dumps(store.update_user(args.identifier, changes), indent=2, sort_keys=True))
            return 0

        if args.action in {"enable", "disable"}:
            status = "active" if args.action == "enable" else "disabled"
            print(json.dumps(store.update_user(args.identifier, {"status": status}), indent=2, sort_keys=True))
            return 0

        if args.action == "link-jellyfin":
            try:
                jellyfin_user = default_jellyfin_provider().get_user(
                    args.jellyfin_user_id
                )
            except MediaProviderError as exc:
                raise UserProfileError(
                    f"unable to link Jellyfin user: {exc}"
                ) from exc

            profile = store.update_user(
                args.identifier,
                {"jellyfin_user_id": jellyfin_user["id"]},
            )
            print(json.dumps(profile, indent=2, sort_keys=True))
            return 0

        if args.action == "verify":
            errors = store.verify(args.identifier)
            if errors:
                for error in errors:
                    print(f"FAIL\t{error}")
                return 1
            print("PASS\tuser profiles valid")
            return 0
    except UserProfileError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
