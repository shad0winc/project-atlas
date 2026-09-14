import { addFavorite } from "../../favorites";
import { addDislike } from "../../dislikes/api/dislikes";

import {
  refreshMediaRetentionAfterMutation,
  type MediaRetentionRefreshResult
} from "./retention-refresh";

type FavoriteInput =
  Parameters<typeof addFavorite>[0];

type FavoriteOptions =
  Parameters<typeof addFavorite>[1];

type DislikeInput =
  Parameters<typeof addDislike>[0];

type DislikeOptions =
  Parameters<typeof addDislike>[1];

export async function addFavoriteAndRefreshRetention(
  input: FavoriteInput,
  options: FavoriteOptions
): Promise<MediaRetentionRefreshResult> {
  await addFavorite(input, options);

  return refreshMediaRetentionAfterMutation(
    input.provider,
    input.itemId
  );
}

export type DislikeSuccessCallback =
  () => void | Promise<void>;

export async function addDislikeAndNotify(
  input: DislikeInput,
  options: DislikeOptions,
  onDisliked?: DislikeSuccessCallback
): Promise<void> {
  await addDislike(input, options);

  if (onDisliked === undefined) {
    return;
  }

  try {
    await onDisliked();
  } catch {
    // The Dislike mutation already succeeded.
    // Post-success refresh/notification failure must not
    // rewrite that mutation as failed.
  }
}
