import {
  createDislikeRecord,
  readDislikes,
  removeDislikeRecord,
  type CreateDislikeOptions,
  type DislikeCreateInput,
  type ReadDislikesOptions,
  type RemoveDislikeOptions
} from "../services/dislikes";
import type { Dislike } from "../types/dislikes";

export type AddDislikeOptions = CreateDislikeOptions;
export type AddDislikeInput = DislikeCreateInput;
export type LoadDislikesOptions = ReadDislikesOptions;
export type RemoveDislikeRequestOptions = RemoveDislikeOptions;

export async function loadDislikes(options: LoadDislikesOptions): Promise<readonly Dislike[]> {
  return readDislikes(options);
}

export async function addDislike(
  input: AddDislikeInput,
  options: AddDislikeOptions
): Promise<Dislike> {
  return createDislikeRecord(input, options);
}

export async function removeDislike(
  dislikeId: string,
  options: RemoveDislikeRequestOptions
): Promise<Dislike> {
  return removeDislikeRecord(dislikeId, options);
}
