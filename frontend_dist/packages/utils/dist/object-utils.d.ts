/**
 * Deep clone an object
 * @param obj - Object to clone
 * @returns Deep cloned object
 */
export declare function deepClone<T>(obj: T): T;
/**
 * Deep merge objects
 * @param target - Target object
 * @param sources - Source objects to merge
 * @returns Merged object
 */
export declare function deepMerge<T extends Record<string, any>>(target: T, ...sources: Partial<T>[]): T;
/**
 * Check if value is an object
 * @param item - Item to check
 * @returns True if item is an object
 */
export declare function isObject(item: any): item is Record<string, any>;
/**
 * Get nested property from object safely
 * @param obj - Object to get property from
 * @param path - Dot-separated path to property
 * @param defaultValue - Default value if property doesn't exist
 * @returns Property value or default value
 */
export declare function getNestedProperty<T = any>(obj: any, path: string, defaultValue?: T): T;
/**
 * Set nested property on object
 * @param obj - Object to set property on
 * @param path - Dot-separated path to property
 * @param value - Value to set
 */
export declare function setNestedProperty(obj: any, path: string, value: any): void;
/**
 * Pick specific properties from object
 * @param obj - Source object
 * @param keys - Keys to pick
 * @returns New object with only picked properties
 */
export declare function pick<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K>;
/**
 * Omit specific properties from object
 * @param obj - Source object
 * @param keys - Keys to omit
 * @returns New object without omitted properties
 */
export declare function omit<T, K extends keyof T>(obj: T, keys: K[]): Omit<T, K>;
