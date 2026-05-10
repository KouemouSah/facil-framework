/**
 * Expo config plugin — writes android/app/src/main/assets/adi-registration.properties
 * during prebuild so the APK ships with the Android Developer Identity (ADI)
 * verification token required by Play Console "Validation des développeurs Android".
 *
 * Status (2026-05-07): Inspector (com.facil.inspeccion) has NOT yet been
 * registered on Play Console — no token has been issued. The plugin reads
 * ADI_REGISTRATION_TOKEN_INSPECTOR env var and writes it if non-empty;
 * otherwise it does nothing (ADI verification step doesn't apply yet).
 *
 * To activate when shipping inspector to Play Store:
 *   1. Register package com.facil.inspeccion in Play Console developer
 *      verification dialog → declare an eligible public key (capture the
 *      EAS keystore SHA-256 from
 *      https://expo.dev/accounts/emacsah/projects/facil-inspeccion/credentials/android).
 *   2. Click "Signer et importer un APK" → copy the unique token snippet.
 *   3. Set the token as an EAS env var (preview + production):
 *        eas env:create --name ADI_REGISTRATION_TOKEN_INSPECTOR \
 *          --value "<token>" --environment preview
 *        eas env:create --name ADI_REGISTRATION_TOKEN_INSPECTOR \
 *          --value "<token>" --environment production
 *   4. Set the same as a GitHub Secret for the native CI path
 *      (inspector-ci.yml if it ever runs Gradle natively).
 *   5. Trigger a fresh build → upload the resulting APK to Play Console
 *      "Signer et importer un APK".
 *
 * Mirrors packages/mobile/plugins/with-adi-registration.js — keep the
 * two in sync if one of them needs a fix.
 */
const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

function withAdiRegistration(config) {
  return withDangerousMod(config, [
    'android',
    async (cfg) => {
      const token = (process.env.ADI_REGISTRATION_TOKEN_INSPECTOR || '').trim();
      if (!token) {
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
