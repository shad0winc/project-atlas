export { addDislike, loadDislikes, removeDislike } from "./api/dislikes";
export type {
  AddDislikeInput,
  AddDislikeOptions,
  LoadDislikesOptions,
  RemoveDislikeRequestOptions
} from "./api/dislikes";

export { DislikeAction } from "./components/DislikeAction";

export {
  createDislikeRecord,
  readDislikes,
  removeDislikeRecord
} from "./services/dislikes";

export type {
  CreateDislikeOptions,
  DislikeCreateInput,
  ReadDislikesOptions,
  RemoveDislikeOptions
} from "./services/dislikes";

export {
  createDislike,
  createDislikeCollection,
  createDislikesState,
  normalizeDislikeId,
  normalizeDislikeUserId
} from "./types/dislikes";
