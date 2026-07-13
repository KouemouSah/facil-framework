#!/usr/bin/env python3
"""Garde-NetworkPolicy PARSEE (SEC-012) sur le rendu `helm template`.

Aujourd'hui, sans NetworkPolicy, Postgres/Redis/MinIO/OpenBao sont des Service
ClusterIP joignables par N'IMPORTE QUEL pod du cluster (k3s embarque kube-router,
donc les NetworkPolicy sont REELLEMENT appliquees -- contrairement a un cluster
flannel nu ou elles seraient silencieusement ignorees). Un conteneur compromis
suffit a atteindre tout le data-plane.

Un `grep -q "kind: NetworkPolicy"` ne prouve RIEN sur le ciblage : une policy au
`podSelector` mal ecrit (typo, cle renommee par une regression du helper
`facil.selectorLabels`) ne protege rien tout en ayant l'air correcte -- ou pire,
coupe la stack si elle cible le mauvais composant. Ce parseur verifie, comme
guard_secrets.py / guard_resources.py (meme convention, DRY), des invariants
STRUCTURELS sur TOUTES les NetworkPolicy du rendu :

  1. Exactement une policy "default-deny" (podSelector: {}), et son
     policyTypes est [Ingress] SEULEMENT (jamais Egress -- un default-deny
     egress casserait la resolution DNS vers kube-dns dans kube-system, qui
     est hors du namespace de la release). Durcissement PARTIEL assume :
     l'egress reste ouvert.
  2. Aucune policy du chart ne porte Egress dans policyTypes.
  3. Invariant central : tout podSelector (cible OU peer dans
     `ingress[].from[].podSelector`) DOIT matcher AU MOINS UN pod-template
     REELLEMENT rendu (Deployment/StatefulSet/Job). Verifie au niveau du
     SELECTEUR (pas valeur par valeur d'un `matchExpressions.values` OR-list) :
     un `matchLabels` a valeur unique qui ne matche aucun pod est TOUJOURS
     entierement inerte (le cas de mutation demande par le brief : renommer un
     `facil.component` en une valeur inexistante). Un `matchExpressions/In`
     partiellement invalide (ex. `openbao` absent parce que
     `openbao.enabled=false`) n'est PAS flag ici : c'est une configuration
     legitime (composant desactive), pas un typo -- flag-per-valeur produirait
     un faux-positif a chaque composant optionnel eteint. Les paires precises
     requises (ex. "les datastores acceptent bien backend+db-init+db-role")
     sont verifiees par des assertions dediees dans test_guard_networkpolicy.py
     (`test_datastores_policy_allows_migration_jobs`), qui restent sensibles a
     un typo sur UNE valeur precise de la liste -- complementaire de ce guard.

Usage : helm template ... | python guard_networkpolicy.py
Exit 0 = propre, 1 = policy(ies) inertes ou mal formees.
"""
from __future__ import annotations

import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "Job"}
COMPONENT_LABEL = "facil.component"


def _load_docs(stream: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(stream) if isinstance(d, dict)]


def iter_observed_components(docs: list[dict]) -> set[str]:
    """Ensemble des `facil.component` REELLEMENT portes par un pod-template du rendu."""
    observed: set[str] = set()
    for doc in docs:
        if doc.get("kind") not in WORKLOAD_KINDS:
            continue
        pod_meta = (((doc.get("spec") or {}).get("template") or {}).get("metadata")) or {}
        labels = pod_meta.get("labels") or {}
        comp = labels.get(COMPONENT_LABEL)
        if comp:
            observed.add(comp)
    return observed


def iter_networkpolicies(docs: list[dict]) -> list[dict]:
    return [d for d in docs if d.get("kind") == "NetworkPolicy"]


