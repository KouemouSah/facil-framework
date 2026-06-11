/**
 * Bundle workflow — error catalog.
 *
 * Maps backend metier codes (bundle_workflow_routes.py _error_messages)
 * to a user-facing title + hint + CTA (retry / back / support / inline).
 *
 * Any code not in this catalog falls through to the generic fallback.
 * The title and hint are localized es/fr/en; the actionable `message`
 * comes from the backend StructuredApiError (already localized).
 *
 * Plan: .claude/plans/BUNDLE_DEBUG_PHASE3_PLAN.md §2.5
 */

export type BundleErrorCtaType = 'retry' | 'back' | 'support' | 'inline' | 'none' | 'view_request'

export interface BundleErrorCatalogEntry {
  /** Short title shown above the message */
  title: { es: string; fr: string; en: string }
  /** Optional hint explaining the recovery path */
  hint: { es: string; fr: string; en: string } | null
  /** Recommended user action */
  cta: BundleErrorCtaType
  /** Cooldown in ms before retry is allowed (only applies to cta=retry) */
  retryCooldownMs?: number
}

export const BUNDLE_ERROR_CATALOG: Record<string, BundleErrorCatalogEntry> = {
  // ── 409 — race conditions ─────────────────────────────────────
  PAYMENT_ALREADY_IN_PROGRESS: {
    title: {
      es: 'Pago ya registrado',
      fr: 'Paiement déjà enregistré',
      en: 'Payment already registered',
    },
    hint: {
      es: 'Su pago ya fue registrado exitosamente. Puede consultar el estado de su solicitud.',
      fr: 'Votre paiement a déjà été enregistré avec succès. Vous pouvez consulter l\'état de votre demande.',
      en: 'Your payment has already been registered successfully. You can check the status of your request.',
    },
    cta: 'view_request',
    retryCooldownMs: 0,
  },
  OBLIGATION_RACE_CONDITION: {
    title: {
      es: 'Obligaciones bloqueadas',
      fr: 'Obligations verrouillées',
      en: 'Obligations locked',
    },
    hint: {
      es: 'Otro usuario está pagando estas obligaciones. Reintente en unos segundos.',
      fr: 'Un autre utilisateur paie ces obligations. Réessayez dans quelques secondes.',
      en: 'Another user is paying these obligations. Retry in a few seconds.',
    },
    cta: 'retry',
    retryCooldownMs: 3000,
  },
  LICENSE_ALREADY_COMPLETE: {
    title: {
      es: 'Ya pagado',
      fr: 'Déjà réglé',
      en: 'Already paid',
    },
    hint: {
      es: 'Todas las obligaciones de este año fiscal ya están pagadas.',
      fr: 'Toutes les obligations de cet exercice sont déjà payées.',
      en: 'All obligations for this fiscal year are already paid.',
    },
    cta: 'back',
  },

  // ── 404 — not found ───────────────────────────────────────────
  LICENSE_NOT_FOUND: {
    title: {
      es: 'Licencia no encontrada',
      fr: 'Licence introuvable',
      en: 'License not found',
    },
    hint: null,
    cta: 'back',
  },
  COMPANY_NOT_FOUND: {
    title: {
      es: 'Empresa no encontrada',
      fr: 'Entreprise introuvable',
      en: 'Company not found',
    },
    hint: null,
    cta: 'back',
  },

  // ── 403 — forbidden ───────────────────────────────────────────
  LICENSE_SUSPENDED: {
    title: {
      es: 'Licencia suspendida',
      fr: 'Licence suspendue',
      en: 'License suspended',
    },
    hint: {
      es: 'Su licencia está suspendida. Contacte la administración para más información.',
      fr: 'Votre licence est suspendue. Contactez l\'administration pour plus d\'informations.',
      en: 'Your license is suspended. Contact the administration for more information.',
    },
    cta: 'support',
  },

  // ── 422 — business validation ─────────────────────────────────
  LICENSE_NOT_PAYABLE: {
    title: {
      es: 'Licencia no pagable',
      fr: 'Licence non payable',
      en: 'License not payable',
    },
    hint: {
      es: 'El estado actual de la licencia no permite el pago.',
      fr: 'Le statut actuel de la licence ne permet pas le paiement.',
      en: 'The current license status does not allow payment.',
    },
    cta: 'back',
  },
  NO_PAYABLE_OBLIGATIONS: {
    title: {
      es: 'Sin obligaciones pendientes',
      fr: 'Aucune obligation en attente',
      en: 'No pending obligations',
    },
    hint: null,
    cta: 'back',
  },
  NO_OBLIGATIONS_SELECTED: {
    title: {
      es: 'Selección vacía',
      fr: 'Sélection vide',
      en: 'Empty selection',
    },
    hint: {
      es: 'En Modo A, debe seleccionar al menos una obligación.',
      fr: 'En Mode A, vous devez sélectionner au moins une obligation.',
      en: 'In Mode A, you must select at least one obligation.',
    },
    cta: 'inline',
  },
  INVALID_PROCESSING_MODE: {
    title: {
      es: 'Modo inválido',
      fr: 'Mode invalide',
      en: 'Invalid mode',
    },
    hint: null,
    cta: 'back',
  },
  INVALID_PAYMENT_METHOD: {
    title: {
      es: 'Método de pago no soportado',
      fr: 'Méthode de paiement non supportée',
      en: 'Payment method not supported',
    },
    hint: null,
    cta: 'inline',
  },
  PHONE_REQUIRED: {
    title: {
      es: 'Teléfono requerido',
      fr: 'Téléphone requis',
      en: 'Phone number required',
    },
    hint: {
      es: 'Formato: +240 XXX XXX XXX',
      fr: 'Format : +240 XXX XXX XXX',
      en: 'Format: +240 XXX XXX XXX',
    },
    cta: 'inline',
  },

  // ── 503 — external gateway ────────────────────────────────────
  PAYMENT_INITIATION_FAILED: {
    title: {
      es: 'Pasarela de pago no disponible',
      fr: 'Passerelle de paiement indisponible',
      en: 'Payment gateway unavailable',
    },
    hint: {
      es: 'No pudimos conectar con BANGE. Reintente en unos minutos.',
      fr: 'Impossible de se connecter à BANGE. Réessayez dans quelques minutes.',
      en: 'Could not connect to BANGE. Retry in a few minutes.',
    },
    cta: 'retry',
    retryCooldownMs: 10000,
  },

  // ── 500 — server / integrity (should contact support) ────────
  BUNDLE_SR_MISSING_LICENSE_ID: {
    title: {
      es: 'Error interno',
      fr: 'Erreur interne',
      en: 'Internal error',
    },
    hint: {
      es: 'La solicitud no está vinculada a una licencia. Contacte el soporte.',
      fr: 'La demande n\'est pas liée à une licence. Contactez le support.',
      en: 'The request is not linked to a license. Contact support.',
    },
    cta: 'support',
  },
  BUNDLE_SR_MISSING_FISCAL_YEAR: {
    title: {
      es: 'Error interno',
      fr: 'Erreur interne',
      en: 'Internal error',
    },
    hint: {
      es: 'Falta el año fiscal. Contacte el soporte.',
      fr: 'Année fiscale manquante. Contactez le support.',
      en: 'Missing fiscal year. Contact support.',
    },
    cta: 'support',
  },
  BUNDLE_INTEGRITY_ERROR: {
    title: {
      es: 'Error de integridad',
      fr: 'Erreur d\'intégrité',
      en: 'Integrity error',
    },
    hint: {
      es: 'La solicitud no cumple con las reglas del paquete. Contacte el soporte.',
      fr: 'La demande ne respecte pas les règles du forfait. Contactez le support.',
      en: 'The request does not meet bundle rules. Contact support.',
    },
    cta: 'support',
  },
  DATABASE_CONSTRAINT_VIOLATION: {
    title: {
      es: 'Conflicto de datos',
      fr: 'Conflit de données',
      en: 'Data conflict',
    },
    hint: {
      es: 'La operación viola una regla de la base de datos. Contacte el soporte.',
      fr: 'L\'opération viole une règle de la base de données. Contactez le support.',
      en: 'The operation violates a database rule. Contact support.',
    },
    cta: 'support',
  },

  // ── Client-side synthetic codes ───────────────────────────────
  NETWORK_ERROR: {
    title: {
      es: 'Sin conexión',
      fr: 'Pas de connexion',
      en: 'No connection',
    },
    hint: {
      es: 'Verifique su red y reintente.',
      fr: 'Vérifiez votre réseau et réessayez.',
      en: 'Check your network and retry.',
    },
    cta: 'retry',
    retryCooldownMs: 2000,
  },
  UNKNOWN_ERROR: {
    title: {
      es: 'Error inesperado',
      fr: 'Erreur inattendue',
      en: 'Unexpected error',
    },
    hint: {
      es: 'Reintente o contacte el soporte si el problema persiste.',
      fr: 'Réessayez ou contactez le support si le problème persiste.',
      en: 'Retry or contact support if the problem persists.',
    },
    cta: 'retry',
    retryCooldownMs: 3000,
  },
}

/**
 * Fallback entry used when an unknown code comes from the backend.
 * Guarantees the UI never renders an empty state.
 */
export const BUNDLE_ERROR_FALLBACK: BundleErrorCatalogEntry = BUNDLE_ERROR_CATALOG.UNKNOWN_ERROR

export function getBundleErrorEntry(code: string): BundleErrorCatalogEntry {
  return BUNDLE_ERROR_CATALOG[code] ?? BUNDLE_ERROR_FALLBACK
}
