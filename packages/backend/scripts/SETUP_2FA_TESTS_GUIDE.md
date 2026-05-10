# Guide de Setup des Tests 2FA Login

Ce guide vous permet d'exécuter les 7 tests skipped pour valider complètement le flux 2FA avec une vraie base de données Supabase.

## Étape 1 : Créer les utilisateurs de test dans Supabase

### Option A : Via l'interface web Supabase (RECOMMANDÉ)

1. Ouvrez votre projet Supabase : https://supabase.com/dashboard/project/bpdzfkymgydjxxwlctam

2. Allez dans **SQL Editor**

3. Copiez-collez le contenu du fichier `setup_2fa_test_users.sql` dans l'éditeur

4. Cliquez sur **RUN** pour exécuter le script

5. Vérifiez que 2 utilisateurs ont été créés :
   ```sql
   SELECT email, two_factor_enabled FROM users
   WHERE email IN ('test_2fa_user@taxasge.com', 'test_no2fa_user@taxasge.com');
   ```

### Option B : Via psql (ligne de commande)

```bash
cd packages/backend
psql "postgresql://postgres:taxasge-db25@db.bpdzfkymgydjxxwlctam.supabase.co:5432/postgres" -f scripts/setup_2fa_test_users.sql
```

## Étape 2 : Mettre à jour les constantes de test

Ouvrez le fichier `tests/integration/test_auth_2fa_login_endpoints.py` et mettez à jour les constantes (lignes ~210-220) :

```python
# DÉJÀ CONFIGURÉ - Pas besoin de changer
TEST_2FA_USER_EMAIL = "test_2fa_user@taxasge.com"
TEST_2FA_USER_PASSWORD = "TestPass2FA123!"
TEST_2FA_USER_SECRET = "JBSWY3DPEHPK3PXP"

TEST_NO2FA_USER_EMAIL = "test_no2fa_user@taxasge.com"
TEST_NO2FA_USER_PASSWORD = "TestPassNo2FA456!"
```

## Étape 3 : Décommenter les tests skipped

Dans le fichier `tests/integration/test_auth_2fa_login_endpoints.py`, **supprimez les décorateurs** `@pytest.mark.skip` devant les classes suivantes :

### Tests à décommenter (7 tests au total) :

1. **TestLoginWith2FAEnabledUser** (lignes ~345-405)
   ```python
   # @pytest.mark.skip(reason="...")  # ← SUPPRIMEZ CETTE LIGNE
   class TestLoginWith2FAEnabledUser:
       ...
   ```

2. **TestLoginWithout2FA** (lignes ~406-445)
   ```python
   # @pytest.mark.skip(reason="...")  # ← SUPPRIMEZ CETTE LIGNE
   class TestLoginWithout2FA:
       ...
   ```

3. **TestTwoFactorVerifyEndpoint** (lignes ~446-555)
   ```python
   # @pytest.mark.skip(reason="...")  # ← SUPPRIMEZ CETTE LIGNE
   class TestTwoFactorVerifyEndpoint:
       ...
   ```

4. **TestE2E2FALoginFlow** (lignes ~556-719)
   ```python
   # @pytest.mark.skip(reason="...")  # ← SUPPRIMEZ CETTE LIGNE
   class TestE2E2FALoginFlow:
       ...
   ```

## Étape 4 : Exécuter les tests

```bash
cd packages/backend

# Tous les tests 2FA login
pytest tests/integration/test_auth_2fa_login_endpoints.py -v

# Seulement les tests réels (pas les validations)
pytest tests/integration/test_auth_2fa_login_endpoints.py::TestLoginWith2FAEnabledUser -v
pytest tests/integration/test_auth_2fa_login_endpoints.py::TestLoginWithout2FA -v
pytest tests/integration/test_auth_2fa_login_endpoints.py::TestTwoFactorVerifyEndpoint -v
pytest tests/integration/test_auth_2fa_login_endpoints.py::TestE2E2FALoginFlow -v
```

### Résultats attendus

```
======================== test session starts ========================
tests/integration/test_auth_2fa_login_endpoints.py::TestLoginWith2FAEnabledUser::test_login_with_2fa_enabled_returns_temp_token PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestLoginWith2FAEnabledUser::test_login_with_2fa_remember_me_preserved PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestLoginWithout2FA::test_login_without_2fa_returns_tokens_immediately PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestTwoFactorVerifyEndpoint::test_2fa_verify_with_valid_totp_code PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestTwoFactorVerifyEndpoint::test_2fa_verify_with_invalid_code PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestTwoFactorVerifyEndpoint::test_2fa_verify_with_wrong_token_type PASSED
tests/integration/test_auth_2fa_login_endpoints.py::TestE2E2FALoginFlow::test_complete_2fa_login_flow PASSED

=================== 7 passed in 3.5s ====================
```