def selector_components(selector: dict) -> set[str]:
    """Toutes les valeurs `facil.component` referencees par un podSelector,
    que ce soit via `matchLabels` ou `matchExpressions` (operator `In`)."""
    if not selector:
        return set()
    values: set[str] = set()
    match_labels = selector.get("matchLabels") or {}
    if COMPONENT_LABEL in match_labels:
        values.add(match_labels[COMPONENT_LABEL])
    for expr in (selector.get("matchExpressions") or []):
        if expr.get("key") == COMPONENT_LABEL and expr.get("operator") == "In":
            values |= set(expr.get("values") or [])
    return values


def check(stream: str) -> list[str]:
    docs = _load_docs(stream)
    observed = iter_observed_components(docs)
    policies = iter_networkpolicies(docs)

    problems: list[str] = []

    if not policies:
        problems.append("aucune NetworkPolicy trouvee dans le rendu (networkPolicy.enabled ?).")
        return problems

    deny_all = [p for p in policies if (p.get("spec") or {}).get("podSelector") == {}]
    if len(deny_all) == 0:
        problems.append(
            "aucune policy default-deny (podSelector: {}) trouvee -- le namespace "
            "n'a pas de deny-by-default sur l'ingress.")
    elif len(deny_all) > 1:
        names = [((p.get("metadata") or {}).get("name")) for p in deny_all]
        problems.append(f"plusieurs policies default-deny trouvees (attendu 1) : {names}")
    else:
        deny_types = (deny_all[0].get("spec") or {}).get("policyTypes") or []
        if deny_types != ["Ingress"]:
            name = (deny_all[0].get("metadata") or {}).get("name", "?")
            problems.append(
                f"{name}: policy default-deny a policyTypes={deny_types} -- attendu "
                f"exactement [Ingress] (Egress casserait le DNS vers kube-dns).")

    for pol in policies:
        name = (pol.get("metadata") or {}).get("name", "?")
        spec = pol.get("spec") or {}
        policy_types = spec.get("policyTypes") or []

        if "Egress" in policy_types:
            problems.append(
                f"{name}: policyTypes inclut Egress -- un default-deny egress "
                f"casserait la resolution DNS (kube-dns vit dans kube-system, "
                f"hors du namespace de la release). Le brief ne pose du deny que "
                f"sur l'ingress ; l'egress doit rester ouvert.")

        pod_selector = spec.get("podSelector")
        if pod_selector == {} or pod_selector is None:
            continue  # default-deny (tous les pods) -- deja verifie ci-dessus

        targets = selector_components(pod_selector)
        if not targets:
            problems.append(
                f"{name}: podSelector ne reference aucun `{COMPONENT_LABEL}` -- "
                f"ciblage non verifiable, potentiellement trop large ou inerte.")
        elif not (targets & observed):
            problems.append(
                f"{name}: podSelector cible {COMPONENT_LABEL} in {sorted(targets)} "
                f"mais AUCUNE de ces valeurs ne matche un pod-template du rendu -- "
                f"policy entierement INERTE (ne s'applique a aucun pod).")

        for rule in (spec.get("ingress") or []):
            for frm in (rule.get("from") or []):
                peer_selector = frm.get("podSelector")
                if peer_selector is None:
                    continue  # namespaceSelector (ex. kube-system/Traefik) -- hors scope de ce guard
                peers = selector_components(peer_selector)
                if not peers:
                    problems.append(
                        f"{name}: une regle ingress.from a un podSelector sans "
                        f"`{COMPONENT_LABEL}` -- ciblage non verifiable.")
                elif not (peers & observed):
                    problems.append(
                        f"{name}: ingress.from cible {COMPONENT_LABEL} in "
                        f"{sorted(peers)} mais AUCUNE de ces valeurs ne matche un "
                        f"pod-template du rendu -- regle d'autorisation entierement "
                        f"INERTE (n'autorise personne).")

    return problems


if __name__ == "__main__":
    found = check(sys.stdin.read())
    if found:
        print("FAIL garde-networkpolicy (SEC-012) :", file=sys.stderr)
        for p in found:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)
    print("OK garde-networkpolicy (SEC-012)")
