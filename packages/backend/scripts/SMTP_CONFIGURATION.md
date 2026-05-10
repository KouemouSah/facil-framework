# Configuration SMTP Gmail - TaxasGE Backend

## ⚠️ CRITIQUE: Configuration Requise pour l'Envoi d'Emails

Le backend TaxasGE utilise Gmail SMTP pour envoyer des emails de vérification. **Sans cette configuration, l'inscription utilisateur ÉCHOUERA.**

## 🔑 Secret Manager

**NOM DU SECRET**: `smtp-password` (lowercase avec tiret)
**IMPORTANT**: Le code charge depuis Google Cloud Secret Manager avec ce nom exact.

Le backend récupère automatiquement le secret via `app/core/secrets.py` qui appelle `get_secret("smtp-password")`.

---

## 🔴 Symptômes si SMTP non configuré

### Erreur côté utilisateur:
```
Erreur d'inscription
Erreur lors de l'envoi d'email de vérification: Le mot de passe d'application Gmail n'est pas configuré.
L'administrateur doit ajouter SMTP_PASSWORD dans Google Cloud Secret Manager.
```

### Logs backend:
```
SMTP connection failed: Authentication failed
Email verification failed for user xxx@gmail.com
Rolled back user creation due to email failure
```

---

## 📋 Prérequis

1. **Compte Gmail** avec accès administrateur
2. **Accès Google Cloud Console** pour le projet `taxasge-dev` ou `taxasge-pro`
3. **Permissions** pour créer des secrets dans Secret Manager

---

## 🔧 Étape 1: Obtenir le Mot de Passe Gmail

Vous utilisez votre mot de passe Gmail standard (pas App Password).

### Procédure:

1. **Connectez-vous au compte Gmail** `libressai@gmail.com` (ou votre compte SMTP)

2. **Activez la vérification en 2 étapes** (si pas déjà fait):
   - Allez sur https://myaccount.google.com/security
   - Cliquez sur "Validation en deux étapes"
   - Suivez les instructions

3. **Générez un mot de passe d'application**:
   - Allez sur https://myaccount.google.com/apppasswords
   - Sélectionnez "Autre (nom personnalisé)"
   - Entrez: `TaxasGE Backend`
   - Cliquez sur "Générer"
   - **COPIEZ le mot de passe** (16 caractères, ex: `abcd efgh ijkl mnop`)

⚠️ **IMPORTANT**: Ce mot de passe ne sera affiché qu'UNE SEULE FOIS. Sauvegardez-le temporairement.

---

## 🔐 Étape 2: Ajouter le Secret dans Google Cloud Secret Manager

### Option A: Via Console Google Cloud (Recommandé)

1. **Ouvrez Google Cloud Console**:
   - https://console.cloud.google.com/security/secret-manager?project=taxasge-dev

2. **Créez un nouveau secret**:
   - Cliquez sur "CREATE SECRET"
   - **Name**: `smtp-password`
   - **Secret value**: Collez le mot de passe d'application Gmail (16 caractères)
   - Cliquez sur "CREATE SECRET"

3. **Vérifiez les permissions**:
   - Le service account backend doit avoir le rôle `Secret Manager Secret Accessor`
   - Normalement déjà configuré dans le projet

### Option B: Via gcloud CLI

```bash
# Authentification
gcloud auth login
gcloud config set project taxasge-dev

# Créer le secret
echo -n "votre-mot-de-passe-app-gmail-16-chars" | \
  gcloud secrets create smtp-password \
  --data-file=- \
  --replication-policy="automatic"

# Vérifier
gcloud secrets versions access latest --secret="smtp-password"
```

---

## 🔄 Étape 3: Redéployer le Backend

Le backend charge les secrets au démarrage. Après avoir ajouté `smtp-password`:

### Pour Staging (Cloud Run):
```bash
# Le déploiement automatique via GitHub Actions récupère les secrets
# Poussez un commit vers develop pour déclencher le déploiement
git push origin develop
```

### Pour Local Development:
```bash
# Mettre à jour .env
cd packages/backend
echo "SMTP_PASSWORD=$(gcloud secrets versions access latest --secret='smtp-password')" >> .env

# Redémarrer le serveur
uvicorn main:app --reload
```

---

## ✅ Étape 4: Tester la Configuration

### Test manuel:
1. Allez sur votre environnement staging: https://taxasge-dev--staging-xxx.web.app
2. Cliquez sur "Inscription"
3. Remplissez le formulaire avec un **vrai email** auquel vous avez accès
4. Soumettez

### Résultats attendus:

#### ✅ Succès:
- Message: "Compte créé avec succès"
- Email reçu dans votre boîte de réception
- Redirection vers `/auth/verify-email`

#### ❌ Échec (SMTP non configuré):
```
Erreur d'inscription
Le mot de passe d'application Gmail n'est pas configuré.
L'administrateur doit ajouter SMTP_PASSWORD dans Google Cloud Secret Manager.
```

---

## 🐛 Troubleshooting

### Problème: "Authentication failed (535)"

**Cause**: Mot de passe d'application Gmail invalide ou expiré

**Solution**:
1. Régénérez un nouveau mot de passe d'application Gmail
2. Mettez à jour le secret `smtp-password` dans Secret Manager
3. Redéployez le backend

### Problème: "Connection refused"

**Cause**: Firewall bloque le port SMTP 587

**Solution**:
- Vérifiez que Cloud Run permet les connexions sortantes (normalement oui)
- Testez avec `telnet smtp.gmail.com 587`

### Problème: "Secret not found"

**Cause**: Le secret `smtp-password` n'existe pas dans Secret Manager

**Solution**:
```bash
gcloud secrets list --project=taxasge-dev | grep SMTP
# Si vide, créez le secret (voir Étape 2)
```

### Problème: "Permission denied"

**Cause**: Service account backend n'a pas accès au secret

**Solution**:
```bash
# Donner accès au service account
gcloud secrets add-iam-policy-binding smtp-password \
  --member="serviceAccount:backend-service@taxasge-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 📊 Configuration Actuelle

### Variables d'environnement backend:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=libressai@gmail.com
SMTP_PASSWORD=<from Google Cloud Secret Manager: smtp-password>
SMTP_USE_TLS=true
```

### Fichier: `packages/backend/.env`
```bash
# ✅ Configuré (hardcodé)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=libressai@gmail.com

# ⚠️ DOIT être dans Secret Manager
SMTP_PASSWORD=from_secret_manager  # ← REMPLACER par accès Secret Manager
```

---

## 🔗 Ressources

- [mot de passe Gmails](https://support.google.com/accounts/answer/185833)
- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
- [FastAPI Email Sending](https://fastapi.tiangolo.com/)
- [Python smtplib Documentation](https://docs.python.org/3/library/smtplib.html)

---

## 📝 Notes de Sécurité

1. **NE JAMAIS** commiter `SMTP_PASSWORD` en clair dans Git
2. **TOUJOURS** utiliser Secret Manager en production
3. **ROTATION**: Changer le mot de passe d'application tous les 3-6 mois
4. **MONITORING**: Surveiller les logs pour détecter les échecs SMTP
5. **RATE LIMITING**: Gmail limite à 500 emails/jour pour les App Passwords

---

**Dernière mise à jour**: 2025-11-03
**Responsable**: DevOps Team
**Contact**: support@taxasge.com
