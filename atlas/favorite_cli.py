"""Command-line interface for Atlas favorites."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atlas.events import publish_core_event
from atlas.favorite_service import FavoriteService
from atlas.favorites import FavoriteError, FavoriteStore, default_favorite_store
from atlas.media import default_jellyfin_provider
from atlas.user_profiles import UserProfileError, UserProfileStore, default_store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas favorite")
    parser.add_argument("--identity-directory")
    subparsers = parser.add_subparsers(dest="action", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--user", required=True, help="Atlas username or user ID")
    add_parser.add_argument("--provider", default="jellyfin")
    add_parser.add_argument("--item-id", required=True)
    add_parser.add_argument("--metadata-json")
    add_parser.add_argument("--json", action="store_true")

    remove_parser = subparsers.add_parser("remove")
    target = remove_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--favorite-id")
    target.add_argument("--item-id")
    remove_parser.add_argument("--user", help="Required with --item-id")
    remove_parser.add_argument("--provider", help="Required with --item-id")
    remove_parser.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--user", help="Atlas username or user ID")
    list_parser.add_argument("--provider")
    list_parser.add_argument("--type", dest="media_type")
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("favorite_id")

    subparsers.add_parser("verify")
    return parser


def _stores(args: argparse.Namespace) -> tuple[FavoriteStore, UserProfileStore]:
    if args.identity_directory:
        root = Path(args.identity_directory).expanduser().resolve()
        return FavoriteStore(root), UserProfileStore(root)
    return default_favorite_store(), default_store()


def _resolve_user_id(store: UserProfileStore, identifier: str | None) -> str | None:
    if identifier is None:
        return None
    return str(store.get_user(identifier)["user_id"])


def _metadata(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FavoriteError("metadata JSON is invalid") from exc
    if not isinstance(value, dict):
        raise FavoriteError("metadata JSON must be an object")
    return value


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    favorites, users = _stores(args)
    try:
        if args.action == "add":
            service = FavoriteService(favorites, {"jellyfin": default_jellyfin_provider()}, event_publisher=publish_core_event)
            result = service.add(_resolve_user_id(users, args.user), args.provider, args.item_id, metadata=_metadata(args.metadata_json))
            record = result.record
            if result.event_error:
                print(f"warning: favorite event failed: {result.event_error}", file=sys.stderr)
            if args.json:
                _print_json(record)
            else:
                print(f"Added favorite: {record['favorite_id']}")
                print(f"User: {args.user}")
                print(f"Provider: {record['provider']}")
                print(f"Item: {record['item_id']}")
                print(f"Title: {record['title'] or '-'}")
            return 0

        if args.action == "remove":
            favorite_id = args.favorite_id
            if favorite_id is None:
                if not args.user or not args.provider:
                    raise FavoriteError("--user and --provider are required with --item-id")
                record = favorites.find(
                    _resolve_user_id(users, args.user), args.provider, args.item_id
                )
                if record is None:
                    raise FavoriteError("favorite relationship not found")
                favorite_id = str(record["favorite_id"])
            service = FavoriteService(favorites, {"jellyfin": default_jellyfin_provider()}, event_publisher=publish_core_event)
            result = service.remove(favorite_id)
            removed = result.record
            if result.event_error:
                print(f"warning: favorite event failed: {result.event_error}", file=sys.stderr)
            if args.json:
                _print_json(removed)
            else:
                print(f"Removed favorite: {removed['favorite_id']}")
            return 0

        if args.action == "list":
            user_id = _resolve_user_id(users, args.user)
            records = favorites.list(
                user_id=user_id,
                provider=args.provider,
                media_type=args.media_type,
            )
            if args.json:
                _print_json(records)
            else:
                print("FAVORITE ID\tUSER ID\tPROVIDER\tTYPE\tTITLE")
                for record in records:
                    print(
                        f"{record['favorite_id']}\t{record['user_id']}\t"
                        f"{record['provider']}\t{record['media_type']}\t"
                        f"{record['title'] or '-'}"
                    )
            return 0

        if args.action == "show":
            _print_json(favorites.get(args.favorite_id))
            return 0

        if args.action == "verify":
            errors = favorites.verify()
            if errors:
                for error in errors:
                    print(f"FAIL\t{error}")
                return 1
            print("PASS\tfavorites valid")
            return 0
    except (FavoriteError, UserProfileError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
