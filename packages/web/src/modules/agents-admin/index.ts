/**
 * Agents Admin Module
 * Module for managing agents and admin users
 *
 * @module agents-admin
 * @date 2025-01-14
 *
 * BUSINESS RULES:
 * - Menu "Agents & Admins" manages users with roles: admin, agent
 * - Agents have agent_profiles with ministry/entity assignment
 * - Admins do not have agent profiles (full system access via role)
 * - Agent creation = user + profile atomically via POST /agents/complete
 * - Admin creation = user only via POST /agents/admin
 */

// Types
export * from './types';

// Services
export * from './services';

// Hooks
export * from './hooks';

// Components
export * from './components';
