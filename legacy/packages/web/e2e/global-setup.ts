import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Global setup for Playwright E2E tests
 * - Ensures auth directory exists
 * - Can perform any pre-test setup (database seeding, etc.)
 */
async function globalSetup(config: FullConfig) {
  // Create auth directory if it doesn't exist
  const authDir = path.join(__dirname, '../playwright/.auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  // Optional: Seed test data or perform other setup tasks
  console.log('Global setup complete');
}

export default globalSetup;
