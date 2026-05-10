'use client'

/**
 * Account Deletion Request Page (Public)
 *
 * Required by Google Play Console "Account deletion" policy (since 2023):
 * a public URL — accessible WITHOUT login — that explains how a user can
 * request deletion of their account and the data associated with it.
 *
 * URL: /[locale]/legal/account-deletion (es | fr | en)
 *
 * The page describes:
 *   1. In-app procedure (mobile + web).
 *   2. Web procedure for users who still have credentials.
 *   3. Email procedure (fallback when the user lost access to the app).
 *   4. Data lifecycle (immediate soft-delete + 30-day grace + final purge).
 *   5. Data categories purged vs retained for legal/fiscal reasons.
 *   6. Contact information.
 *
 * RGPD reference: art. 17 — "right to erasure".
 */

import { useTranslations, useLocale } from 'next-intl'
import { Trash2, Smartphone, Globe, Mail, Clock, ShieldCheck, AlertTriangle, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function AccountDeletionPage() {
  const t = useTranslations('legalPages')
  const locale = useLocale()

  const inAppSteps = [
    t('accountDeletion.steps.openApp'),
    t('accountDeletion.steps.openProfile'),
    t('accountDeletion.steps.dangerZone'),
    t('accountDeletion.steps.confirmPassword'),
    t('accountDeletion.steps.typeDelete'),
    t('accountDeletion.steps.confirmFinal'),
  ]

  const dataPurged = [
    t('accountDeletion.purged.profile'),
    t('accountDeletion.purged.contact'),
    t('accountDeletion.purged.preferences'),
    t('accountDeletion.purged.documents'),
    t('accountDeletion.purged.sessions'),
    t('accountDeletion.purged.notifications'),
  ]

  const dataRetained = [
    t('accountDeletion.retained.fiscalRecords'),
    t('accountDeletion.retained.payments'),
    t('accountDeletion.retained.auditLogs'),
    t('accountDeletion.retained.legalObligations'),
  ]

  return (
    <div className="container mx-auto max-w-4xl px-4 py-12">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <Trash2 className="h-8 w-8 text-destructive" />
        <h1 className="text-3xl font-bold">{t('accountDeletion.title')}</h1>
      </div>
      <p className="text-muted-foreground mb-2">{t('accountDeletion.lastUpdated')}</p>
      <p className="text-lg mb-10">{t('accountDeletion.intro')}</p>

      {/* Important banner */}
      <div className="mb-10 p-4 rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40 flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-sm text-amber-800 dark:text-amber-200 space-y-1">
          <p className="font-semibold">{t('accountDeletion.warning.title')}</p>
          <p>{t('accountDeletion.warning.body')}</p>
        </div>
      </div>

      {/* Section 1: In-app deletion (mobile) */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Smartphone className="h-5 w-5 text-primary" />
          1. {t('accountDeletion.fromMobileTitle')}
        </h2>
        <p className="text-muted-foreground mb-4">
          {t('accountDeletion.fromMobileIntro')}
        </p>
        <ol className="space-y-2 ml-4">
          {inAppSteps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex-shrink-0 h-6 w-6 rounded-full bg-primary/10 text-primary text-sm font-semibold flex items-center justify-center">
                {i + 1}
              </span>
              <span className="text-foreground/80">{step}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* Section 2: Web deletion */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-primary" />
          2. {t('accountDeletion.fromWebTitle')}
        </h2>
        <p className="text-muted-foreground mb-4">
          {t('accountDeletion.fromWebIntro')}
        </p>
        <Link
          href={`/${locale}/auth`}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium"
        >
          {t('accountDeletion.fromWebCta')}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>

      {/* Section 3: Email procedure */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Mail className="h-5 w-5 text-primary" />
          3. {t('accountDeletion.fromEmailTitle')}
        </h2>
        <p className="text-muted-foreground mb-4">
          {t('accountDeletion.fromEmailIntro')}
        </p>
        <div className="p-4 rounded-lg bg-muted/50 border border-border space-y-2 text-sm">
          <p>
            <strong>{t('accountDeletion.emailToLabel')}:</strong>{' '}
            <a href="mailto:facilege26@gmail.com?subject=Solicitud%20de%20eliminacion%20de%20cuenta" className="text-primary hover:underline">
              facilege26@gmail.com
            </a>
          </p>
          <p>
            <strong>{t('accountDeletion.emailSubjectLabel')}:</strong>{' '}
            <code className="px-2 py-0.5 bg-background rounded">
              {t('accountDeletion.emailSubjectValue')}
            </code>
          </p>
          <div>
            <strong>{t('accountDeletion.emailBodyLabel')}:</strong>
            <pre className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground bg-background p-3 rounded border">
{t('accountDeletion.emailBodyTemplate')}
            </pre>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-3">
          {t('accountDeletion.emailResponseTime')}
        </p>
      </section>

      {/* Section 4: Data lifecycle */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-primary" />
          4. {t('accountDeletion.lifecycleTitle')}
        </h2>
        <div className="space-y-4 text-foreground/80">
          <div className="flex gap-3">
            <span className="flex-shrink-0 h-6 w-6 rounded-full bg-destructive/10 text-destructive text-xs font-semibold flex items-center justify-center mt-0.5">
              T+0
            </span>
            <p>{t('accountDeletion.lifecycle.immediate')}</p>
          </div>
          <div className="flex gap-3">
            <span className="flex-shrink-0 h-6 w-6 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-semibold flex items-center justify-center mt-0.5">
              30j
            </span>
            <p>{t('accountDeletion.lifecycle.gracePeriod')}</p>
          </div>
          <div className="flex gap-3">
            <span className="flex-shrink-0 h-6 w-6 rounded-full bg-muted text-muted-foreground text-xs font-semibold flex items-center justify-center mt-0.5">
              T+30
            </span>
            <p>{t('accountDeletion.lifecycle.finalPurge')}</p>
          </div>
        </div>
      </section>

      {/* Section 5: Data categories */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          5. {t('accountDeletion.dataCategoriesTitle')}
        </h2>

        <div className="grid md:grid-cols-2 gap-4">
          {/* Purged */}
          <div className="p-4 rounded-lg border border-destructive/30 bg-destructive/5">
            <h3 className="font-semibold mb-3 text-destructive flex items-center gap-2">
              <Trash2 className="h-4 w-4" />
              {t('accountDeletion.purgedTitle')}
            </h3>
            <ul className="space-y-1.5 text-sm text-foreground/80">
              {dataPurged.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-destructive">×</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Retained */}
          <div className="p-4 rounded-lg border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20">
            <h3 className="font-semibold mb-3 text-amber-700 dark:text-amber-300 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              {t('accountDeletion.retainedTitle')}
            </h3>
            <ul className="space-y-1.5 text-sm text-foreground/80">
              {dataRetained.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-amber-600">⚖</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground">
              {t('accountDeletion.retainedNote')}
            </p>
          </div>
        </div>
      </section>

      {/* Section 6: Legal & contact */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4">
          6. {t('accountDeletion.legalTitle')}
        </h2>
        <p className="text-muted-foreground leading-relaxed">
          {t('accountDeletion.legalContent')}
        </p>
        <div className="mt-4 p-4 rounded-lg bg-muted/50 border border-border text-sm">
          <p><strong>Facil — Plataforma Digital AI de Tramites</strong></p>
          <p className="text-muted-foreground">Malabo II — Guinea Ecuatorial</p>
          <p className="text-muted-foreground">
            <a href="mailto:facilege26@gmail.com" className="text-primary hover:underline">
              facilege26@gmail.com
            </a>
            {' · '}
            <a href="tel:+240222574494" className="text-primary hover:underline">
              +240 222 574 494
            </a>
          </p>
        </div>
      </section>

      {/* Footer with locale switch links */}
      <div className="border-t pt-6 mt-12 flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span>{t('accountDeletion.languageLabel')}:</span>
        <Link href="/es/legal/account-deletion" className="hover:text-primary hover:underline">Español</Link>
        <Link href="/fr/legal/account-deletion" className="hover:text-primary hover:underline">Français</Link>
        <Link href="/en/legal/account-deletion" className="hover:text-primary hover:underline">English</Link>
      </div>
    </div>
  )
}
