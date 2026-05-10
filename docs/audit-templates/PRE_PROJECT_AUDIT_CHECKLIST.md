# Audit pré-projet — Checklist pour TDR Treasury / Government Payment Portal

> **Livrable D1** du plan `TREASURY_CAPABILITIES_UPGRADE_PLAN.md`
> **Date** : 2026-05-10
> **Scope** : checklist structuré à compléter AVANT de chiffrer une réponse à un TDR type PIMEPE (Trésor public / portail paiement État) pour cadrer les inconnues techniques et organisationnelles.
> **Format** : à dupliquer pour chaque pays/projet, à compléter sur le terrain.

---

## 1. Comment utiliser cette checklist

- À chaque appel d'offres treasury/payment gov, dupliquer ce fichier dans le repo projet
- À compléter par l'équipe avant-vente / tech-lead lors des **réunions de cadrage** avec le bénéficiaire
- Chaque section a des **questions précises** + **artefacts requis** (captures, exports, accès lecture)
- Les sections marquées 🔴 sont **bloquantes** : impossible de chiffrer sans réponse
- Sections 🟡 = à compléter idéalement, sinon documenter l'hypothèse retenue
- Sections 🟢 = nice-to-have

---

## 2. Audit ERP cible 🔴

### 2.1 ERP installé (réponses obligatoires)

- [ ] Quel ERP est installé pour la comptabilité publique ? (Sage X3 / SAP S/4 HANA / Oracle EBS / Odoo / autre)
- [ ] Version exacte et patch level (ex : Sage X3 v12 patch 9)
- [ ] Date dernière mise à jour majeure
- [ ] L'ERP est-il déjà acquis ou à acquérir dans le périmètre du marché ?

### 2.2 Modules actifs et utilisés

- [ ] Modules comptabilité publique activés (Comptabilité générale / Trésorerie / Immobilisations / Fournisseurs / Clients) ?
- [ ] Plan comptable de l'État (PCE) configuré ? Quelle version ? Codes effectivement utilisés (export en CSV) ?
- [ ] Workflows comptables existants (validation 4-yeux, contrôles internes) ?

### 2.3 APIs et intégration

- [ ] APIs REST exposées par l'ERP ? Liste documentée ? OpenAPI spec disponible ?
- [ ] APIs SOAP fallback ? WSDL disponible ?
- [ ] Authentification : OAuth 2.0 / API key / Basic / autre ?
- [ ] Limite de débit (rate limit) connue ?
- [ ] Sandbox / environnement de test accessible ? Procédure d'accès ?

### 2.4 Compétences locales

- [ ] Expert Sage X3 (ou autre ERP) certifié interne ? Sous-traitance ?
- [ ] Cabinet partenaire Sage présent dans le pays ou région ?
- [ ] Documentation technique en quelle langue (espagnol / français / anglais) ?

### 2.5 Artefacts à récupérer

- [ ] Capture d'écran : page version Sage X3
- [ ] Export PCE actuel : `SELECT * FROM gacctop` ou équivalent (CSV)
- [ ] Liste users + rôles administrateurs ERP
- [ ] OpenAPI spec ou WSDL à jour
- [ ] Politique de backup et reprise (RTO/RPO)

---

## 3. Audit banques partenaires 🔴

### 3.1 Liste banques (compléter par projet)

| Banque | Type | Statut activation | Volume mensuel transactions | Contact tech | Notes |
|---|---|---|---|---|---|
| BANGE | Étatique | Active | À renseigner | À renseigner | |
| Ecobank | Régional | À renseigner | À renseigner | À renseigner | |
| BGFI Bank | Régional | À renseigner | À renseigner | À renseigner | |
| CCEI Bank | Régional | À renseigner | À renseigner | À renseigner | |
| La Nationale | National | À renseigner | À renseigner | À renseigner | |
| BISA Bank | International | À renseigner | À renseigner | À renseigner | |
| SGGE | Filiale française | À renseigner | À renseigner | À renseigner | |
| _Autres_ | | | | | |

### 3.2 Maturité ISO 20022 (par banque)

