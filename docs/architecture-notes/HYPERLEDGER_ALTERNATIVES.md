# Note technique — Alternatives à Hyperledger Fabric pour l'audit chain immuable

> **Livrable D2** du plan `TREASURY_CAPABILITIES_UPGRADE_PLAN.md`
> **Date** : 2026-05-10
> **Audience** : tech-leads, security-auditors, sales avant-vente, bailleurs internationaux (BAD, BM, AFD), commanditaires gouvernementaux
> **Objectif** : démontrer chiffres à l'appui que **Hyperledger Fabric n'est pas la seule option** pour atteindre l'objectif fonctionnel d'immuabilité d'un journal d'audit gouvernemental, et qu'une alternative basée sur **PostgreSQL hash chain + Trillian + Sigstore Rekor** offre un TCO 5 ans **5-10x moindre** pour 95 % de la valeur.

---

## 1. Contexte

Plusieurs TDR récents (PIMEPE Guinée Équatoriale, équivalents CEMAC) demandent **Hyperledger Fabric** comme référence implicite pour la traçabilité immuable. Cette demande est souvent un copier-coller de bonnes pratiques internationales sans analyse coût/bénéfice spécifique au cas d'usage. Ce document examine les alternatives techniques équivalentes.

## 2. Cas d'usage typique : journal d'audit gouvernemental

**Caractéristiques** :
- 3-5 autorités collaboratives (Ministère des Finances, Trésor public, Cour des comptes, Cour suprême, Inspection générale)
- **Pas adverses** : autorités co-signataires de bonne foi (vs. consortium blockchain où parties peuvent avoir intérêts opposés)
- Volume : 100k-10M opérations / an
- Lecture publique souhaitée pour transparence citoyenne
- Audit externe semestriel/annuel

**Ce qui n'est PAS le cas d'usage** :
- ❌ Smart contracts complexes multi-parties (contrats supply chain, escrow)
- ❌ Tokens / monnaie programmable
- ❌ Parties potentiellement adverses (consortium banques concurrentes)
- ❌ Décentralisation publique permissionless

**Conclusion** : le cas d'usage est un **append-only log avec co-signature multi-autorité** + **transparence publique vérifiable**. Pas une vraie blockchain au sens DLT.

## 3. Comparaison des architectures

### Option 1 : Hyperledger Fabric (référence du TDR)

**Architecture** :
- 3+ peer nodes par autorité
- 1+ orderer node RAFT (3 minimum pour HA)
- Fabric CA pour gestion certificats
- Chaincodes en Go/Node/Java pour smart contracts
- World state CouchDB ou LevelDB
- Channel privé entre les 3 autorités

**Avantages** :
- ✅ Vraie DLT distribuée
- ✅ Smart contracts Turing-complets
- ✅ Reconnu par auditeurs financiers internationaux
- ✅ Communauté large

**Inconvénients** :
- ❌ Complexité opérationnelle élevée (Kubernetes + ops 24/7)
- ❌ Compétences rares (Go chaincode + Fabric CA + endorsement policies)
- ❌ Performance limitée (~3000 tps theoretical, beaucoup moins en pratique)
- ❌ Pas de transparency log public natif (channel privé)

### Option 2 : Hash chain Postgres + co-signature + Sigstore Rekor (proposé)

**Architecture** :
- Table `audit_chain` PostgreSQL avec colonnes `prev_hash`, `payload_hash`, `curr_hash` SHA-512
- Trigger PostgreSQL avant insert pour validation cohérence chaîne
- Cron daily : compute Merkle root → table `audit_chain_anchors`
- Co-signature détachée Ed25519/RSA-PSS par 3 autorités
- Cron weekly : push Merkle root signé vers **Sigstore Rekor** (transparency log Google, gratuit)
- Optionnel : ancrage **OpenTimestamps** (Bitcoin OP_RETURN, gratuit, ~1 sem latence)

**Avantages** :
- ✅ Utilise infra existante (PostgreSQL déjà déployé)
- ✅ Compétences disponibles localement (DBA + dev backend)
- ✅ Performance excellente (100k+ ops/sec)
- ✅ Transparency log public natif via Rekor
- ✅ Vérifiable hors-ligne par tout auditeur
- ✅ TCO 5-10x moindre (cf. §4)

