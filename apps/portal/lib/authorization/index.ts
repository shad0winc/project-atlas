export {
  ATLAS_PERMISSIONS,
  atlasPermissionPatternMatches,
  hasAnyAtlasPermission,
  hasAtlasPermission,
  hasEveryAtlasPermission,
  normalizeAtlasPermission,
  type AtlasEffectivePermissionPatterns,
  type AtlasPermission
} from "./permissions";

export { usePermission, type AtlasPermissionEvaluation } from "./use-permission";