Pour chaque banque :
- [ ] Banque supporte ISO 20022 pain.001 (émission virement) ? Version (`pain.001.001.xx`) ?
- [ ] Banque supporte ISO 20022 camt.053 (relevé) ? Version ?
- [ ] Banque supporte ISO 20022 camt.054 (notification temps réel) ?
- [ ] Webhook ingestion temps réel ou polling SFTP daily seul ?
- [ ] Format fallback (MT940 SWIFT / fichier propriétaire / paper / autre) ?
- [ ] Sandbox banque accessible ?

### 3.3 Authentification et sécurité

- [ ] mTLS supporté ? Procédure d'échange certificats ?
- [ ] Signature payload (XAdES sur pain.001) requise ?
- [ ] IP whitelisting requis ?
- [ ] HSM banque pour clés ?

### 3.4 Reconciliation

- [ ] La banque met-elle l'IUI (référence externe) dans le libellé du relevé ?
- [ ] Sinon, par quel champ identifier le payeur (IBAN + montant) ?
- [ ] Délai moyen entre virement émis et notification reçue ?

### 3.5 Mobile money et opérateurs télécoms

- [ ] Opérateurs MM disponibles dans le pays (GETESA, MUNI, MTN, Orange, autres) ?
- [ ] APIs publiques disponibles ? Documentation ? Sandbox ?
- [ ] Formats USSD / API REST / autre ?
- [ ] Délais de règlement (T+0 / T+1 / T+2) ?

### 3.6 Artefacts à récupérer

- [ ] Liste banques avec contacts tech et budget intégration estimé
- [ ] Schémas ISO 20022 supportés (par banque, par version)
- [ ] Comptes test sandbox (par banque)

---

## 4. Audit AD/LDAP/SSO entreprise 🔴

### 4.1 Annuaire existant

- [ ] Active Directory déployé ? Version (Windows Server XX) ?
- [ ] LDAP simple / SAMBA / autre ?
- [ ] Annuaire unifié pour les 5 directions générales ou silos par direction ?
- [ ] Nombre d'utilisateurs total (estimation) ?

### 4.2 Schéma et attributs

- [ ] Format `userPrincipalName` (email-like) ?
- [ ] Attributs métier (matricule, direction, sous-direction, fonction) ?
- [ ] Groupes utilisés pour RBAC actuellement ?

### 4.3 Authentification fédérée

- [ ] SSO existant (Keycloak, ADFS, Auth0, autre) ?
- [ ] SAML 2.0 / OIDC / WS-Federation supporté ?
- [ ] MFA déjà en place ? Quelle méthode (TOTP, SMS, smart card, biometrics) ?

### 4.4 Politique de sécurité

- [ ] Politique de mots de passe (longueur, rotation, complexité) ?
- [ ] Lockout après N tentatives ?
- [ ] Session timeout ?
- [ ] Audit log centralisé (SIEM) ?

### 4.5 Artefacts à récupérer

- [ ] Schema LDAP export (ldif)
- [ ] Documentation SSO / SAML / OIDC config si existant
- [ ] Liste groupes AD utilisés pour autorisation

---

## 5. Audit cadre légal e-signature 🔴

### 5.1 Législation pays

- [ ] Loi nationale sur les signatures électroniques ? Référence (numéro, date) ?
- [ ] Décrets d'application ? Références ?
- [ ] Distinction signature simple / avancée / qualifiée ?
- [ ] Valeur probante en justice : équivalente au manuscrit ou subordonnée ?

### 5.2 Autorité de certification (AC) nationale

- [ ] AC nationale qualifiée existe ? Nom, statut juridique ?
- [ ] AC accréditée eIDAS ou équivalent régional (CEMAC, UEMOA, OHADA) ?
- [ ] Cross-recognition avec eIDAS UE ?
- [ ] Procédure d'émission certificats (formulaires, délais, coûts) ?

### 5.3 TSP étrangers acceptables

- [ ] Si pas d'AC nationale, certificats étrangers acceptés ? Lesquels ?
- [ ] Convention bilatérale avec pays UE ou autres ?
- [ ] Adobe AATL accepté pour usages administratifs ?

### 5.4 Documents officiels

