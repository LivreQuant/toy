// src/validation-utils.ts
/**
 * Validate email format
 * @param email - Email to validate
 * @returns True if email is valid
 */
export function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}
/**
 * Validate URL format
 * @param url - URL to validate
 * @returns True if URL is valid
 */
export function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    }
    catch (_a) {
        return false;
    }
}
/**
 * Validate phone number (basic US format)
 * @param phone - Phone number to validate
 * @returns True if phone number is valid
 */
export function isValidPhoneNumber(phone) {
    const phoneRegex = /^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$/;
    return phoneRegex.test(phone);
}
/**
 * Check if string contains only numbers
 * @param str - String to check
 * @returns True if string is numeric
 */
export function isNumeric(str) {
    return !isNaN(Number(str)) && !isNaN(parseFloat(str));
}
/**
 * Check if value is empty (null, undefined, empty string, empty array)
 * @param value - Value to check
 * @returns True if value is empty
 */
export function isEmpty(value) {
    if (value == null)
        return true;
    if (typeof value === 'string')
        return value.trim() === '';
    if (Array.isArray(value))
        return value.length === 0;
    if (typeof value === 'object')
        return Object.keys(value).length === 0;
    return false;
}
/**
 * Validate password strength
 * @param password - Password to validate
 * @returns Object with validation results
 */
export function validatePassword(password) {
    const feedback = [];
    let score = 0;
    if (password.length >= 8) {
        score += 1;
    }
    else {
        feedback.push('Password must be at least 8 characters long');
    }
    if (/[a-z]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('Password must contain at least one lowercase letter');
    }
    if (/[A-Z]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('Password must contain at least one uppercase letter');
    }
    if (/\d/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('Password must contain at least one number');
    }
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('Password must contain at least one special character');
    }
    return {
        isValid: score >= 4,
        score,
        feedback
    };
}
/**
 * Sanitize string for safe HTML insertion
 * @param str - String to sanitize
 * @returns Sanitized string
 */
export function sanitizeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
