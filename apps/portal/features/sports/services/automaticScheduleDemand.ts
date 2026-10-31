import type { SportsFollow } from "../types/sports";
import type { SportsEventFilter } from "./sports";
import type { UpcomingSelection } from "./upcomingSchedule";

/** Only an explicit disabled catalog permits the original provider polling loop. */
export function automaticScheduleDemand(
  follows: readonly SportsFollow[],
  browse: UpcomingSelection | undefined,
  curatedEnabled: boolean | null | undefined,
): Readonly<{ follows: readonly SportsFollow[]; browse: UpcomingSelection | undefined }> {
  if (curatedEnabled === false) return { follows, browse };
  return {
    follows: follows.filter(follow => follow.provider === "espn"),
    browse: browse?.provider === "espn" ? browse : undefined,
  };
}

/** One deliberate legacy browse loads the provider's follows coherently, without a timer. */
export function manualScheduleDemand(follows: readonly SportsFollow[], browse: UpcomingSelection): SportsEventFilter {
  if (!browse.provider.trim() || !browse.providerId.trim()) throw new Error("Choose a saved Sport to browse.");
  const eventIds = new Set<string>(), teamIds = new Set<string>(), leagueIds = new Set<string>();
  for (const follow of follows) {
    if (!follow.enabled || follow.type === "channel" || follow.provider !== browse.provider || !follow.providerId.trim()) continue;
    (follow.type === "event" ? eventIds : follow.type === "team" ? teamIds : leagueIds).add(follow.providerId);
  }
  (browse.type === "team" ? teamIds : leagueIds).add(browse.providerId);
  return { provider: browse.provider, eventIds: [...eventIds], teamIds: [...teamIds], leagueIds: [...leagueIds] };
}
