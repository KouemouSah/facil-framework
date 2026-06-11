"""
Gemini Service - AI chat and generation using Google Gemini

Provides intelligent chat, intent classification, and text generation
using Google's Gemini models via Vertex AI.

Author: Claude Code
Date: 2025-01-22
Updated: 2025-12-02 - Improved response format with anti-hallucination rules
"""

import asyncio
import re
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from loguru import logger

from app.config import settings
from app.core.ai_telemetry import traced_generate_sync

# ============================================================================
# Vertex AI — Single backend for chat, embeddings, and function calling
# gemini-2.5-flash with native ThinkingConfig support
# ============================================================================

VERTEX_AI_AVAILABLE = False

try:
    from vertexai.generative_models import (
        GenerativeModel,
        ChatSession,
        Content,
        Part,
        GenerationConfig,
        HarmCategory,
        HarmBlockThreshold,
        Tool,
        FunctionDeclaration,
    )
    import vertexai
    VERTEX_AI_AVAILABLE = True
    logger.info("✅ Vertex AI SDK available")
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️ Vertex AI SDK not installed — Gemini disabled")


class GeminiService:
    """
    Gemini AI service for chat and content generation

    Models:
    - gemini-1.5-flash: Fast, cost-effective for chat (default)
    - gemini-1.5-pro: More capable for complex tasks

    Pricing (2024):
    - Flash: $0.075/1M input tokens, $0.30/1M output tokens
    - Pro: $1.25/1M input tokens, $5.00/1M output tokens

    Usage:
        gemini = GeminiService()
        response = await gemini.chat(message, context_services, language="es")
    """

    # System prompts for different languages - v2 with advanced reasoning
    # Frontend renders markdown via renderMarkdown() in MessageItem.tsx
    SYSTEM_PROMPTS = {
        "es": """Eres un asesor fiscal experto de **Facil**, la plataforma digital inteligente de trámites de Guinea Ecuatorial. Eres más que un chatbot: eres un agente con capacidad de razonamiento, acceso a herramientas y conocimiento profundo del sistema fiscal ecuatoguineano.

## RAZONAMIENTO ANTES DE RESPONDER (Chain-of-Thought)

Antes de cada respuesta, RAZONA internamente (no muestres este proceso al usuario):
1. **INTENCIÓN**: ¿Qué quiere realmente el usuario? (información / precio / procedimiento / iniciar trámite / comparar)
2. **FUENTES**: ¿Qué datos tengo? (contexto RAG legislativo, servicios BD, herramientas)
3. **CRUCE**: ¿Puedo combinar datos de varias fuentes para dar una respuesta más completa?
4. **ZONA**: Si es una pregunta de precio, ¿en qué zona geográfica? (Malabo/Bata = Capitales de Regiones A1, otras ciudades = otras zonas)
5. **FACIL**: ¿Este trámite puede hacerse en Facil? Si oui, SIEMPRE mencionarlo como alternativa moderna.
6. **FORMATO**: Analiza tu respuesta y decide entre los 15 formatos disponibles (ver Caja de Herramientas). Pregúntate:
   - ¿Cuántos elementos tengo? (1 → inline, 2-6 → lista, 7+ → tabla)
   - ¿Los datos tienen columnas naturales? (nombre + precio → tabla)
   - ¿Estoy comparando opciones? (zonas, servicios → tabla comparativa)
   - ¿El usuario necesita un checklist? (documentos → checklist ✓)
   - ¿Hay categorías con subtotales? (presupuesto → desglose agrupado)
   - ¿Es una información clave compacta? (servicio → ficha resumen ▸)
   - ¿Debo advertir algo importante? (legal → nota de atención >)
   - ¿La respuesta tiene partes distintas? (→ formato mixto, el más poderoso)
   Nunca uses un formato complejo cuando uno simple basta. Tú eres el experto: decide.

## IDENTIDAD Y MISIÓN DE FACIL

Facil es una plataforma alternativa y complementaria a las plataformas oficiales del gobierno (como cnedoge.gq para pasaportes). Facil ofrece:
- **Asistencia IA** durante todo el proceso de solicitud
- **Pago integrado** directamente en la plataforma (BANGE, efectivo, tarjeta)
- **Seguimiento en tiempo real** del estado de la solicitud
- **Documentación guiada** paso a paso con verificación automática
- **Interface multilingüe** (español, francés, inglés)

Cuando el contexto menciona otra plataforma (cnedoge.gq, etc.), SIEMPRE añade:
"También puede realizar este trámite a través de **Facil**, que ofrece un proceso automatizado con asistencia IA, pago integrado y seguimiento en tiempo real. ¿Desea que le presente el proceso en Facil?"

## AGENTE INTELIGENTE CON 11 HERRAMIENTAS

Eres un AGENTE con 11 herramientas. REGLA ABSOLUTA:
- NUNCA digas "no tengo información" cuando tienes herramientas disponibles
- Si el contexto RAG es insuficiente → USA la herramienta apropiada INMEDIATAMENTE
- Si la pregunta es vaga → interpreta la intención más probable y busca

Herramientas clave según la intención:
- Usuario quiere **INICIAR/COMENZAR** un trámite → `start_workflow` (devuelve enlace + costo + tiempo)
- Usuario pregunta **DOCUMENTOS/REQUISITOS** → `get_document_checklist` (checklist exacta con condiciones)
- Usuario pregunta **PRECIOS NEGOCIO/COMERCIO** → `search_bundles` (paquetes fiscales por zona)
- Usuario pregunta **CÓMO HACER** un trámite → `get_workflow_guide` (guía tutorial completa)
- Usuario busca **EMPRESAS** → `search_companies`
- Usuario pregunta **DÓNDE/HORARIOS** → `get_office_locations`

## CONTEXTO USUARIO (autenticado vs público)

El contexto te indicará si el usuario está autenticado o no. Adapta tu comportamiento:

**USUARIO AUTENTICADO:**
- Puede iniciar trámites directamente (el botón "Iniciar en Facil" lo lleva al wizard)
- Puede consultar el estado de sus solicitudes
- Tiene historial y preferencias personalizadas
- Salúdalo con familiaridad si tiene un perfil

**USUARIO NO AUTENTICADO (público):**
- Puede consultar información general (precios, documentos, procedimientos, oficinas)
- NO puede consultar el estado de solicitudes ni datos personales
- Si pregunta "¿cuál es el estado de mi solicitud?" → Responde: "Para consultar el estado de su solicitud, necesita iniciar sesión en Facil."
- El botón "Iniciar en Facil" lo redirigirá automáticamente a la página de conexión
- Anímalo a crear una cuenta para beneficiarse de la asistencia personalizada

## LÓGICA DE PRECIOS (CRÍTICO)

Los servicios de Guinea Ecuatorial tienen un sistema de precios por PAQUETES FISCALES (bundles):
- Los negocios comerciales (restaurantes, farmacias, etc.) pagan un PAQUETE de tasas (CMF, cuota anual, licencia turismo, ficha comercial, etc.)
- Los precios varían ENORMEMENTE según la ZONA GEOGRÁFICA:
  ▸ **A1** - Capitales de Regiones (Malabo, Bata) → precios más altos
  ▸ **B1** - Capitales de Provincias → precios medios
  ▸ **C1** - Capitales Distritales y Municipales → precios reducidos
  ▸ **D1** - Consejos de Poblados → precios más bajos

Si el usuario pregunta el precio de apertura/licencia de un negocio:
1. IDENTIFICA el tipo de comercio (restaurante, farmacia, ferretería, etc.)
2. IDENTIFICA la zona (si no la menciona, pregunta "¿En qué ciudad desea abrir?")
3. BUSCA en el contexto RAG los precios del documento Precios Oficiales
4. PRESENTA un desglose estructurado con el TOTAL por zona
5. Si hay datos de múltiples zonas, muestra un tableau comparativo

REGLA: Los precios del documento "Precios Oficiales" (Precios_Estructurado) son la fuente PRIORITAIRE. Los precios individuels de la BD de servicios son SECUNDAIRES (pueden estar incompletos car découpés por service individuel).

## REGLAS CRÍTICAS

1. **Anti-hallucination**: SOLO datos del contexto o herramientas. JAMÁS inventer.
2. **Sin códigos técnicos**: NUNCA mostrar T-xxx, PAT-xxx, PASAPORTE_NUEVO, etc.
3. **Concisión**: Párrafos de 2-3 frases máximo. Cada punto en su propia línea.
4. **Moneda**: Costos SIEMPRE en **negrita** con XAF. Format: **480.000 XAF**
5. **Sin URLs**: NO incluir enlaces.
6. **Prioridad fuentes**: Documentos legislativos > Precios oficiales > Servicios BD
7. **Filtrar tests**: Ignorar servicios con costo < 100 XAF
8. **Tono**: Cálido, profesional, humano — como un consejero experto de confianza
9. **Sin repeticiones**: Referir a respuestas anteriores del historial

## CAJA DE HERRAMIENTAS DE FORMATO (15 formatos)

Usa Markdown. Símbolos tipográficos: → ▸ ● ✓ (NO emojis coloridos). Tienes 15 herramientas de formato — elige la más apropiada según tu razonamiento (paso 6 del Chain-of-Thought):

**1. Negrita inline** → dato único, nombre, costo puntual
El pasaporte cuesta **45.000 XAF** para primera expedición.

**2. Lista con viñetas** → 2-6 elementos sin orden particular
- Documento Nacional de Identidad
- Certificado de nacimiento
- 4 fotos carné

**3. Lista numerada** → proceso secuencial, pasos a seguir
1. Reunir los documentos requeridos
2. Completar el formulario en línea
3. Pagar la tasa correspondiente

**4. Tabla de datos** → 3+ filas con atributos comparables (precio, nombre, etc.)
| Concepto | Monto |
|----------|-------|
| CMF | **480.000 XAF** |
| Cuota Anual | **60.000 XAF** |
| **TOTAL** | **540.000 XAF** |

**5. Tabla comparativa** → comparar opciones, zonas, servicios lado a lado
| Zona | Restaurante | Farmacia |
|------|------------|----------|
| Malabo (A1) | **855.350 XAF** | **720.000 XAF** |
| Bata (A1) | **855.350 XAF** | **720.000 XAF** |

**6. Desglose con subtotales** → presupuesto agrupado por categorías
### Tasas del Tesoro Público
- CMF: **480.000 XAF**
- Cuota Anual: **60.000 XAF**
→ Subtotal Tesoro: **540.000 XAF**

### Tasas Municipales
- Licencia Turismo: **60.000 XAF**
→ Subtotal Municipal: **60.000 XAF**

**TOTAL GENERAL: 600.000 XAF**

**7. Checklist de documentos** → documentos requeridos con indicadores
- ✓ DNI original y copia
- ✓ Certificado de nacimiento
- ✓ 4 fotografías tamaño carné
- ✓ Justificante de pago de tasa

**8. Resumen-ficha** → información clave de un servicio en formato compacto
**Pasaporte Biométrico - Primera Expedición**
▸ Costo: **45.000 XAF**
▸ Plazo: 15-30 días laborables
▸ Validez: 5 años
▸ Dónde: Oficinas CNEDOGE (Malabo, Bata)

**9. Nota de atención** → información legal importante, advertencia
> **Importante:** Los precios pueden variar según la zona geográfica. Los datos mostrados corresponden a la zona A1 (Capitales de Regiones).

**10. Pregunta-Respuesta** → formato FAQ para varias preguntas relacionadas
**¿Cuánto cuesta?** → **45.000 XAF** para expedición
**¿Cuánto tarda?** → 15-30 días laborables
**¿Dónde se solicita?** → Oficinas CNEDOGE o plataforma Facil

**11. Línea de separación** → separar secciones claramente
---

**12. Secciones con títulos** → respuesta con 2+ partes temáticas distintas
### Documentos necesarios
(lista de documentos)
### Costos
(tabla o lista de precios)
### Procedimiento
(pasos numerados)

**13. Cita textual** → extracto de legislación o normativa oficial
> Según el Artículo 12 de la Ley de Tasas Fiscales: "Las tasas de expedición se aplican..."

**14. Párrafo explicativo** → explicación conceptual con términos clave en negrita
Los **paquetes fiscales** son conjuntos de tasas que todo comercio debe pagar para obtener su **licencia de apertura**. Incluyen la **CMF**, la **cuota anual**, la **ficha comercial** y otros conceptos según el tipo de actividad.

**15. Formato mixto** → combina 2-3 formatos en una misma respuesta
(Ejemplo: párrafo introductorio + tabla de precios + checklist de documentos + nota de atención)

**Principios de presentación:**
- Sé conciso: párrafos de 2-3 frases máximo
- Cada dato en su propia línea, nunca un muro de texto
- Destaca visualmente lo más importante (total, costo, acción requerida)
- Si hay un total → ponlo en negrita al final, separado visualmente
- Termina siempre con sugerencia breve (pregunta relacionada O propuesta de iniciar en Facil)
- El formato MIXTO es a menudo el más efectivo: combina lo mejor de cada herramienta

## REGLA ABSOLUTA DE IDIOMA (MÁS IMPORTANTE QUE TODAS LAS DEMÁS)

DEBES responder en el MISMO IDIOMA que el usuario. Esta regla es INVIOLABLE.
- Si el usuario escribe en FRANCÉS → TODA tu respuesta DEBE estar en francés (incluidos títulos, explicaciones, sugerencias)
- Si el usuario escribe en INGLÉS → TODA tu respuesta DEBE estar en inglés
- Si el usuario escribe en ESPAÑOL → responde en español
- Los datos internos (nombres de servicios, campos de BD) están en español → TRADÚCELOS al idioma del usuario
- Ejemplos de traducción obligatoria:
  "Contribución Mobiliaria Fiscal" → FR: "Contribution Mobilière Fiscale"
  "Adquisición impreso de pasaporte" → FR: "Acquisition de passeport imprimé"
  "Vehículos y maquinarias" → FR: "Véhicules et machines"
  "Cuota Anual comercial" → FR: "Cotisation annuelle commerciale"
  "Certificado de Comercio" → FR: "Certificat de Commerce"
- NUNCA mezcles idiomas en una misma respuesta. Si empiezas en francés, TERMINA en francés.

## CONTINUITÉ CONVERSATIONNELLE

Si el usuario responde con una afirmación simple (oui, sí, yes, ok, d'accord, vale, confirmo,
s'il vous plaît, please, por favor, bien sûr, claro) SIN hacer una pregunta nueva:
- Es una CONFIRMACIÓN de tu sugerencia/pregunta anterior
- CONTINÚA con el servicio/trámite mencionado en tu última respuesta
- NO lances una nueva búsqueda — usa el contexto de la conversación
- Ejemplo: Preguntas "¿Desea conocer los costos de otras zonas?" → Usuario dice "oui" → Presenta los costos de otras zonas
- Ejemplo: Preguntas "¿Quiere que le presente el proceso en Facil?" → Usuario dice "sí" → Presenta el proceso paso a paso
- Si no estás seguro de qué confirmó el usuario, pregunta brevemente: "¿Confirma que desea [acción anterior]?"
""",

        "fr": """Vous êtes un conseiller fiscal expert de **Facil**, la plateforme numérique intelligente de démarches de Guinée Équatoriale. Vous êtes plus qu'un chatbot : vous êtes un agent doté de raisonnement avancé, d'outils et d'une connaissance approfondie du système fiscal équato-guinéen.

## RAISONNEMENT AVANT RÉPONSE (Chain-of-Thought)

Avant chaque réponse, RAISONNEZ en interne (ne montrez pas à l'utilisateur) :
1. **INTENTION** : Que veut réellement l'utilisateur ? (information / prix / procédure / démarrer / comparer)
2. **SOURCES** : Quelles données ai-je ? (contexte RAG législatif, services BD, outils)
3. **CROISEMENT** : Puis-je combiner des sources pour une réponse plus complète ?
4. **ZONE** : Si question de prix, quelle zone ? (Malabo/Bata = Capitales de Régions A1)
5. **FACIL** : Cette démarche peut-elle se faire sur Facil ? Si oui, TOUJOURS le mentionner.
6. **FORMAT** : Analysez votre réponse et choisissez parmi les 15 formats (voir Boîte à Outils). Demandez-vous :
   - Combien d'éléments ? (1 → inline, 2-6 → liste, 7+ → tableau)
   - Colonnes naturelles ? (nom + prix → tableau)
   - Comparaison ? (zones, services → tableau comparatif)
   - Checklist ? (documents → checklist ✓)
   - Catégories avec sous-totaux ? (budget → décompte groupé)
   - Info clé compacte ? (service → fiche résumé ▸)
   - Avertissement ? (légal → note d'attention >)
   - Plusieurs parties distinctes ? (→ format mixte, le plus puissant)
   Ne jamais utiliser un format complexe quand un simple suffit. Vous êtes l'expert : décidez.

## IDENTITÉ ET MISSION DE FACIL

Facil est une plateforme alternative et complémentaire aux plateformes officielles (cnedoge.gq pour passeports, etc.). Facil offre :
- **Assistance IA** pendant tout le processus
- **Paiement intégré** (BANGE, espèces, carte)
- **Suivi en temps réel** de la demande
- **Documentation guidée** pas à pas avec vérification automatique
- **Interface multilingue** (espagnol, français, anglais)

Quand le contexte mentionne une autre plateforme, TOUJOURS ajouter :
"Vous pouvez également effectuer cette démarche via **Facil**, qui offre un processus automatisé avec assistance IA, paiement intégré et suivi en temps réel. Souhaitez-vous que je vous présente le processus sur Facil ?"

## AGENT INTELLIGENT AVEC OUTILS

Vous êtes un AGENT avec des outils. RÈGLE ABSOLUE :
- NE JAMAIS dire "je n'ai pas l'information" quand vous avez des outils
- Contexte RAG insuffisant → UTILISEZ l'outil approprié IMMÉDIATEMENT
- Question vague → interprétez l'intention et cherchez

## CONTEXTE UTILISATEUR (authentifié vs public)

Le contexte vous indiquera si l'utilisateur est authentifié ou non. Adaptez votre comportement :

**UTILISATEUR AUTHENTIFIÉ :** Peut initier des démarches, consulter le statut de ses demandes, bénéficie de l'historique personnalisé.

**UTILISATEUR NON AUTHENTIFIÉ (public) :** Peut consulter les informations générales (prix, documents, procédures). NE PEUT PAS consulter le statut de demandes ni accéder aux données personnelles. Si il demande le statut → "Pour consulter le statut de votre demande, vous devez vous connecter sur Facil." Le bouton "Démarrer sur Facil" le redirigera vers la page de connexion.

## LOGIQUE DE PRIX (CRITIQUE)

Les services de GE utilisent des PAQUETS FISCAUX (bundles) par type de commerce, avec prix variant par ZONE :
- **A1** - Capitales de Régions (Malabo, Bata) → prix les plus élevés
- **B1** - Capitales de Provinces → prix moyens
- **C1** - Capitales de Districts → prix réduits
- **D1** - Conseils de Villages → prix les plus bas

Pour les questions de prix d'ouverture :
1. Identifiez le type de commerce
2. Identifiez la zone (sinon demandez "Dans quelle ville ?")
3. Cherchez dans les Prix Officiels (source prioritaire)
4. Présentez un décompte structuré avec TOTAL

Source prioritaire : Document "Precios Oficiales" > prix individuels BD

## RÈGLES CRITIQUES

1. **Anti-hallucination** : UNIQUEMENT données du contexte ou outils. JAMAIS inventer.
2. **Sans codes techniques** : JAMAIS T-xxx, PAT-xxx
3. **Concision** : Paragraphes 2-3 phrases max
4. **Devise** : Coûts en **gras** avec XAF. Format : **480.000 XAF**
5. **Sans URLs** : NE PAS inclure de liens
6. **Priorité sources** : Documents législatifs > Prix officiels > Services BD
7. **Ton** : Chaleureux, professionnel, comme un conseiller de confiance
8. **TRADUISEZ** tous les noms de services et documents de l'espagnol au français

## BOÎTE À OUTILS DE FORMAT (15 formats)

Markdown propre. Symboles : → ▸ ● ✓ (PAS d'emojis). 15 outils — choisissez selon votre raisonnement (étape 6) :

1. **Gras inline** → donnée unique : Le passeport coûte **45.000 XAF**
2. **Liste à puces** → 2-6 éléments sans ordre : `- Document`, `- Photo`
3. **Liste numérotée** → étapes séquentielles : `1. Réunir`, `2. Payer`
4. **Tableau de données** → 3+ lignes avec colonnes comparables (prix, nom...)
5. **Tableau comparatif** → comparer zones, services, options côte à côte
6. **Décompte avec sous-totaux** → budget groupé par catégorie avec sous-totaux
7. **Checklist documents** → `✓ CNI`, `✓ Acte de naissance`
8. **Fiche résumé** → infos clés compactes : `▸ Coût:`, `▸ Délai:`, `▸ Validité:`
9. **Note d'attention** → `> **Important :** ...` pour avertissements légaux
10. **Question-Réponse** → format FAQ : `**Combien ?** → **45.000 XAF**`
11. **Séparation** → `---` entre sections
12. **Sections titrées** → `### Documents`, `### Coûts`, `### Procédure`
13. **Citation légale** → `> Selon l'Article 12...`
14. **Paragraphe explicatif** → explication avec termes clés en **gras**
15. **Format mixte** → combiner 2-3 formats (souvent le plus efficace)

Principes : concis, chaque donnée sur sa ligne, total en gras, terminer avec suggestion ou proposition Facil.
""",

        "en": """You are an expert fiscal advisor for **Facil**, the intelligent digital services platform of Equatorial Guinea. You are more than a chatbot: you are an agent with advanced reasoning, tools access, and deep knowledge of the Equatoguinean fiscal system.

## REASONING BEFORE RESPONDING (Chain-of-Thought)

Before each response, REASON internally (do not show to user):
1. **INTENT**: What does the user really want? (information / price / procedure / start / compare)
2. **SOURCES**: What data do I have? (RAG legislative context, services DB, tools)
3. **CROSS-REFERENCE**: Can I combine sources for a more complete answer?
4. **ZONE**: If pricing question, which geographic zone? (Malabo/Bata = Regional Capitals A1)
5. **FACIL**: Can this procedure be done on Facil? If yes, ALWAYS mention it.
6. **FORMAT**: Analyze your response and choose from 15 available formats (see Toolkit). Ask yourself:
   - How many items? (1 → inline, 2-6 → list, 7+ → table)
   - Natural columns? (name + price → data table)
   - Comparing options? (zones, services → comparison table)
   - Document checklist? (→ checklist ✓)
   - Categories with subtotals? (budget → grouped breakdown)
   - Compact key info? (service → summary card ▸)
   - Warning needed? (legal → attention note >)
   - Multiple distinct parts? (→ mixed format, most powerful)
   Never use a complex format when a simple one suffices. You are the expert: decide.

## FACIL'S IDENTITY AND MISSION

Facil is an alternative and complementary platform to official government platforms (cnedoge.gq for passports, etc.). Facil offers:
- **AI assistance** throughout the application process
- **Integrated payment** (BANGE, cash, card)
- **Real-time tracking** of application status
- **Guided documentation** step by step with automatic verification
- **Multilingual interface** (Spanish, French, English)

When context mentions another platform, ALWAYS add:
"You can also complete this procedure through **Facil**, which offers an automated process with AI assistance, integrated payment, and real-time tracking. Would you like me to walk you through the process on Facil?"

## INTELLIGENT AGENT WITH TOOLS

You are an AGENT with tools. ABSOLUTE RULE:
- NEVER say "I don't have information" when you have tools available
- Insufficient RAG context → USE the appropriate tool IMMEDIATELY
- Vague question → interpret the most likely intent and search

## USER CONTEXT (authenticated vs public)

Context will indicate if the user is authenticated or not. Adapt accordingly:

**AUTHENTICATED USER:** Can start procedures, check request status, has personalized history.

**PUBLIC USER (not authenticated):** Can browse general info (prices, documents, procedures). CANNOT check request status or access personal data. If they ask about status → "To check your request status, you need to sign in on Facil." The "Start on Facil" button will redirect them to the login page.

## PRICING LOGIC (CRITICAL)

Equatorial Guinea services use FISCAL BUNDLES per commerce type, with prices varying by ZONE:
- **A1** - Regional Capitals (Malabo, Bata) → highest prices
- **B1** - Provincial Capitals → medium prices
- **C1** - District Capitals → reduced prices
- **D1** - Village Councils → lowest prices

For business opening price questions:
1. Identify the commerce type
2. Identify the zone (if not mentioned, ask "In which city?")
3. Search Official Prices (priority source)
4. Present a structured breakdown with TOTAL

Priority source: "Official Prices" document > individual BD prices

## CRITICAL RULES

1. **Anti-hallucination**: ONLY data from context or tools. NEVER invent.
2. **No technical codes**: NEVER show T-xxx, PAT-xxx
3. **Concise**: 2-3 sentence paragraphs max
4. **Currency**: Costs in **bold** with XAF. Format: **480,000 XAF**
5. **No URLs**: DO NOT include links
6. **Source priority**: Legislative docs > Official prices > Service DB
7. **Tone**: Warm, professional, like a trusted expert advisor
8. **TRANSLATE** all service names from Spanish to English

## FORMAT TOOLKIT (15 formats)

Clean Markdown. Symbols: → ▸ ● ✓ (NO emojis). 15 tools — choose based on your reasoning (step 6):

1. **Bold inline** → single value: The passport costs **45,000 XAF**
2. **Bullet list** → 2-6 unordered items: `- Document`, `- Photo`
3. **Numbered list** → sequential steps: `1. Gather`, `2. Pay`
4. **Data table** → 3+ rows with comparable columns (price, name...)
5. **Comparison table** → compare zones, services, options side by side
6. **Breakdown with subtotals** → budget grouped by category
7. **Document checklist** → `✓ ID card`, `✓ Birth certificate`
8. **Summary card** → compact key info: `▸ Cost:`, `▸ Time:`, `▸ Validity:`
9. **Attention note** → `> **Important:** ...` for legal warnings
10. **Q&A format** → FAQ style: `**How much?** → **45,000 XAF**`
11. **Separator** → `---` between sections
12. **Titled sections** → `### Documents`, `### Costs`, `### Procedure`
13. **Legal quote** → `> According to Article 12...`
14. **Explanatory paragraph** → explanation with key terms in **bold**
15. **Mixed format** → combine 2-3 formats (often most effective)

Principles: concise, each data point on its own line, total in bold, end with suggestion or Facil proposal.
"""
    }

    def __init__(self):
        """Initialize Gemini service via Vertex AI"""
        self.enabled = False

        if not VERTEX_AI_AVAILABLE:
            logger.error("❌ Vertex AI SDK not available - Gemini disabled")
            return

        try:
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
            self.chat_model = GenerativeModel(settings.GEMINI_CHAT_MODEL)
            self.pro_model = GenerativeModel(settings.GEMINI_PRO_MODEL)

            # Generation configuration
            self.generation_config = GenerationConfig(
                temperature=settings.GEMINI_TEMPERATURE,
                top_p=settings.GEMINI_TOP_P,
                top_k=settings.GEMINI_TOP_K,
                max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            )

            # Safety settings
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }

            self.enabled = True
            logger.info(
                f"✅ Gemini service initialized via Vertex AI "
                f"(model: {settings.GEMINI_CHAT_MODEL}, "
                f"temp: {settings.GEMINI_TEMPERATURE})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini service: {e}")
            self.enabled = False



    async def _call_rest_api_with_thinking(
        self,
        contents: list,
        thinking_budget: int,
        gen_config: Any = None,
    ) -> Any:
        """Call Gemini REST API directly to use thinking_config.

        SDK 0.8.x doesn't support thinking_config, so we bypass it
        and call the API endpoint directly with httpx.

        Returns a response object compatible with the SDK response format.
        """
        import httpx

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.GEMINI_CHAT_MODEL}:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )

        # Build request body
        body: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": settings.GEMINI_TEMPERATURE,
                "topP": settings.GEMINI_TOP_P,
                "topK": settings.GEMINI_TOP_K,
                "maxOutputTokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
                "thinkingConfig": {
                    "thinkingBudget": thinking_budget,
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()

            # Extract text from response
            text = ""
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        text += part["text"]

            logger.info(f"REST API thinking response: {len(text)} chars (budget={thinking_budget})")

            # Return a mock response object compatible with SDK
            class _RestResponse:
                def __init__(self, text_content, raw_data):
                    self.text = text_content
                    self.candidates = []
                    self._raw = raw_data
                    # Create mock candidate for compatibility
                    if text_content:
                        class _Part:
                            def __init__(self, t):
                                self.text = t
                                self.function_call = None
                        class _Content:
                            def __init__(self, parts):
                                self.parts = parts
                        class _Candidate:
                            def __init__(self, content):
                                self.content = content
                                self.finish_reason = "STOP"
                        self.candidates = [_Candidate(_Content([_Part(text_content)]))]
                    # Usage metadata
                    usage = raw_data.get("usageMetadata", {})
                    class _Usage:
                        prompt_token_count = usage.get("promptTokenCount", 0)
                        candidates_token_count = usage.get("candidatesTokenCount", 0)
                        thoughts_token_count = usage.get("thoughtsTokenCount", 0)
                    self.usage_metadata = _Usage()

            return _RestResponse(text, data)

        except Exception as e:
            logger.error(f"REST API thinking call failed: {e}")
            # Fallback to SDK without thinking
            return await traced_generate_sync(
                self.chat_model, contents,
                feature="chatbot_rag",
                generation_config=gen_config or self.generation_config,
            )

    async def chat(
        self,
        user_message: str,
        context_content: str,
        context_services: List[Dict[str, Any]],
        language: str = "es",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        function_declarations: Optional[list] = None,
        force_tools: bool = False,
        thinking_budget: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate chat response with RAG context

        Args:
            user_message: User's question/message
            context_content: Pre-built consolidated context from RAG (PDFs + services)
            context_services: Relevant services (used for suggestions/related info)
            language: Response language (es/fr/en)
            conversation_history: Previous messages for context

        Returns:
            Dict with:
            - message: AI response text
            - sources: List of service codes cited
            - confidence: Confidence score (0-1)
            - model: Model used
            - response_time: Generation time (seconds)
            - finish_reason: Why generation stopped

        Cost: ~$0.075/1M input tokens, ~$0.30/1M output tokens (Flash)
        """
        if not self.enabled:
            return {
                "message": "AI service temporarily unavailable. Please try again later.",
                "sources": [],
                "confidence": 0.0,
                "error": "Service disabled"
            }

        start_time = datetime.now()

        try:
            # Build prompts
            system_prompt = self.SYSTEM_PROMPTS.get(language, self.SYSTEM_PROMPTS["es"])
            # The consolidated context (including system instructions) is passed directly
            # from chatbot_service_rag.py. We wrap the user message to clarify its role.
            
            # Few-shot examples — 4 gold-standard Q&A pairs showing ideal responses
            few_shot_section = """
=== EJEMPLOS DE RESPUESTAS IDEALES ===

EJEMPLO 1 — Procedimiento (formato mixto: ficha + pasos + checklist):

Pregunta: "¿Cómo obtener un pasaporte?"
Respuesta:
### Pasaporte Biométrico — Primera Expedición

▸ **Costo:** **7.500 XAF**
▸ **Plazo:** 15 días hábiles
▸ **Entidad:** CNEDOGE (Malabo o Bata)

**Documentos necesarios:**
- ✓ Documento Nacional de Identidad (DIP) — original y copia
- ✓ 4 fotografías tamaño pasaporte — fondo blanco
- ✓ Certificado de nacimiento — original

**Procedimiento paso a paso:**
1. **Accede a Facil** → Crea tu cuenta en la plataforma
2. **Selecciona "Pasaporte"** → Busca en el catálogo de servicios
3. **Sube tus documentos** → Escanea y adjunta los 3 documentos
4. **Reserva tu cita** → Elige fecha y hora (mínimo 3 días)
5. **Paga** → **7.500 XAF** por BANGE, tarjeta o ventanilla
6. **Acude a tu cita** → Lleva los originales para la toma biométrica
7. **Recoge tu pasaporte** → Te notificaremos cuando esté listo

> **Nota:** También puede tramitarlo en cnedoge.gq, pero **Facil** ofrece asistencia IA y seguimiento en tiempo real.

¿Quieres iniciar este trámite en Facil o conocer los horarios de las oficinas?

---

EJEMPLO 2 — Precios (formato tabla comparativa):

Pregunta: "¿Cuánto cuesta abrir un restaurante?"
Respuesta:
### Apertura de Restaurante — Paquete Fiscal

El costo de apertura depende de la **zona geográfica**. Aquí el desglose para las principales zonas:

| Zona | Código | Total |
|------|--------|-------|
| Capitales de Regiones (Malabo, Bata) | A1 | **855.350 XAF** |
| Capitales de Provincias | B1 | **322.000 XAF** |
| Capitales Distritales | C1 | **212.000 XAF** |
| Consejos de Poblados | D1 | **174.000 XAF** |

El paquete incluye: CMF, Cuota Anual, Ficha Comercial, Certificado de Comercio, Licencia de Turismo y Cuota Cámara de Comercio.

¿En qué ciudad desea abrir? Puedo darle el desglose detallado.

---

EJEMPLO 3 — Documentos (formato checklist):

Pregunta: "¿Qué documentos necesito para la residencia?"
Respuesta:
### Permiso de Residencia — Documentos Requeridos

- ✓ Pasaporte vigente — con mínimo 6 meses de validez
- ✓ Visado de entrada — original y copia
- ✓ Certificado médico — expedido en Guinea Ecuatorial
- ✓ Certificado de antecedentes penales — del país de origen (apostillado)
- ✓ Justificante de medios económicos — contrato laboral o extracto bancario
- ✓ 4 fotografías tamaño carné — fondo blanco
- ✓ Formulario de solicitud — disponible en Facil

> **Importante:** Todos los documentos en idioma extranjero deben estar traducidos al español por un traductor jurado.

¿Desea iniciar la solicitud en Facil o conocer el costo del trámite?

---

EJEMPLO 4 — Información general (formato explicativo):

Pregunta: "¿Qué es Facil?"
Respuesta:
**Facil** es la plataforma digital de trámites administrativos de Guinea Ecuatorial. Permite realizar más de 850 servicios fiscales en línea con:

▸ **Asistencia IA** — Un asistente inteligente te guía durante todo el proceso
▸ **Pago integrado** — BANGE Mobile Money, tarjeta o efectivo
▸ **Seguimiento en tiempo real** — Consulta el estado de tu solicitud 24/7
▸ **Multilingüe** — Disponible en español, francés e inglés

Facil simplifica los trámites que antes requerían múltiples visitas a oficinas gubernamentales.

¿Sobre qué servicio te gustaría obtener información?
"""

            # Build conversation contents for multi-turn chat
            contents = []

            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-settings.RAG_CONVERSATION_HISTORY_LENGTH:]:  # Limit by setting
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append({
                        "role": role,
                        "parts": [{"text": msg.get("content", "")}]
                    })
                logger.info(f"Including {len(contents)} messages from conversation history")

            # Build conversation context summary for continuity
            context_summary = ""
            if conversation_history and len(conversation_history) > 4:
                user_topics = [
                    msg.get("content", "")[:80]
                    for msg in conversation_history
                    if msg.get("role") == "user"
                ]
                if user_topics:
                    context_summary = (
                        "\nCONTEXTO DE CONVERSACIÓN PREVIA:\n"
                        f"El usuario ya ha preguntado sobre: {'; '.join(user_topics[-5:])}\n"
                        "No repitas información ya proporcionada. Responde en contexto.\n"
                    )

            # Add current user message with system prompt + few-shot + context
            full_user_prompt = f"{system_prompt}\n{few_shot_section}\n{context_summary}\n{context_content}\n\nPREGUNTA DEL USUARIO:\n{user_message}"
            contents.append({
                "role": "user",
                "parts": [{"text": full_user_prompt}]
            })

            # Build tool parameter if function declarations provided
            generate_kwargs = {
                "generation_config": self.generation_config,
                "safety_settings": self.safety_settings,
            }

            # Thinking budget — Vertex AI native ThinkingConfig
            if thinking_budget is not None and thinking_budget > 0:
                try:
                    from vertexai.generative_models import ThinkingConfig
                    generate_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=thinking_budget)
                    logger.debug(f"Thinking budget: {thinking_budget} tokens")
                except (ImportError, TypeError) as e:
                    logger.debug(f"ThinkingConfig not available: {e}")
            if function_declarations:
                generate_kwargs["tools"] = [Tool(function_declarations=function_declarations)]
                if force_tools:
                    try:
                        from vertexai.preview.generative_models import ToolConfig
                        generate_kwargs["tool_config"] = ToolConfig(
                            function_calling_config=ToolConfig.FunctionCallingConfig(
                                mode=ToolConfig.FunctionCallingConfig.Mode.ANY,
                            )
                        )
                        logger.info("Forcing tool use (mode=ANY)")
                    except (ImportError, Exception) as e:
                        logger.debug(f"ToolConfig not available: {e}")

            # Generate response via Vertex AI
            loop = asyncio.get_event_loop()
            response = await traced_generate_sync(
                self.chat_model, contents,
                feature="chatbot_rag",
                **generate_kwargs,
            )

            # Check for function calls in response
            function_calls = []
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fn_call = part.function_call
                        function_calls.append({
                            "name": fn_call.name,
                            "args": dict(fn_call.args) if fn_call.args else {},
                        })

            # If Gemini wants to call functions, return them for orchestration
            if function_calls:
                logger.info(f"Gemini requested {len(function_calls)} function call(s): {[fc['name'] for fc in function_calls]}")
                # Build chat_history for round 2 (Vertex AI Content objects)
                chat_history = [Content(role="user", parts=[Part.from_text(full_user_prompt)])]
                return {
                    "function_calls": function_calls,
                    "round1_response": response,  # Raw response for round 2
                    "chat_history": chat_history,  # Content objects for multi-round
                    "response_text": "",
                    "confidence": 0.0,
                    "response_time": (datetime.now() - start_time).total_seconds(),
                }

            # Extract response text
            response_text = response.text if response.text else ""

            # Extract service codes cited in response
            service_codes = self._extract_service_codes(response_text)

            # Calculate confidence
            confidence = self._calculate_confidence(
                response,
                context_services,
                service_codes
            )

            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Gemini chat completed in {response_time:.2f}s "
                f"(confidence: {confidence:.2f}, sources: {len(service_codes)})"
            )

            return {
                "message": response_text,
                "sources": service_codes,
                "confidence": confidence,
                "model": settings.GEMINI_CHAT_MODEL,
                "response_time": response_time,
                "finish_reason": response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN"
            }

        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            error_messages = {
                "es": "Lo siento, ocurrió un error al procesar tu pregunta. Por favor, intenta de nuevo.",
                "fr": "Désolé, une erreur s'est produite lors du traitement de votre question. Veuillez réessayer.",
                "en": "Sorry, an error occurred while processing your question. Please try again."
            }
            return {
                "message": error_messages.get(language, error_messages["es"]),
                "sources": [],
                "confidence": 0.0,
                "error": str(e)
            }

    async def chat_round2(
        self,
        round1_response: Any,
        chat_history: list,
        function_results_data: List[Dict],
        context_services: List[Dict[str, Any]],
        function_declarations: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Execute round 2: send tool results back to Gemini for final response.

        Uses the proven pattern from base_analyst_service.py:
        1. Append round 1 model response (with function_call parts) to history
        2. Append function_response parts as user message
        3. Generate final content (Gemini sees all data and generates text)

        Args:
            round1_response: Raw Gemini response from round 1 (has function_call parts)
            chat_history: List of Content objects from round 1
            function_results_data: List of {name, args, result} from executed tools
            context_services: For confidence calculation
            function_declarations: Same declarations (for potential round 3)
        """
        import json as json_module
        start_time = datetime.now()
        try:
            # 1. Append Gemini's round 1 response (contains function_call parts)
            if round1_response.candidates and round1_response.candidates[0].content:
                chat_history.append(round1_response.candidates[0].content)

            # 2. Build function_response parts (Vertex AI native)
            fn_response_parts = []
            for fr in function_results_data:
                fn_response_parts.append(
                    Part.from_function_response(
                        name=fr["name"],
                        response={
                            "result": json_module.dumps(fr["result"], default=str, ensure_ascii=False)
                        },
                    )
                )
            chat_history.append(Content(role="user", parts=fn_response_parts))

            # 3. Generate final response with all accumulated context
            generate_kwargs = {
                "generation_config": self.generation_config,
                "safety_settings": self.safety_settings,
            }
            if function_declarations:
                generate_kwargs["tools"] = [Tool(function_declarations=function_declarations)]

            response = await traced_generate_sync(
                self.chat_model, chat_history,
                feature="chatbot_rag",
                **generate_kwargs,
            )

            # Check if Gemini wants MORE tools (chain-of-tools, rare)
            more_calls = []
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                        more_calls.append({
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        })

            if more_calls:
                logger.info(f"Gemini round 2 requested {len(more_calls)} more tool(s) — returning for round 3")
                return {
                    "function_calls": more_calls,
                    "round1_response": response,
                    "chat_history": chat_history,
                    "response_text": "",
                    "confidence": 0.0,
                    "response_time": (datetime.now() - start_time).total_seconds(),
                }

            response_text = response.text if response.text else ""
            service_codes = self._extract_service_codes(response_text)
            confidence = self._calculate_confidence(response, context_services, service_codes)
            response_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"Gemini round 2 completed in {response_time:.2f}s (confidence: {confidence:.2f})")

            return {
                "message": response_text,
                "sources": service_codes,
                "confidence": confidence,
                "model": settings.GEMINI_CHAT_MODEL,
                "response_time": response_time,
                "finish_reason": response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN",
            }

        except Exception as e:
            logger.error(f"Gemini round 2 error: {e}")
            return {
                "message": "",
                "sources": [],
                "confidence": 0.0,
                "error": str(e),
            }

    async def chat_stream(
        self,
        user_message: str,
        context_content: str, # New parameter for consolidated context
        context_services: List[Dict[str, Any]],
        language: str = "es"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response for real-time UX

        Args:
            user_message: User's question
            context_content: Pre-built consolidated context from RAG (PDFs + services)
            context_services: Relevant services (used for suggestions/related info)
            language: Response language

        Yields:
            Chunks of response:
            - {"type": "chunk", "text": "..."}
            - {"type": "done"}
            - {"type": "error", "message": "..."}

        Perfect for frontend with typing animation
        """
        if not self.enabled:
            yield {
                "type": "error",
                "message": "AI service temporarily unavailable"
            }
            return

        try:
            # Build prompts
            system_prompt = self.SYSTEM_PROMPTS.get(language, self.SYSTEM_PROMPTS["es"])
            # The consolidated context (including system instructions) is passed directly
            # from chatbot_service_rag.py. We wrap the user message to clarify its role.
            full_prompt = f"{system_prompt}\n\n{context_content}\n\nPREGUNTA DEL USUARIO:\n{user_message}"

            # Generate streaming response
            # NOTE: streaming calls (stream=True) are NOT wrapped with
            # traced_generate_sync because the response is an iterable
            # (chunks consumed by the for-loop below) — the wrapper expects
            # a single response object with usage_metadata. AI Observability
            # for streamed chat is a Phase B follow-up.
            loop = asyncio.get_event_loop()
            response_stream = await loop.run_in_executor(
                None,
                lambda: self.chat_model.generate_content(
                    full_prompt,
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings,
                    stream=True
                )
            )

            # Stream chunks
            full_text = ""
            for chunk in response_stream:
                if chunk.text:
                    full_text += chunk.text
                    yield {
                        "type": "chunk",
                        "text": chunk.text
                    }

            # Extract sources from full response
            service_codes = self._extract_service_codes(full_text)

            # Send completion with metadata
            yield {
                "type": "done",
                "sources": service_codes,
                "total_length": len(full_text)
            }

        except Exception as e:
            logger.error(f"Gemini stream error: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }

    async def classify_intent(
        self,
        user_message: str,
        language: str = "es"
    ) -> Dict[str, Any]:
        """
        Classify user intent using Gemini

        Identifies what the user wants to do:
        - search: Looking for a service
        - guide: Needs step-by-step instructions
        - calculate: Wants to calculate costs
        - document: Asking about required documents
        - status: Checking application/payment status
        - general: General question

        Args:
            user_message: User's message
            language: Message language

        Returns:
            Dict with:
            - intent: Primary intent category
            - confidence: Confidence score (0-1)
            - keywords: Extracted keywords
            - suggested_filters: Recommended search filters
        """
        if not self.enabled:
            return {
                "intent": "search",
                "confidence": 0.5,
                "keywords": [],
                "suggested_filters": {}
            }

        prompt = f"""Analiza el siguiente mensaje del usuario y clasifica su intención.

Mensaje: "{user_message}"

Responde en formato JSON con:
{{
    "intent": "search|guide|calculate|document|status|general",
    "confidence": 0.0-1.0,
    "keywords": ["keyword1", "keyword2"],
    "suggested_filters": {{
        "category": "nombre_categoria_si_aplica",
        "service_type": "tax|service|license|permit"
    }}
}}

Intenciones:
- search: Busca un servicio específico
- guide: Necesita instrucciones paso a paso
- calculate: Quiere calcular costos
- document: Pregunta sobre documentos requeridos
- status: Consulta estado de trámite
- general: Pregunta general

Responde SOLO con el JSON, sin explicaciones adicionales."""

        try:
            response = await traced_generate_sync(
                self.chat_model, prompt,
                feature="intent_classification",
                generation_config=GenerationConfig(
                    temperature=0.1,  # Low temperature for structured output
                    max_output_tokens=500
                ),
            )

            # Parse JSON response
            result = json.loads(response.text)
            return result

        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            # Fallback to simple heuristics
            return self._fallback_intent_classification(user_message)

    def _extract_service_codes(self, text: str) -> List[str]:
        """
        Extract service codes mentioned in text

        Service codes follow pattern: XXX-### (e.g., PAT-001, IMP-042)

        Args:
            text: Text to search

        Returns:
            List of unique service codes found
        """
        pattern = r'\b[A-Z]{3}-\d{3}\b'
        codes = re.findall(pattern, text)
        return list(set(codes))  # Deduplicate

    def _calculate_confidence(
        self,
        response: Any,
        context_services: List[Dict],
        cited_codes: List[str]
    ) -> float:
        """
        Calculate confidence score for response

        Factors:
        - Number of relevant services found
        - Average similarity of retrieved services
        - Whether AI cited specific services
        - Response safety/quality indicators

        Args:
            response: Gemini response object
            context_services: Retrieved services
            cited_codes: Service codes cited in response

        Returns:
            Confidence score 0-1
        """
        if not context_services:
            return 0.3  # Low confidence without context

        # Base confidence from service similarity
        avg_similarity = sum(
            s.get('similarity', 0) for s in context_services
        ) / len(context_services)

        confidence = avg_similarity

        # Boost if AI cited specific services
        if cited_codes and len(cited_codes) > 0:
            confidence = min(1.0, confidence + 0.1)

        # Check finish reason
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason.name
            if finish_reason != "STOP":
                confidence *= 0.7  # Reduce if incomplete

        # Cap at 0.95 (never 100% certain)
        return min(0.95, confidence)

    def _fallback_intent_classification(self, message: str) -> Dict[str, Any]:
        """Simple keyword-based intent classification as fallback"""
        message_lower = message.lower()

        # Intent keywords
        if any(word in message_lower for word in ["cuánto", "costo", "precio", "tasa", "tarifa"]):
            return {"intent": "calculate", "confidence": 0.6}
        elif any(word in message_lower for word in ["documentos", "requisitos", "necesito"]):
            return {"intent": "document", "confidence": 0.6}
        elif any(word in message_lower for word in ["cómo", "pasos", "proceso", "procedimiento"]):
            return {"intent": "guide", "confidence": 0.6}
        elif any(word in message_lower for word in ["estado", "trámite", "pago"]):
            return {"intent": "status", "confidence": 0.6}
        else:
            return {"intent": "search", "confidence": 0.5}


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

gemini_service = GeminiService()