## Étape 5 : Tests manuels (optionnel)

### Test 1 : Login avec 2FA (devrait retourner temp_token)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test_2fa_user@taxasge.com", "password": "TestPass2FA123!", "remember_me": false}' \
  | python -m json.tool
```

**Réponse attendue** :
```json
{
  "requires_2fa": true,
  "temp_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "message": "2FA verification required. Please provide your 2FA code."
}
```

### Test 2 : Générer un code TOTP

```bash
python -c "import pyotp; print(pyotp.TOTP('JBSWY3DPEHPK3PXP').now())"
```

**Exemple de sortie** : `123456` (code à 6 chiffres, change toutes les 30 secondes)

### Test 3 : Vérifier 2FA avec le code

```bash
# Remplacez <TEMP_TOKEN> et <CODE>
curl -X POST http://localhost:8000/api/v1/auth/login/2fa-verify \
  -H "Content-Type: application/json" \
  -d '{"temp_token": "<TEMP_TOKEN>", "code": "<CODE>"}' \
  | python -m json.tool
```

**Réponse attendue** :
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "test_2fa_user_id_1234567890",
    "email": "test_2fa_user@taxasge.com",
    ...
  }
}
```

### Test 4 : Login sans 2FA (devrait retourner les tokens directement)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test_no2fa_user@taxasge.com", "password": "TestPassNo2FA456!", "remember_me": false}' \
  | python -m json.tool
```

**Réponse attendue** (pas de temp_token, accès direct) :
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {...}
}
```

## Informations utiles

### Codes de backup pour test (2FA)

Si vous voulez tester avec un backup code au lieu d'un code TOTP :

```
1234-5678
9876-5432
```

**Note** : Après utilisation, le backup code sera supprimé de la base de données (one-time use).

### Identifiants de test

**Utilisateur avec 2FA** :
- Email : `test_2fa_user@taxasge.com`
- Password : `TestPass2FA123!`
- TOTP Secret : `JBSWY3DPEHPK3PXP`

**Utilisateur sans 2FA** :
- Email : `test_no2fa_user@taxasge.com`
- Password : `TestPassNo2FA456!`

### Nettoyage (optionnel)

Pour supprimer les utilisateurs de test après les tests :

```sql
DELETE FROM users WHERE email IN (
    'test_2fa_user@taxasge.com',
    'test_no2fa_user@taxasge.com'
);
```

## Dépannage

### Problème : "Invalid or expired 2FA code"

- Vérifiez que le code TOTP est bien généré avec le bon secret : `JBSWY3DPEHPK3PXP`
- Les codes TOTP expirent toutes les 30 secondes, régénérez-en un nouveau
- Vérifiez que l'horloge système est synchronisée (TOTP dépend du temps)

### Problème : "2FA is not enabled for this account"

- Vérifiez que l'utilisateur a bien `two_factor_enabled = TRUE` dans la DB :
  ```sql
  SELECT email, two_factor_enabled FROM users WHERE email = 'test_2fa_user@taxasge.com';
  ```

### Problème : "Invalid or expired temporary token"

- Le temp_token expire après 5 minutes
- Refaites un login pour obtenir un nouveau temp_token
- Vérifiez que vous utilisez bien le temp_token retourné par `/login`, pas un access_token

### Problème : Tests échouent avec "Connection refused"

- Vérifiez que le backend FastAPI est lancé : `uvicorn app.main:app --reload`
- Le backend doit tourner sur `http://localhost:8000`

## Prochaines étapes

Une fois tous les tests passent (23/23), vous pouvez :

1. **Commiter les changements** (tests décommentés)
2. **Créer le rapport final MODULE_01**
3. **Continuer vers MODULE_02** (Password Reset, Email Verification)

**Fichiers modifiés pour commit** :
- `tests/integration/test_auth_2fa_login_endpoints.py` (7 tests décommentés)
- `scripts/setup_2fa_test_users.sql` (nouveau fichier)
- `scripts/run_2fa_test_users_setup.py` (nouveau fichier)
- `scripts/SETUP_2FA_TESTS_GUIDE.md` (ce guide)

---

**Source** : TASK-M01-013 - 2FA Login Integration
**Date** : 2025-11-02
