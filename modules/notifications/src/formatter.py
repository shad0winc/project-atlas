#!/usr/bin/env python3

from typing import Any


def format_notification(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")
    payload = notification.get("payload", {})

    if event_name == "atlas.health-changed":
        previous = payload.get("previous", "Unknown")
        current = payload.get("current", "Unknown")
        score = payload.get("score", "Unknown")

        return (
            "🚨 **Atlas Health Changed**\n"
            f"{previous} → {current}\n"
            f"Health Score: {score} / 100"
        )

    if event_name == "storage.low":
        available = payload.get("available", "Unknown")

        return (
            "💾 **Atlas Storage Warning**\n"
            f"Available Storage: {available}"
        )

    if event_name == "sports.game-started":
        game = payload.get("game", "Unknown")

        return (
            "🏟️ **Sports Event Started**\n"
            f"Game: {game}"
        )

    if event_name == "sports.game-finished":
        game = payload.get("game", "Unknown")
        status = payload.get("status", "Complete")

        return (
            "🏁 **Sports Event Finished**\n"
            f"Game: {game}\n"
            f"Status: {status}"
        )

    return (
        "ℹ️ **Project Atlas Notification**\n"
        f"Event: {event_name}"
    )
