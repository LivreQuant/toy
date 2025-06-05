/**
 * Format a date for display
 * @param date - Date to format
 * @param options - Intl.DateTimeFormat options
 * @returns Formatted date string
 */
export declare function formatDate(date: Date | string | number, options?: Intl.DateTimeFormatOptions): string;
/**
 * Format a timestamp for display with time
 * @param timestamp - Timestamp to format
 * @param options - Additional formatting options
 * @returns Formatted timestamp string
 */
export declare function formatTimestamp(timestamp: Date | string | number, options?: Intl.DateTimeFormatOptions): string;
/**
 * Get relative time string (e.g., "2 minutes ago")
 * @param date - Date to compare
 * @param baseDate - Base date to compare against (defaults to now)
 * @returns Relative time string
 */
export declare function getRelativeTime(date: Date | string | number, baseDate?: Date): string;
/**
 * Check if a date is today
 * @param date - Date to check
 * @returns True if the date is today
 */
export declare function isToday(date: Date | string | number): boolean;
/**
 * Get the start of day for a given date
 * @param date - Date to get start of day for
 * @returns Date object representing start of day
 */
export declare function getStartOfDay(date: Date | string | number): Date;
/**
 * Get the end of day for a given date
 * @param date - Date to get end of day for
 * @returns Date object representing end of day
 */
export declare function getEndOfDay(date: Date | string | number): Date;
/**
 * Parse a date string safely
 * @param dateString - String to parse
 * @returns Date object or null if parsing fails
 */
export declare function parseDate(dateString: string): Date | null;
