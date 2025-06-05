/**
 * Validate email format
 * @param email - Email to validate
 * @returns True if email is valid
 */
export declare function isValidEmail(email: string): boolean;
/**
 * Validate URL format
 * @param url - URL to validate
 * @returns True if URL is valid
 */
export declare function isValidUrl(url: string): boolean;
/**
 * Validate phone number (basic US format)
 * @param phone - Phone number to validate
 * @returns True if phone number is valid
 */
export declare function isValidPhoneNumber(phone: string): boolean;
/**
 * Check if string contains only numbers
 * @param str - String to check
 * @returns True if string is numeric
 */
export declare function isNumeric(str: string): boolean;
/**
 * Check if value is empty (null, undefined, empty string, empty array)
 * @param value - Value to check
 * @returns True if value is empty
 */
export declare function isEmpty(value: any): boolean;
/**
 * Validate password strength
 * @param password - Password to validate
 * @returns Object with validation results
 */
export declare function validatePassword(password: string): {
    isValid: boolean;
    score: number;
    feedback: string[];
};
/**
 * Sanitize string for safe HTML insertion
 * @param str - String to sanitize
 * @returns Sanitized string
 */
export declare function sanitizeHtml(str: string): string;
