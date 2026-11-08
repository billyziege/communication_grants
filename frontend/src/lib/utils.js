/**
 * Utility helpers for the communication grants frontend.
 */

/**
 * cn() — combines class names, filtering out falsy values.
 * Lightweight alternative to clsx/twMerge for this project.
 */
export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

/**
 * Format a funding amount using Intl.NumberFormat.
 * Returns null if amount is null/undefined.
 */
export function formatFunding(amount, currency) {
  if (amount == null) return null;
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency ?? 'USD',
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    // Fallback for unknown currency codes
    return `${currency ?? ''} ${amount.toLocaleString()}`.trim();
  }
}

/**
 * Format an ISO date string to a year string.
 * Returns null if isoDate is null/undefined.
 */
export function formatYear(isoDate) {
  if (!isoDate) return null;
  return isoDate.slice(0, 4);
}

/**
 * Convert a snake_case key to Title Case.
 * e.g. "source_id" -> "Source Id"
 */
export function snakeToTitle(key) {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