- [ ] Quels documents nécessitent signature qualifiée vs avancée ?
- [ ] Formats officiels (PDF/A-3, XML, etc.) ?
- [ ] Code QR / horodatage requis sur quels documents ?

### 5.5 Artefacts à récupérer

- [ ] Texte de loi e-signature
- [ ] Liste TSP autorisés
- [ ] Templates documents officiels en vigueur

---

## 6. Audit infrastructure cloud / on-prem 🟡

### 6.1 Hébergement

- [ ] Cloud public autorisé pour données publiques ? Quels providers (AWS, GCP, Azure, OVHcloud, autres) ?
- [ ] Cloud souverain national / régional disponible ?
- [ ] Données sensibles (NIF, montants taxes) doivent rester on-prem ?
- [ ] Réglementation localisation données (data residency) ?

### 6.2 Disponibilité et reprise

- [ ] RTO target (Recovery Time Objective) ?
- [ ] RPO target (Recovery Point Objective) ?
- [ ] DR site secondaire planifié ? Géographiquement où ?
- [ ] Tests DR réguliers ?

### 6.3 Connectivité

- [ ] Connexion internet datacenter (Mbps, latence vers UE/US) ?
- [ ] Redondance fournisseurs internet ?
- [ ] VPN inter-sites ?

### 6.4 Sécurité physique

- [ ] Datacenter conforme Tier II / III / IV ?
- [ ] Audit physique récent ?
- [ ] Accès biométrique ?

### 6.5 Artefacts à récupérer

- [ ] Schéma réseau actuel
- [ ] Politique DR / BCP
- [ ] Audit datacenter récent

---

## 7. Audit profils de compétences 🟢

### 7.1 Recrutement local

- [ ] Pool dev local taille estimée ?
- [ ] Compétences disponibles : FastAPI Python / Next.js React / DevOps Kubernetes / Crypto / Comptabilité publique ?
- [ ] Universités locales avec cursus IT ?
- [ ] Coûts journaliers moyens (junior / senior) ?

### 7.2 Sous-traitance régionale

- [ ] Cabinets partenaires Sage X3 / SAP / Oracle dans la région ?
- [ ] Cabinets sécurité / pentest agréés ?
- [ ] Experts comptabilité publique disponibles ?

### 7.3 International

- [ ] Visas dev expat possibles ? Délais et coûts ?
- [ ] Télétravail accepté pour devs internationaux ?
- [ ] Décalage horaire avec pays sources (UE = +1h, US = -5h) ?

---

## 8. Synthèse et go/no-go

À compléter après audit terrain :

| Section | Status | Bloquants identifiés | Décision |
|---|---|---|---|
| ERP | 🟢 / 🟡 / 🔴 | | |
| Banques | 🟢 / 🟡 / 🔴 | | |
| AD/SSO | 🟢 / 🟡 / 🔴 | | |
| Cadre légal | 🟢 / 🟡 / 🔴 | | |
| Infrastructure | 🟢 / 🟡 / 🔴 | | |
| Compétences | 🟢 / 🟡 / 🔴 | | |

**Décision globale** : ☐ Go (chiffrage possible) / ☐ Go conditionnel (clarifications requises) / ☐ No-go (bloquants critiques)

**Note libre** :
_______________________________________________________________

---

## 9. Recommandations à inscrire dans la réponse au TDR

Basé sur l'audit, les éléments suivants doivent figurer dans la réponse :

1. **Hypothèses techniques retenues** (ex : « ERP Sage X3 v12+ supposé, sinon SOAP fallback inclus avec surcoût X »)
2. **Clauses de partage de risque** (ex : « livraison adapter SIGREF conditionnée à API tiers livrée à T0+4M »)
3. **Plan phasé** si bloquants partiels (ex : « Phase 1 sans ISO 20022, Phase 2 après upgrade banques »)
4. **Budget infrastructure dédié** distinct du budget développement
5. **Conditions de réception** précises pour chaque module
6. **Plan de formation** avec budget conduite du changement (typiquement 30-40 % du budget projet)

---

*Fin de la checklist. À dupliquer pour chaque projet, à compléter sur le terrain, à archiver dans le dossier de réponse au TDR.*
