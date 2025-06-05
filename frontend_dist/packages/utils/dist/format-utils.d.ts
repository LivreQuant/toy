/**
 * Format a number as currency
 * @param amount - Amount to format
 * @param currency - Currency code (default: USD)
 * @param options - Additional formatting options
 * @returns Formatted currency string
 */
export declare function formatCurrency(amount: number, currency?: string, options?: Intl.NumberFormatOptions): string;
/**
 * Format a number with thousands separators
 * @param num - Number to format
 * @param options - Additional formatting options
 * @returns Formatted number string
 */
export declare function formatNumber(num: number, options?: Intl.NumberFormatOptions): string;
/**
 * Format a percentage
 * @param value - Value to format as percentage (0.5 = 50%)
 * @param decimals - Number of decimal places
 * @returns Formatted percentage string
 */
export declare function formatPercentage(value: number, decimals?: number): string;
/**
 * Format file size in human readable format
 * @param bytes - Size in bytes
 * @param decimals - Number of decimal places
 * @returns Formatted size string
 */
export declare function formatFileSize(bytes: number, decimals?: number): string;
/**
 * Truncate text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @param suffix - Suffix to add when truncated
 * @returns Truncated text
 */
export declare function truncateText(text: string, maxLength: number, suffix?: string): string;
/**
 * Capitalize first letter of each word
 * @param text - Text to capitalize
 * @returns Capitalized text
 */
export declare function toTitleCase(text: string): string;
/**
 * Convert camelCase to kebab-case
 * @param text - Text to convert
 * @returns kebab-case text
 */
export declare function toKebabCase(text: string): string;
/**
 * Convert text to camelCase
 * @param text - Text to convert
 * @returns camelCase text
 */
export declare function toCamelCase(text: string): string;
