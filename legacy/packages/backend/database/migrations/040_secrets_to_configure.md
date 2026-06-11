# Secrets to Configure in Google Cloud Secret Manager

## Project: `taxasge-dev`

### Verified Identifiers Encryption Keys

| Secret Name | Value (Base64) | Description |
|-------------|----------------|-------------|
| `verified-identifiers-aes-key` | `wBQJnpSZbYQvhdVpPJBYBKClTlqFlA7X6A+a7tgxMfQ=` | AES-256-GCM encryption key (32 bytes) |
| `verified-identifiers-hmac-key` | `N2x5qY5TryRvMxOMoEHNNhVqD0kBCecyxtSD17jW2tA=` | HMAC-SHA256 blind index key (32 bytes) |

---

## Manual Configuration Steps

### 1. Create Secrets

```powershell
# In PowerShell or CMD

# Create AES key
gcloud secrets create verified-identifiers-aes-key ^
  --project=taxasge-dev ^
  --replication-policy="automatic"

# Add secret value
echo wBQJnpSZbYQvhdVpPJBYBKClTlqFlA7X6A+a7tgxMfQ= | gcloud secrets versions add verified-identifiers-aes-key --data-file=- --project=taxasge-dev

# Create HMAC key
gcloud secrets create verified-identifiers-hmac-key ^
  --project=taxasge-dev ^
  --replication-policy="automatic"

# Add secret value
echo N2x5qY5TryRvMxOMoEHNNhVqD0kBCecyxtSD17jW2tA= | gcloud secrets versions add verified-identifiers-hmac-key --data-file=- --project=taxasge-dev
```

### 2. Grant Access to Cloud Run Service Account

```powershell
# Grant access to the backend service account
gcloud secrets add-iam-policy-binding verified-identifiers-aes-key ^
  --member="serviceAccount:taxasge-dev@appspot.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor" ^
  --project=taxasge-dev

gcloud secrets add-iam-policy-binding verified-identifiers-hmac-key ^
  --member="serviceAccount:taxasge-dev@appspot.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor" ^
  --project=taxasge-dev
```

### 3. Verify Secrets Created

```powershell
# List secrets
gcloud secrets list --project=taxasge-dev --filter="name:verified-identifiers"

# Verify secret values (optional - for testing only)
gcloud secrets versions access latest --secret=verified-identifiers-aes-key --project=taxasge-dev
gcloud secrets versions access latest --secret=verified-identifiers-hmac-key --project=taxasge-dev
```

---

## Local Development (.env)

For local development, these values are already configured in `packages/backend/.env`:

```env
VERIFIED_IDENTIFIERS_AES_KEY=wBQJnpSZbYQvhdVpPJBYBKClTlqFlA7X6A+a7tgxMfQ=
VERIFIED_IDENTIFIERS_HMAC_KEY=N2x5qY5TryRvMxOMoEHNNhVqD0kBCecyxtSD17jW2tA=
```

---

## Via Google Cloud Console (Alternative)

1. Go to: https://console.cloud.google.com/security/secret-manager?project=taxasge-dev
2. Click **"Create Secret"**
3. Fill in:
   - **Name**: `verified-identifiers-aes-key`
   - **Secret value**: `wBQJnpSZbYQvhdVpPJBYBKClTlqFlA7X6A+a7tgxMfQ=`
4. Click **"Create Secret"**
5. Repeat for `verified-identifiers-hmac-key`

### Grant Permissions via Console:
1. Click on each secret
2. Go to **"Permissions"** tab
3. Click **"Grant Access"**
4. Add principal: `taxasge-dev@appspot.gserviceaccount.com`
5. Role: **Secret Manager Secret Accessor**

---

## Security Notes

- Keys are 256-bit (32 bytes) cryptographically secure random values
- AES key is used for AES-256-GCM authenticated encryption
- HMAC key is used for blind index (searchable encryption without decryption)
- Never commit these values to git (they are in .env which is gitignored)
- Rotate keys periodically (add new version, update `encryption_key_version` column)
