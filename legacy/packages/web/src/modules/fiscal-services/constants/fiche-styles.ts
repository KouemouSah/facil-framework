/**
 * Shared print styles for Fiche TESORO PÚBLICO
 * Used by both detail and edit pages for service bundles.
 */
export const FICHE_PRINT_STYLES = `
  body { font-family: 'Times New Roman', serif; margin: 2cm; color: #000; }
  table { width: 100%; border-collapse: collapse; margin: 1em 0; }
  th, td { border: 1px solid #000; padding: 6px 10px; font-size: 11px; }
  th { background: #1a365d; color: white; text-align: left; }
  .total-row { background: #e2e8f0; font-weight: bold; font-size: 12px; }
  .header { text-align: center; margin-bottom: 1.5em; }
  .header h1 { font-size: 16px; margin: 0; letter-spacing: 2px; }
  .header h2 { font-size: 12px; margin: 4px 0; font-weight: normal; }
  .meta { display: flex; justify-content: space-between; margin: 1em 0; font-size: 11px; }
  .footer { margin-top: 2em; font-size: 10px; color: #666; text-align: center; border-top: 1px solid #ccc; padding-top: 1em; }
  @media print { body { margin: 1cm; } }
`