**Inconvénients** :
- ❌ « Pas de blockchain » (perception marketing)
- ❌ Smart contracts en triggers PostgreSQL (moins lisibles que chaincode Go)
- ❌ Si les 3 autorités collusionnent ET modifient Rekor (improbable), théorie de tampering existe

### Option 3 : Trillian seul (Google CT-style)

**Architecture** :
- Trillian (open-source Google, Apache 2.0) déployé Docker
- Personality `audit_personality` qui forwarde events
- Inclusion proofs cryptographiques par event
- Pas de co-signature multi-autorité par défaut

**Avantages** :
- ✅ Mature (utilisé par Certificate Transparency, gravita publique)
- ✅ Inclusion proofs cryptographiques solides
- ✅ Performance excellente

**Inconvénients** :
- ❌ Pas de smart contracts
- ❌ Co-signature multi-autorité à coder par-dessus

### Option 4 : Hyperledger Besu (EVM compatible)

**Architecture** :
- Hyperledger Besu (Apache 2.0) en mode private network QBFT/IBFT
- Smart contracts Solidity (écosystème Ethereum)
- 3+ validators (un par autorité)

**Avantages** :
- ✅ EVM standard (écosystème mature)
- ✅ Plus léger que Fabric
- ✅ Compétences Solidity plus disponibles que Fabric chaincode

**Inconvénients** :
- ❌ Toujours 60-70 % de la complexité ops Fabric
- ❌ Performance moyenne (~100 tps)

## 4. TCO 5 ans chiffré

### Hyperledger Fabric (Option 1)

| Poste | An 1 | An 2-5 / an | Total 5 ans |
|---|---|---|---|
| Licences | 0 € | 0 € | 0 € |
| Infra cloud (5 VMs Standard, GCP/AWS) | 18 k€ | 12 k€ | 66 k€ |
| DevOps blockchain (1 ETP dédié) | 100 k€ | 100 k€ | 500 k€ |
| Formation initiale | 50 k€ | 0 € | 50 k€ |
| Audit sécurité chaincode (annuel) | 50 k€ | 50 k€ | 250 k€ |
| Outillage monitoring (Hyperledger Explorer + SIEM) | 30 k€ | 5 k€ | 50 k€ |
| Upgrades trimestriels (effort) | 20 k€ | 20 k€ | 100 k€ |
| **TOTAL** | **268 k€** | **187 k€** | **1 016 k€** |

> Variabilité ±30 % selon contexte → fourchette **670-950 k€**.

### Hash chain Postgres + Trillian + Rekor (Option 2)

| Poste | An 1 | An 2-5 / an | Total 5 ans |
|---|---|---|---|
| Licences | 0 € | 0 € | 0 € |
| Infra (PostgreSQL existant + 1 VM Trillian) | 2 k€ | 1.5 k€ | 8 k€ |
| Dev initial (5-8j) | 8 k€ | 0 € | 8 k€ |
| Ops (DBA habituel partagé) | 0 € | 0 € | 0 € |
| TSA RFC 3161 externe (DigiCert) | 3 k€ | 3 k€ | 15 k€ |
| Sigstore Rekor | 0 € | 0 € | 0 € |
| OpenTimestamps backup | 0 € | 0 € | 0 € |
| Audit annuel intégrité (1j) | 1 k€ | 1 k€ | 5 k€ |
| Formation équipe (2j) | 5 k€ | 0 € | 5 k€ |
| Upgrades (mineurs) | 2 k€ | 2 k€ | 10 k€ |
| **TOTAL** | **21 k€** | **7.5 k€** | **51 k€** |

> Variabilité ±50 % selon contexte → fourchette **40-95 k€**.

### Économie nette sur 5 ans

**Économie Option 2 vs Option 1** : 670-950 k€ - 40-95 k€ = **575-910 k€ économisés**.

À cette économie s'ajoutent :
- Pas besoin de recruter ETP DevOps blockchain (rare dans pays émergents)
- Performance 30x supérieure (100k vs 3k tps)
- Transparency log public natif via Rekor

## 5. Comparaison fonctionnelle (équivalence ?)

