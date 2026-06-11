"""
Query Preprocessor — Normalize, expand, and extract entities from user queries.

Improves RAG recall by:
1. Normalizing accents for full-text search
2. Expanding abbreviations for better embedding
3. Extracting entities (cities, commerce types, workflows)
4. Rewriting queries for richer semantic embeddings

Usage:
    preprocessor = QueryPreprocessor()
    result = preprocessor.preprocess("cuanto cuesta el DNI en Malabo")
    # result.normalized → "cuanto cuesta el dni en malabo"
    # result.expanded → "cuanto cuesta el Documento Nacional de Identidad en Malabo Guinea Ecuatorial"
    # result.entities → {"city": "malabo", "zone_code": "A1", "workflow": "VERIFICACION"}
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional, List


@dataclass
class PreprocessedQuery:
    """Result of query preprocessing."""
    original: str
    normalized: str  # accent-stripped, lowered — for full-text search
    expanded: str  # abbreviations expanded — for embedding generation
    entities: Dict[str, str] = field(default_factory=dict)
    detected_intent_hints: List[str] = field(default_factory=list)


# Maps city names → commerce zone codes
CITY_ZONE_MAP = {
    'malabo': 'A1',
    'bata': 'A1',
    'ebebiyin': 'B1',
    'ebebiyín': 'B1',
    'evinayong': 'B1',
    'mongomo': 'B1',
    'luba': 'B1',
    'riaba': 'B1',
    'añisok': 'C1',
    'anisok': 'C1',
    'niefang': 'C1',
    'micomeseng': 'C1',
    'acurenam': 'C1',
    'nsork': 'C1',
    'mbini': 'C1',
    'kogo': 'C1',
    'annobon': 'C1',
    'corisco': 'C1',
}

# Maps commerce keywords → bundle codes
COMMERCE_KEYWORDS = {
    'restaurant': 'BARES_RESTAURANTES',
    'restaurante': 'BARES_RESTAURANTES',
    'bar': 'BARES_RESTAURANTES',
    'farmacia': 'CLINICAS_FARMACIAS',
    'clinica': 'CLINICAS_FARMACIAS',
    'clínica': 'CLINICAS_FARMACIAS',
    'hospital': 'CLINICAS_FARMACIAS',
    'discoteca': 'DISCOTECAS',
    'ferretería': 'FERRETERIAS',
    'ferreteria': 'FERRETERIAS',
    'carpintería': 'CARPINTERIAS',
    'carpinteria': 'CARPINTERIAS',
    'cafetería': 'CAFETERIAS_PASTELERIAS',
    'cafeteria': 'CAFETERIAS_PASTELERIAS',
    'panadería': 'CAFETERIAS_PASTELERIAS',
    'panaderia': 'CAFETERIAS_PASTELERIAS',
    'pastelería': 'CAFETERIAS_PASTELERIAS',
    'snack': 'CAFETERIAS_PASTELERIAS',
    'taller': 'TALLERES_BLOQUERIAS',
    'bloquería': 'TALLERES_BLOQUERIAS',
    'artesanal': 'TALLERES_ARTESANALES',
    'artesanía': 'TALLERES_ARTESANALES',
    'videoclub': 'VIDEOS_CLUBS',
    'video club': 'VIDEOS_CLUBS',
    'abacería': 'ABACERIAS',
    'abaceria': 'ABACERIAS',
    'factoría': 'ABACERIAS',
    'tienda': 'ABACERIAS',
    'comercio': 'ABACERIAS',
}

# Maps workflow keywords → workflow code references
WORKFLOW_KEYWORDS = {
    'pasaporte': 'PASAPORTE',
    'passport': 'PASAPORTE',
    'residencia': 'RESIDENCIA',
    'résidence': 'RESIDENCIA',
    'residence': 'RESIDENCIA',
    'conducir': 'CONDUCIR',
    'permis': 'CONDUCIR',
    'carnet de conducir': 'CONDUCIR',
    'licencia de conducir': 'CONDUCIR',
    'contrato': 'CONTRATO',
    'contrat': 'CONTRATO',
    'contract': 'CONTRATO',
    'matriculación': 'VEHICULO',
    'matriculacion': 'VEHICULO',
    'vehículo': 'VEHICULO',
    'vehiculo': 'VEHICULO',
    'coche': 'VEHICULO',
    'voiture': 'VEHICULO',
    'inspección técnica': 'VEHICULO',
    'itv': 'VEHICULO',
    'itve': 'VEHICULO',
    'funcionario': 'FUNCION_PUBLICA',
    'carnet funcionario': 'FP_CARNET',
    'verificación': 'FP_VERIFICACION',
    'verificacion': 'FP_VERIFICACION',
    'dni': 'FP_VERIFICACION',
    'dip': 'FP_VERIFICACION',
    'visado': 'TRAMITES_VISADO',
    'visa': 'TRAMITES_VISADO',
    'prórroga': 'TRAMITES_VISADO',
    'prorroga': 'TRAMITES_VISADO',
}

# Abbreviation expansions for embedding enrichment
ABBREVIATIONS = {
    'dni': 'Documento Nacional de Identidad Personal DIP',
    'dip': 'Documento de Identidad Personal DIP Guinea Ecuatorial',
    'cmf': 'Contribución Mínima Forfetaria impuesto comercio',
    'iva': 'Impuesto sobre el Valor Añadido',
    'irpf': 'Impuesto sobre la Renta de las Personas Físicas',
    'dgt': 'Dirección General del Tesoro tasas fiscales',
    'dgi': 'Dirección General de Impuestos',
    'cnedoge': 'Centro Nacional de Expedición de Documentos Guinea Ecuatorial pasaporte',
    'inseso': 'Instituto Nacional de Seguridad Social',
    'itve': 'Inspección Técnica de Vehículos',
    'itv': 'Inspección Técnica de Vehículos',
    'onrc': 'Oficina Nacional de Registro de Contratos',
    'minfp': 'Ministerio de Función Pública',
    'xaf': 'Franco CFA moneda Guinea Ecuatorial',
    'rbc': 'Recargo Básico Complementario',
    'ge': 'Guinea Ecuatorial',
}

# Intent hint keywords (multilingual)
INTENT_HINTS = {
    'calculate': [
        'cuánto', 'cuanto', 'precio', 'cuesta', 'tarifa', 'tasa', 'coste', 'costo',
        'combien', 'coûte', 'prix', 'tarif',
        'how much', 'cost', 'price', 'fee',
    ],
    'guide': [
        'cómo', 'como', 'pasos', 'procedimiento', 'tramitar', 'proceso', 'hacer',
        'comment', 'étapes', 'procédure', 'démarche',
        'how to', 'steps', 'procedure', 'process',
    ],
    'document': [
        'documento', 'documentos', 'requisito', 'requisitos', 'necesito papeles', 'papeles necesarios',
        'documents requis', 'pièces', 'justificatif',
        'documents needed', 'requirements', 'what documents',
    ],
    'start': [
        'iniciar', 'comenzar', 'empezar', 'solicitar trámite', 'quiero hacer',
        'commencer', 'démarrer', 'je veux faire',
        'start the', 'begin the', 'apply for', 'i want to start',
    ],
}


class QueryPreprocessor:
    """Preprocesses user queries for improved RAG search quality."""

    def preprocess(self, query: str) -> PreprocessedQuery:
        """
        Main entry point. Preprocesses a user query.

        Args:
            query: Raw user message

        Returns:
            PreprocessedQuery with normalized, expanded, and entity-extracted versions
        """
        original = query.strip()
        normalized = self._normalize(original)
        entities = self._extract_entities(original)
        expanded = self._expand(original, entities)
        intent_hints = self._detect_intent_hints(normalized)

        return PreprocessedQuery(
            original=original,
            normalized=normalized,
            expanded=expanded,
            entities=entities,
            detected_intent_hints=intent_hints,
        )

    def _normalize(self, text: str) -> str:
        """Strip accents and lowercase for full-text matching."""
        # NFD decomposition splits accented chars into base + combining mark
        nfkd = unicodedata.normalize('NFKD', text)
        # Keep only non-combining characters
        stripped = ''.join(c for c in nfkd if not unicodedata.combining(c))
        return stripped.lower().strip()

    def _expand(self, text: str, entities: Dict[str, str]) -> str:
        """Expand abbreviations and enrich query for better embedding generation."""
        expanded = text

        # Expand known abbreviations (case-insensitive word boundary)
        for abbr, expansion in ABBREVIATIONS.items():
            pattern = re.compile(r'\b' + re.escape(abbr) + r'\b', re.IGNORECASE)
            if pattern.search(expanded):
                expanded = pattern.sub(f'{abbr} ({expansion})', expanded, count=1)

        # Enrich with entity context
        enrichments = []
        if entities.get('zone_code'):
            enrichments.append(f"zona {entities['zone_code']} Guinea Ecuatorial")
        if entities.get('commerce_type'):
            enrichments.append(f"licencia comercial paquete fiscal apertura")
        if entities.get('workflow'):
            enrichments.append(f"trámite servicio fiscal")

        if enrichments:
            expanded = expanded + ' ' + ' '.join(enrichments)

        return expanded

    def _extract_entities(self, text: str) -> Dict[str, str]:
        """Extract cities, commerce types, and workflow references using word boundaries."""
        entities: Dict[str, str] = {}
        text_lower = text.lower()

        # Detect city → zone (word boundary match to avoid "Malabo" in "Malaboria")
        for city, zone_code in CITY_ZONE_MAP.items():
            if re.search(r'\b' + re.escape(city) + r'\b', text_lower):
                entities['city'] = city
                entities['zone_code'] = zone_code
                break

        # Detect commerce type → bundle code (word boundary to avoid "bar" in "embargo")
        for keyword, bundle_code in COMMERCE_KEYWORDS.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                entities['commerce_keyword'] = keyword
                entities['commerce_type'] = bundle_code
                break

        # Detect workflow reference (word boundary)
        for keyword, workflow_ref in WORKFLOW_KEYWORDS.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                entities['workflow_keyword'] = keyword
                entities['workflow'] = workflow_ref
                break

        return entities

    def _detect_intent_hints(self, normalized_text: str) -> List[str]:
        """Detect intent keywords to hint the routing layer."""
        hints = []
        for intent, keywords in INTENT_HINTS.items():
            if any(kw in normalized_text for kw in keywords):
                hints.append(intent)
        return hints
