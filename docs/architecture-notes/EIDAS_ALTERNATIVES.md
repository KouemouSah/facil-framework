# Note technique — Alternatives à l'AC qualifiée eIDAS pour pays sans TSP national

> **Livrable D3** du plan `TREASURY_CAPABILITIES_UPGRADE_PLAN.md`
> **Date** : 2026-05-10
> **Audience** : tech-leads, security-auditors, sales avant-vente, commanditaires gouvernementaux (Afrique sub-saharienne, CEMAC, UEMOA, OHADA)
> **Objectif** : proposer un schéma phasé pragmatique pour des pays qui exigent « conformité eIDAS » dans leurs TDR mais n'ont pas d'autorité de certification (AC) qualifiée nationale ni de Trust Service Provider (TSP) accrédité.

---

## 1. Contexte

eIDAS (UE) impose qu'une signature qualifiée soit émise par un TSP qualifié inscrit dans la **Trusted List** européenne. Plusieurs pays hors UE (Afrique sub-saharienne notamment) **citent eIDAS dans leurs TDR** comme référence de conformité, mais :
- Ces pays **n'ont pas d'AC qualifiée nationale** (parfois pas d'AC du tout)
- **eIDAS ne s'applique pas juridiquement** hors UE
- La **transposition nationale** des règles e-signature est souvent partielle ou inexistante
- Les commanditaires demandent quand même « équivalence eIDAS »

Ce document propose un schéma **3 phases** réaliste pour répondre à cette demande.

## 2. Constat technique

### 2.1 Acquérir un certificat eIDAS qualifié hors UE

**En théorie possible** via un TSP UE :
- **FNMT-RCM** (Espagne, étatique) — politiquement aligné si pays hispanophone (Guinée Équatoriale, Sahara) + accords bilatéraux
- **Camerfirma**, **Uanataca**, **Logalty**, **Evicertia** (Espagne, privés)
- **Certigna**, **Universign**, **ChamberSign** (France) — Afrique francophone
- **D-Trust**, **Bundesdruckerei** (Allemagne)

**Limites pratiques** :
- Coût : 200-500 €/cert/an × N agents (rapide à monter en coût)
- Délai d'émission : 1-2 mois pour un compte corporate étranger
- **Reconnaissance juridique nationale** : non garantie par défaut → convention bilatérale à négocier
- Procédure d'identification face-to-face (KYC strict eIDAS) → délégation possible via consulat ou notaire local

### 2.2 Adobe Approved Trust List (AATL) comme alternative pragmatique

L'AATL est une liste maintenue par Adobe Inc. : tout document signé par un certificat émis par une AC sur AATL est **automatiquement reconnu valide** par tous les Adobe Acrobat Reader du monde sans configuration utilisateur.

**ACs notables sur AATL** :
- **DigiCert** — leader mondial, Afrique-friendly
- **GlobalSign** — large couverture
- **Sectigo** (ex-Comodo) — bon rapport qualité/prix
- **Entrust** — qualité enterprise
- **IdenTrust**, **Buypass**, **Carillon Federal Services**, etc.

**Avantages** :
- ✅ Reconnu par 99 % des utilisateurs finaux (Adobe Reader = standard de fait)
- ✅ Pas besoin de TSP national
- ✅ Émission rapide (1-2 semaines)
- ✅ Coût modéré (200-400 €/cert/an)

**Limites** :
- ❌ Pas eIDAS qualifié au sens strict (signature avancée, pas qualifiée)
- ❌ Pas de présomption légale eIDAS (mais reconnu mondialement via Adobe + jurisprudence variée)
- ❌ Adobe est une entreprise privée — risque de dépendance

### 2.3 AC nationale auto-construite

Construire une AC nationale propriétaire avec OpenSSL/EJBCA/CFSSL.

**Avantages** :
- ✅ Souveraineté totale
- ✅ Coût récurrent faible
- ✅ Pas de dépendance étrangère

**Limites** :
- ❌ Pas reconnu par défaut (utilisateurs doivent installer la racine manuellement)
- ❌ Audit ETSI EN 319 411 nécessaire pour qualification : 12-18 mois + budget conseil 80-150 k€
- ❌ Compétences crypto rares dans pays émergents

## 3. Schéma phasé recommandé

### Phase 1 — MVP (mois 1-6) : Adobe AATL via DigiCert/GlobalSign

**Stack** :
- Achat certificats AATL via DigiCert (ou GlobalSign / Sectigo / Entrust)
- Quantité : 10-50 certificats agents critiques
- Type : Document Signing Certificate (Class 3)
- Coût estimé : ~3-15 k€/an

**Use case** :
- Signature PAdES des documents officiels (reçus, attestations, certificats)
- Signature reconnue automatiquement par Adobe Reader (badge « Signed and certified by ___ »)
- Accepté pour 99 % des usages administratifs réels

**Effort intégration Facil** :
- 0 jour additionnel : Phase N.5 du roadmap Facil intègre déjà des providers AATL
- Configuration via Studio UI (provider + cert path + chain)

**Avantage stratégique** :
- Permet de répondre IMMÉDIATEMENT à un TDR demandant « signature reconnue internationalement »
- Évite le retard d'attente d'une AC nationale

### Phase 2 — Production (mois 7-18) : AC nationale auto-construite

**Stack** :
- AC racine (root CA) avec clé privée stockée HSM (YubiHSM 2 à 650 € pour MVP, Thales Luna SA pour prod sérieuse 30 k€)
- 2-3 ACs intermédiaires (intermediate CAs) par direction
- Politique de certification (CP/CPS) rédigée selon ETSI EN 319 411
- Procédures opérationnelles (RA = Registration Authority) documentées
- Conservation TSA externe (DigiCert TSA, FreeTSA dev) pour horodatage RFC 3161

**Coût estimé** :
- Initial : 30-100 k€ (HSM + audit + dev)
- Récurrent : ~20 k€/an (ops + audit annuel intégrité)

**Avantage** :
- Souveraineté progressive
- Émission illimitée certificats nationaux
- Préparation à la qualification ETSI

**Limite** :
- Toujours pas qualifié eIDAS (manque audit ETSI formel)
- Utilisateurs doivent installer racine nationale dans leur OS / Adobe Reader

### Phase 3 — Long terme (an 2-3) : Audit ETSI + reconnaissance régionale

**Action** :
- Audit ETSI EN 319 411 par cabinet certifié (LSTI, TÜV, KPMG, etc.)
- Coût : 80-150 k€ pour audit initial + 30-50 k€/an récurrent
- Délai : 12-18 mois
- Sortie : qualification du TSP national
- Partenariat technique avec FNMT-RCM (Espagne) ou ANSSI (France) pour transfert de savoir-faire

**Reconnaissance régionale CEMAC / UEMOA / OHADA** :
- Travail diplomatique : convention bilatérale ou multilatérale entre pays de la région
- Mise en place d'une **Trusted List** régionale (équivalent eIDAS)
- À terme : reconnaissance par UE via accord bilatéral (modèle Suisse-UE)

## 4. Comparaison synthétique

| Critère | Phase 1 AATL | Phase 2 AC nationale | Phase 3 ETSI qualifié |
|---|---|---|---|
| Délai opérationnel | 1-2 sem | 6-12 mois | 12-18 mois |
| Coût initial | 0-5 k€ | 30-100 k€ | 100-200 k€ |
| Coût annuel | 3-15 k€ | 20 k€ | 50-80 k€ |
| Reconnaissance internationale | ✅ (Adobe) | 🟡 (national + manuel) | ✅ (eIDAS-equivalent régional) |
| Souveraineté | ❌ (Adobe + AC US/EU) | ✅ | ✅ |
| Valeur juridique nationale | 🟡 (à clarifier loi) | ✅ (avec décret) | ✅ |
| Compétences requises | Faible | Élevée | Très élevée |
| Adapté pour TDR urgent | ✅ | ❌ | ❌ |

## 5. Argumentaire pour TDR

### Texte type à insérer dans une réponse au TDR

> *« La conformité eIDAS au sens strict suppose l'existence d'un Trust Service Provider qualifié national, ce qui n'est pas le cas en [pays]. Pour répondre à l'exigence de "signature numérique qualifiée reconnue internationalement", nous proposons un schéma phasé :*
>
> *• **Phase 1 (mois 1-6)** : signature PAdES via une autorité de certification membre de l'**Adobe Approved Trust List (AATL)** — fournisseur recommandé : DigiCert ou GlobalSign. Cette approche garantit la reconnaissance automatique des documents signés par 99 % des utilisateurs finaux dans le monde (via Adobe Acrobat Reader, standard de fait), tout en étant conforme à la norme PAdES (PDF Advanced Electronic Signatures, ISO 32000) demandée dans le TDR. Coût opérationnel ~3-15 k€/an.*
>
> *• **Phase 2 (mois 7-18)** : construction d'une **autorité de certification nationale** propriétaire avec stockage HSM, politique de certification rédigée selon ETSI EN 319 411, conservant un horodatage TSA externe RFC 3161. Souveraineté progressive sur l'émission de certificats nationaux. Coût initial 30-100 k€, récurrent ~20 k€/an.*
>
> *• **Phase 3 (année 2-3)** : audit ETSI formel et qualification du TSP national, ouvrant la voie à une reconnaissance qualifiée régionale (CEMAC/UEMOA/OHADA) avec une Trusted List régionale. Coût 100-200 k€ initial.*
>
> *Cette approche permet de répondre immédiatement aux exigences fonctionnelles du TDR (signature qualifiée reconnue, horodatage TSA, validation OCSP) sans bloquer le projet sur le délai d'établissement d'une AC nationale qualifiée eIDAS, tout en bâtissant la souveraineté progressive du pays. »*

## 6. Recommandations par contexte

### Contexte A — TDR avec délai serré (10-12 mois) et budget limité

→ **Phase 1 seule (AATL DigiCert)**
→ Documenter la trajectoire vers Phase 2/3 dans la réponse pour rassurer le commanditaire

### Contexte B — TDR avec budget confortable et politique de souveraineté forte

→ **Phase 1 + Phase 2 en parallèle (mois 1-18)**
→ AATL pour démarrage immédiat, AC nationale construite progressivement
→ Doc Studio UI pour basculer providers sans interruption

### Contexte C — Programme régional (CEMAC, UEMOA, OHADA)

→ **Phases 1 + 2 + démarrage Phase 3**
→ Coordination avec autres pays de la région
→ Partenariat technique TSP UE (FNMT, ANSSI, BSI)

### Contexte D — Pays avec AC nationale existante mais non qualifiée

→ **Phase 2 directe + AATL en backup pour usages internationaux**
→ Audit ETSI en Phase 3

## 7. Risques et mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Commanditaire refuse AATL « pas vraiment eIDAS » | Medium | High | Argumentaire §5 + démonstration Adobe Reader + jurisprudence |
| R2 | Adobe modifie unilatéralement liste AATL | Low | High | Multi-providers AATL + plan migration AC nationale |
| R3 | Délai HSM (importation) bloque Phase 2 | Medium | Medium | Démarrer Phase 2 avec soft HSM (BoringSSL), migrer HW HSM dès dispo |
| R4 | Audit ETSI échoue (ré-audit) | Low | Medium | Cabinet conseil pré-audit + remediation cycle |
| R5 | Régulation nationale change en cours | Medium | Medium | Veille juridique + adaptabilité contractuelle |

## 8. Conclusion

Pour un pays sans TSP national ni AC qualifiée existante, **viser directement eIDAS qualifié dans un projet < 18 mois est irréaliste**. La trajectoire pragmatique est :

1. **AATL DigiCert/GlobalSign en MVP** (1-2 semaines, 3-15 k€/an)
2. **AC nationale auto-construite progressivement** (6-12 mois, 30-100 k€)
3. **Qualification ETSI à terme** (12-18 mois, 100-200 k€)

Cette approche permet de répondre à 99 % des usages administratifs réels dès le mois 1, tout en bâtissant la souveraineté progressive. Elle évite l'écueil de bloquer un projet treasury sur l'absence d'écosystème PKI national mature.

---

*Document à dupliquer dans la réponse au TDR pour démontrer la maîtrise du sujet eIDAS et proposer une voie pragmatique au commanditaire.*
