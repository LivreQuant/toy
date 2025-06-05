// src/date-utils.ts
/**
 * Format a date for display
 * @param date - Date to format
 * @param options - Intl.DateTimeFormat options
 * @returns Formatted date string
 */
export function formatDate(date, options = {}) {
    const dateObj = typeof date === 'string' || typeof date === 'number'
        ? new Date(date)
        : date;
    return new Intl.DateTimeFormat('en-US', Object.assign({ year: 'numeric', month: 'short', day: 'numeric' }, options)).format(dateObj);
}
/**
 * Format a timestamp for display with time
 * @param timestamp - Timestamp to format
 * @param options - Additional formatting options
 * @returns Formatted timestamp string
 */
export function formatTimestamp(timestamp, options = {}) {
    return formatDate(timestamp, Object.assign({ hour: '2-digit', minute: '2-digit', second: '2-digit' }, options));
}
/**
 * Get relative time string (e.g., "2 minutes ago")
 * @param date - Date to compare
 * @param baseDate - Base date to compare against (defaults to now)
 * @returns Relative time string
 */
export function getRelativeTime(date, baseDate = new Date()) {
    const dateObj = typeof date === 'string' || typeof date === 'number'
        ? new Date(date)
        : date;
    const diffMs = baseDate.getTime() - dateObj.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffSeconds < 60) {
        return 'just now';
    }
    else if (diffMinutes < 60) {
        return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    }
    else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    }
    else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    }
    else {
        return formatDate(dateObj);
    }
}
/**
 * Check if a date is today
 * @param date - Date to check
 * @returns True if the date is today
 */
export function isToday(date) {
    const dateObj = typeof date === 'string' || typeof date === 'number'
        ? new Date(date)
        : date;
    const today = new Date();
    return dateObj.toDateString() === today.toDateString();
}
/**
 * Get the start of day for a given date
 * @param date - Date to get start of day for
 * @returns Date object representing start of day
 */
export function getStartOfDay(date) {
    const dateObj = typeof date === 'string' || typeof date === 'number'
        ? new Date(date)
        : new Date(date);
    dateObj.setHours(0, 0, 0, 0);
    return dateObj;
}
/**
 * Get the end of day for a given date
 * @param date - Date to get end of day for
 * @returns Date object representing end of day
 */
export function getEndOfDay(date) {
    const dateObj = typeof date === 'string' || typeof date === 'number'
        ? new Date(date)
        : new Date(date);
    dateObj.setHours(23, 59, 59, 999);
    return dateObj;
}
/**
 * Parse a date string safely
 * @param dateString - String to parse
 * @returns Date object or null if parsing fails
 */
export function parseDate(dateString) {
    try {
        const date = new Date(dateString);
        return isNaN(date.getTime()) ? null : date;
    }
    catch (_a) {
        return null;
    }
}
