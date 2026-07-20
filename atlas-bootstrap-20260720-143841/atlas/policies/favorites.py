"""Favorite-based media protection policy."""

from __future__ import annotations

from atlas.policies.engine import PolicyContext
from atlas.policies.models import PolicyReason


class FavoriteRule:
    """Protect media that has been favorited by one or more Atlas users."""

    def evaluate(
        self,
        context: PolicyContext,
    ) -> list[PolicyReason]:
        favorites = [
            favorite
            for favorite in context.providers.favorites.list(
                provider=context.provider,
            )
            if favorite["item_id"] == context.item_id
        ]

        if not favorites:
            return []

        user_ids = sorted(
            {
                str(favorite["user_id"])
                for favorite in favorites
            }
        )

        favorite_count = len(favorites)
        user_count = len(user_ids)

        return [
            PolicyReason(
                code="favorite",
                source="atlas.favorites",
                detail=(
                    f"Media is favorited by {user_count} "
                    f"Atlas user{'s' if user_count != 1 else ''}."
                ),
                metadata={
                    "favorite_count": favorite_count,
                    "user_count": user_count,
                    "user_ids": user_ids,
                },
            )
        ]
