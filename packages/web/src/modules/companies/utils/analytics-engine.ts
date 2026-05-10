/**
 * Analytics Engine — Heuristic forecasting & risk classification
 *
 * Pure TypeScript, no backend dependency. Uses monthly_trend and top_debtors
 * from CompanyAnalytics to compute projections and risk scores.
 */

import type { CompanyAnalytics } from '../types'

type MonthData = CompanyAnalytics['monthly_trend'][number]
type DebtorData = CompanyAnalytics['top_debtors'][number]

// =============================================================================
// LINEAR REGRESSION (simple least squares)
// =============================================================================

function linearRegression(values: number[]): { slope: number; intercept: number; r2: number } {
  const n = values.length
  if (n < 2) return { slope: 0, intercept: values[0] ?? 0, r2: 0 }

  const xs = values.map((_, i) => i)
  const xMean = xs.reduce((a, b) => a + b, 0) / n
  const yMean = values.reduce((a, b) => a + b, 0) / n

  let ssXY = 0, ssXX = 0, ssTot = 0, ssRes = 0
  for (let i = 0; i < n; i++) {
    ssXY += (xs[i] - xMean) * (values[i] - yMean)
    ssXX += (xs[i] - xMean) ** 2
  }

  const slope = ssXX > 0 ? ssXY / ssXX : 0
  const intercept = yMean - slope * xMean

  for (let i = 0; i < n; i++) {
    const predicted = intercept + slope * i
    ssRes += (values[i] - predicted) ** 2
    ssTot += (values[i] - yMean) ** 2
  }

  return { slope, intercept, r2: ssTot > 0 ? 1 - ssRes / ssTot : 0 }
}

// =============================================================================
// PROJECTIONS
// =============================================================================

export interface Projection {
  label: string       // "2026-04", "2026-05", etc.
  value: number       // projected value
  isProjection: true
}

/**
 * Project future months using linear regression on historical data.
 * @param trend - monthly_trend array from analytics
 * @param field - which field to project ('created', 'verified', 'bundle')
 * @param months - how many months to project (3, 6, 12)
 */
export function projectTrend(
  trend: MonthData[],
  field: 'created' | 'verified' | 'bundle',
  months: number,
): { historical: { label: string; value: number }[]; projected: Projection[]; slope: number; r2: number } {
  const values = trend.map(m => m[field])
  const { slope, intercept, r2 } = linearRegression(values)

  const historical = trend.map(m => ({ label: m.month, value: m[field] }))

  // Generate future month labels
  const lastMonth = trend[trend.length - 1].month // "2026-03"
  const [y, mo] = lastMonth.split('-').map(Number)
  const projected: Projection[] = []
  for (let i = 1; i <= months; i++) {
    const futureMonth = mo + i
    const futureYear = y + Math.floor((futureMonth - 1) / 12)
    const futureMonthNum = ((futureMonth - 1) % 12) + 1
    projected.push({
      label: `${futureYear}-${String(futureMonthNum).padStart(2, '0')}`,
      value: Math.max(0, Math.round(intercept + slope * (values.length - 1 + i))),
      isProjection: true,
    })
  }

  return { historical, projected, slope, r2 }
}

// =============================================================================
// RISK CLASSIFICATION
// =============================================================================

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low'

export interface ClassifiedDebtor extends DebtorData {
  risk: RiskLevel
  riskScore: number       // 0-100 (higher = worse)
  neverPaid: boolean      // 0% recovery with debt
}

export function classifyDebtors(debtors: DebtorData[]): ClassifiedDebtor[] {
  if (!debtors?.length) return []
  const maxDebt = Math.max(...debtors.map(d => d.debt), 1)

  return debtors.map(d => {
    // Composite risk score (0-100):
    // 40% weight on recovery_pct (inverted — low recovery = high risk)
    // 40% weight on debt relative to max
    // 20% weight on having 0% recovery (never paid flag)
    const recoveryRisk = Math.max(0, 100 - d.recovery_pct) * 0.4
    const debtRisk = (d.debt / maxDebt) * 100 * 0.4
    const neverPaidRisk = d.recovery_pct === 0 && d.debt > 0 ? 20 : 0
    const riskScore = Math.round(recoveryRisk + debtRisk + neverPaidRisk)

    const risk: RiskLevel =
      riskScore >= 75 ? 'critical' :
      riskScore >= 50 ? 'high' :
      riskScore >= 25 ? 'medium' : 'low'

    return {
      ...d,
      risk,
      riskScore,
      neverPaid: d.recovery_pct === 0 && d.debt > 0,
    }
  }).sort((a, b) => b.riskScore - a.riskScore)
}

// =============================================================================
// CONCENTRATION RISK
// =============================================================================

export function concentrationRisk(debtors: DebtorData[], totalDebt: number): {
  top3Pct: number
  top1Pct: number
  herfindahl: number // 0-1 index, >0.25 = concentrated
} {
  if (!debtors?.length || totalDebt <= 0) return { top3Pct: 0, top1Pct: 0, herfindahl: 0 }
  const sorted = [...debtors].sort((a, b) => b.debt - a.debt)
  const top3Debt = sorted.slice(0, 3).reduce((s, d) => s + d.debt, 0)
  const top1Debt = sorted[0]?.debt ?? 0

  // Herfindahl index: sum of squared market shares
  const herfindahl = sorted.reduce((h, d) => h + (d.debt / totalDebt) ** 2, 0)

  return {
    top3Pct: Math.round((top3Debt / totalDebt) * 100),
    top1Pct: Math.round((top1Debt / totalDebt) * 100),
    herfindahl: Math.round(herfindahl * 1000) / 1000,
  }
}

// =============================================================================
// ZONE HEALTH SCORE (composite)
// =============================================================================

export function zoneHealthScore(zone: {
  recovery_rate_pct: number
  verified_companies: number
  total_companies: number
  with_nif: number
  missing_identifier: number
}): { score: number; grade: 'A' | 'B' | 'C' | 'D' | 'F' } {
  const t = zone.total_companies || 1
  const recoveryScore = Math.min(zone.recovery_rate_pct, 100) * 0.4  // 40% weight
  const verifiedScore = (zone.verified_companies / t) * 100 * 0.3     // 30% weight
  const identifierScore = ((t - zone.missing_identifier) / t) * 100 * 0.2 // 20% weight
  const nifScore = (zone.with_nif / t) * 100 * 0.1                    // 10% weight

  const score = Math.round(recoveryScore + verifiedScore + identifierScore + nifScore)
  const grade = score >= 80 ? 'A' : score >= 60 ? 'B' : score >= 40 ? 'C' : score >= 20 ? 'D' : 'F'

  return { score, grade }
}
