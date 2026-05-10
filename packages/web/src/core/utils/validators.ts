/**
 * Validation Utilities
 * Common validation functions
 */

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate phone number (Equatorial Guinea format)
 * Format: (222|555|551|333) + 6 digits = 9 total
 */
export function isValidPhone(phone: string): boolean {
  const phoneRegex = /^(222|555|551|333)\d{6}$/;
  return phoneRegex.test(phone);
}

/**
 * Validate NIF/CIF (Tax ID - Equatorial Guinea)
 * Format: 8-9 alphanumeric characters
 */
export function isValidNIF(nif: string): boolean {
  const nifRegex = /^[A-Z0-9]{8,9}$/;
  return nifRegex.test(nif.toUpperCase());
}

/**
 * Validate password strength
 */
export function isStrongPassword(password: string): boolean {
  // Minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 number, 1 special character
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);

  return hasMinLength && hasUppercase && hasLowercase && hasNumber && hasSpecial;
}

/**
 * Get password strength score (0-4)
 */
export function getPasswordStrength(password: string): number {
  let strength = 0;

  if (password.length >= 8) strength++;
  if (/[A-Z]/.test(password)) strength++;
  if (/[a-z]/.test(password)) strength++;
  if (/[0-9]/.test(password)) strength++;
  if (/[^A-Za-z0-9]/.test(password)) strength++;

  return Math.min(strength, 4);
}

/**
 * Sanitize user input (basic XSS prevention)
 */
export function sanitizeInput(input: string): string {
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Check if string is empty or only whitespace
 */
export function isEmpty(str: string): boolean {
  return !str || str.trim().length === 0;
}