| Critère | Fabric | Postgres+Trillian+Rekor | Verdict |
|---|---|---|---|
| Immuabilité cryptographique | ✅ (consensus + signatures) | ✅ (hash chain + Merkle + co-sigs) | **Équivalent** |
| Co-validation multi-autorité | ✅ (endorsement policy chaincode) | ✅ (signatures détachées Ed25519) | **Équivalent** |
| Smart contracts | ✅ (chaincode Go/JS) | ✅ (PL/pgSQL ou FastAPI services) | Équivalent fonctionnel ; Fabric plus expressif |
| Transparence publique | 🟡 (channel privé) | ✅ (Rekor + OTS) | **Avantage Postgres** |
| Vérification hors-ligne par auditeur | 🟡 (nécessite peer node) | ✅ (juste vérifier hash chain + sigs) | **Avantage Postgres** |
| Tolérance défaillance autorité | ✅ (RAFT 1/3 OK) | ✅ (quorum 2/3 dégradé) | **Équivalent** |
| Performance (tps) | ~3 000 | 100 000+ | **Avantage Postgres** (30x) |
| Latence insertion | 1-2 s | < 50 ms | **Avantage Postgres** (40x) |
| Resistance tampering rétroactif | ✅ | ✅ (avec Rekor anchor public) | **Équivalent** |
| Compétences requises | ❌ rares | ✅ standard | **Avantage Postgres** |
| Outillage existant SIEM | 🟡 spécifique | ✅ standard PostgreSQL | **Avantage Postgres** |
| Recovery après incident | Complexe | Standard PG (PITR) | **Avantage Postgres** |

**Verdict** : équivalence fonctionnelle complète pour le cas d'usage gouvernemental. Hyperledger Fabric n'apporte **aucune valeur additionnelle** dans ce contexte spécifique.

## 6. Argumentaire pour bailleurs / commanditaires

### Pour les bailleurs internationaux (BAD, BM, AFD, UE)

> *« Les TDR récents demandent Hyperledger Fabric par référence aux bonnes pratiques internationales. Cependant, l'analyse coût/bénéfice montre que pour le cas d'usage spécifique d'un journal d'audit gouvernemental — où les autorités co-signataires sont collaboratives et de bonne foi, et où la valeur cible est l'immuabilité auditable + transparence publique — une architecture basée sur PostgreSQL hash chain co-signée et ancrée dans un transparency log public (Sigstore Rekor) offre la **même garantie cryptographique d'immuabilité** à un coût total de possession **10x moindre**, avec des compétences disponibles localement, et une performance 30x supérieure. Cette approche évite la dette opérationnelle blockchain dans des contextes où les compétences DevOps Hyperledger sont rares et coûteuses. »*

### Pour les commanditaires gouvernementaux

> *« Hyperledger Fabric a été conçu pour des consortiums multi-organisations potentiellement adverses (ex : banques concurrentes, supply chain multi-tier) avec smart contracts complexes (ex : KYC partagé, escrow). Pour un journal d'audit d'un Trésor public avec 3 autorités étatiques co-signataires, une chaîne de hash PostgreSQL co-signée et ancrée publiquement offre la même garantie d'immuabilité, à un coût total 10x moindre, avec des compétences déjà disponibles dans votre administration (DBA + dev backend), et une performance 30x supérieure. La traçabilité publique via Sigstore Rekor renforce de plus la transparence citoyenne. »*

## 7. Patterns de migration (si Hyperledger imposé plus tard)

Si malgré tout le commanditaire impose Hyperledger Fabric en V2, la migration depuis l'audit chain PostgreSQL est triviale :

1. Hash chain Postgres reste source of truth pour les blocs historiques (read-only)
2. Nouveau adapter `HyperledgerAdapter` réplique blocs futurs vers Fabric
3. Documents historiques restent vérifiables via Rekor anchor
4. Fabric devient un secondary index pour audit, pas le primary store

→ **Migration sans rupture, en 1-2 sprints**.

## 8. Conclusion et recommandation

**Recommandation tech-lead** : pour tous les TDR treasury / payment gov dans pays émergents avec contraintes opérationnelles fortes (compétences locales limitées, budget contraint), **proposer l'option 2 (Postgres + Trillian + Rekor)** comme architecture de référence, accompagnée d'un argumentaire chiffré (ce document).

**Si le commanditaire refuse** : proposer **option 4 (Hyperledger Besu EVM)** comme compromis (plus léger que Fabric, écosystème mature, ~60 % du coût Fabric).

**À éviter** : céder par défaut à Hyperledger Fabric sans argumentaire, ce qui crée une dette opérationnelle de 670 k€-1 M€ sur 5 ans pour aucune valeur additionnelle dans ce cas d'usage.

---

*Document à dupliquer dans la réponse au TDR pour démontrer la maîtrise du sujet et la rationalité du choix architectural.*
