// src/format-utils.ts
/**
 * Format a number as currency
 * @param amount - Amount to format
 * @param currency - Currency code (default: USD)
 * @param options - Additional formatting options
 * @returns Formatted currency string
 */
export function formatCurrency(amount, currency = 'USD', options = {}) {
    return new Intl.NumberFormat('en-US', Object.assign({ style: 'currency', currency }, options)).format(amount);
}
/**
 * Format a number with thousands separators
 * @param num - Number to format
 * @param options - Additional formatting options
 * @returns Formatted number string
 */
export function formatNumber(num, options = {}) {
    return new Intl.NumberFormat('en-US', options).format(num);
}
/**
 * Format a percentage
 * @param value - Value to format as percentage (0.5 = 50%)
 * @param decimals - Number of decimal places
 * @returns Formatted percentage string
 */
export function formatPercentage(value, decimals = 2) {
    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}
/**
 * Format file size in human readable format
 * @param bytes - Size in bytes
 * @param decimals - Number of decimal places
 * @returns Formatted size string
 */
export function formatFileSize(bytes, decimals = 2) {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}
/**
 * Truncate text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @param suffix - Suffix to add when truncated
 * @returns Truncated text
 */
export function truncateText(text, maxLength, suffix = '...') {
    if (text.length <= maxLength)
        return text;
    return text.substring(0, maxLength - suffix.length) + suffix;
}
/**
 * Capitalize first letter of each word
 * @param text - Text to capitalize
 * @returns Capitalized text
 */
export function toTitleCase(text) {
    return text.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
}
/**
 * Convert camelCase to kebab-case
 * @param text - Text to convert
 * @returns kebab-case text
 */
export function toKebabCase(text) {
    return text.replace(/([a-z0-9]|(?=[A-Z]))([A-Z])/g, '$1-$2').toLowerCase();
}
/**
 * Convert text to camelCase
 * @param text - Text to convert
 * @returns camelCase text
 */
export function toCamelCase(text) {
    return text.replace(/[-_\s]+(.)?/g, (_, char) => char ? char.toUpperCase() : '');
}
