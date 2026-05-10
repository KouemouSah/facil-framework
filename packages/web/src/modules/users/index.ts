/**
 * Users Module
 * User profile self-service (not admin management)
 */

// Components - Rename UserProfile component to avoid conflict with type
export { UserProfile as UserProfileComponent } from "./components";

// Services
export * from "./services";

// Types
export type {
  UserRole,
  UserStatus,
  UserProfile,
  CitizenProfile,
  BusinessProfile,
  UserResponse,
  ProfileUpdateRequest,
  PasswordChangeRequest,
} from "./types";
