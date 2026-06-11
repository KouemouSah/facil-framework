/**
 * Expo config plugin — writes android/app/src/main/assets/adi-registration.properties
 * during prebuild so the APK ships with the Android Developer Identity (ADI)
 * verification token required by Play Console "Validation des développeurs Android".
 *
 * Token resolution order:
 *   1. ADI_REGISTRATION_TOKEN env var (preferred — set in EAS env + GitHub Secret)
 *   2. Hardcoded DEFAULT_TOKEN below (fallback)
 *
 * The fallback exists because:
 *   - The token is a one-time ownership proof tied to com.taxasge.app + the
 *     EAS upload key SHA-256. Once Play Console validates, the token is
 *     useless to anyone else (you can't claim ownership of a package whose
 *     signing key you don't control).
 *   - It keeps `expo prebuild` working locally without forcing every dev to
 *     export an env var.
 *
 * Why a config plugin and not a committed file:
 *   - `expo prebuild --clean` (used by mobile-build.yml CI workflow) wipes
 *     the entire android/ folder, including any committed assets/ contents.
 *   - This plugin runs as part of prebuild and recreates the file every time.
 *   - For EAS Cloud builds in non-CNG mode (committed android/), the plugin
 *     is also called and (re)writes the file harmlessly.
 */
const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

// Play Console "Signer et importer un APK" → "Copiez l'extrait ci-dessous"
// Tied to com.taxasge.app + EAS upload key SHA-256 C4:78:D6:B0:6D:88:5F:E6:...
const DEFAULT_TOKEN = 'CXZYNVIZWNFLAAAAAAAAAAAAAA';

function withAdiRegistration(config) {
  return withDangerousMod(config, [
    'android',
    async (cfg) => {
      const token = (process.env.ADI_REGISTRATION_TOKEN || DEFAULT_TOKEN).trim();
      if (!token) {
        // Inspector-style placeholder build path: skip silently.
        return cfg;
      }
      const assetsDir = path.join(
        cfg.modRequest.platformProjectRoot,
        'app',
        'src',
        'main',
        'assets'
      );
      fs.mkdirSync(assetsDir, { recursive: true });
      fs.writeFileSync(
        path.join(assetsDir, 'adi-registration.properties'),
        token + '\n',
        'utf8'
      );
      return cfg;
    },
  ]);
}

module.exports = withAdiRegistration;
