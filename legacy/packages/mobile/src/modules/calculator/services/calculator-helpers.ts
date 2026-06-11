/**
 * Calculator helpers — pure functions ported from web
 * `calculateur/page.tsx`.
 *
 * IMPORTANT: `evaluateFormula` uses a recursive-descent parser instead of
 * `eval()` to remain XSS/injection-safe. The token regex is intentionally
 * strict — DO NOT relax it without a security review.
 */

// ---------------------------------------------------------------------------
// Number parsing
// ---------------------------------------------------------------------------

/**
 * Strip non-numeric characters (except dot and minus) and parse to float.
 * Returns 0 on empty/invalid input.
 */
export function parseNumberInput(value: string): number {
  const cleaned = value.replace(/[^\d.-]/g, '');
  const parsed = Number.parseFloat(cleaned);
  return Number.isNaN(parsed) ? 0 : parsed;
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

/**
 * Format a number as XAF currency using the user's locale.
 * Hermes 0.76+ on Expo SDK 54 ships full ICU support so this is safe.
 */
export function formatCurrencyValue(value: number, locale: string): string {
  return (
    new Intl.NumberFormat(locale, {
      style: 'decimal',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value) + ' XAF'
  );
}

export function formatPercent(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(value / 100);
}

// ---------------------------------------------------------------------------
// Safe formula evaluation
// ---------------------------------------------------------------------------

/**
 * Substitute variables into a formula and evaluate it safely.
 * Returns `null` on any error, invalid character, division-by-zero, etc.
 *
 * Supports: `+ - * /`, parentheses, decimals, unary minus.
 */
export function evaluateFormula(
  formula: string,
  variables: Record<string, number>
): number | null {
  try {
    let evalFormula = formula;
    for (const [key, val] of Object.entries(variables)) {
      const regex = new RegExp(`\\b${key}\\b`, 'g');
      evalFormula = evalFormula.replace(regex, String(val));
    }

    // Whitelist: only digits, whitespace, operators, parentheses, dot.
    const safePattern = /^[\d\s+\-*/().]+$/;
    if (!safePattern.test(evalFormula)) {
      return null;
    }

    const result = safeEval(evalFormula);
    return typeof result === 'number' && Number.isFinite(result) ? result : null;
  } catch {
    return null;
  }
}

/**
 * Recursive-descent parser for arithmetic expressions.
 * Replaces `eval()`. Throws on malformed input — callers should wrap in try/catch
 * (which `evaluateFormula` does).
 */
function safeEval(expr: string): number {
  const matched = expr.match(/(\d+\.?\d*|[+\-*/()])/g);
  if (!matched) throw new Error('Invalid expression');
  const tokens: string[] = matched;
  let pos = 0;

  const peek = (): string | undefined => tokens[pos];
  const consume = (): string => tokens[pos++];

  function parseExpr(): number {
    let left = parseTerm();
    while (peek() === '+' || peek() === '-') {
      const op = consume();
      const right = parseTerm();
      left = op === '+' ? left + right : left - right;
    }
    return left;
  }

  function parseTerm(): number {
    let left = parseFactor();
    while (peek() === '*' || peek() === '/') {
      const op = consume();
      const right = parseFactor();
      if (op === '/' && right === 0) throw new Error('Division by zero');
      left = op === '*' ? left * right : left / right;
    }
    return left;
  }

  function parseFactor(): number {
    if (peek() === '(') {
      consume(); // (
      const val = parseExpr();
      if (peek() !== ')') throw new Error('Missing closing parenthesis');
      consume(); // )
      return val;
    }
    if (peek() === '-') {
      consume();
      return -parseFactor();
    }
    const token = consume();
    const num = Number.parseFloat(token);
    if (Number.isNaN(num)) throw new Error('Invalid number');
    return num;
  }

  const result = parseExpr();
  if (pos < tokens.length) throw new Error('Unexpected token');
  return result;
}
