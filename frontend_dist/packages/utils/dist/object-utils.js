// src/object-utils.ts
/**
 * Deep clone an object
 * @param obj - Object to clone
 * @returns Deep cloned object
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object')
        return obj;
    if (obj instanceof Date)
        return new Date(obj.getTime());
    if (obj instanceof Array)
        return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
    return obj;
}
/**
 * Deep merge objects
 * @param target - Target object
 * @param sources - Source objects to merge
 * @returns Merged object
 */
export function deepMerge(target, ...sources) {
    if (!sources.length)
        return target;
    const source = sources.shift();
    if (isObject(target) && isObject(source)) {
        for (const key in source) {
            if (isObject(source[key])) {
                if (!target[key])
                    Object.assign(target, { [key]: {} });
                deepMerge(target[key], source[key]);
            }
            else {
                Object.assign(target, { [key]: source[key] });
            }
        }
    }
    return deepMerge(target, ...sources);
}
/**
 * Check if value is an object
 * @param item - Item to check
 * @returns True if item is an object
 */
export function isObject(item) {
    return item && typeof item === 'object' && !Array.isArray(item);
}
/**
 * Get nested property from object safely
 * @param obj - Object to get property from
 * @param path - Dot-separated path to property
 * @param defaultValue - Default value if property doesn't exist
 * @returns Property value or default value
 */
export function getNestedProperty(obj, path, defaultValue) {
    const keys = path.split('.');
    let result = obj;
    for (const key of keys) {
        if (result == null || typeof result !== 'object') {
            return defaultValue;
        }
        result = result[key];
    }
    return result === undefined ? defaultValue : result;
}
/**
 * Set nested property on object
 * @param obj - Object to set property on
 * @param path - Dot-separated path to property
 * @param value - Value to set
 */
export function setNestedProperty(obj, path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    let current = obj;
    for (const key of keys) {
        if (!(key in current) || typeof current[key] !== 'object') {
            current[key] = {};
        }
        current = current[key];
    }
    current[lastKey] = value;
}
/**
 * Pick specific properties from object
 * @param obj - Source object
 * @param keys - Keys to pick
 * @returns New object with only picked properties
 */
export function pick(obj, keys) {
    const result = {};
    for (const key of keys) {
        if (key in obj) {
            result[key] = obj[key];
        }
    }
    return result;
}
/**
 * Omit specific properties from object
 * @param obj - Source object
 * @param keys - Keys to omit
 * @returns New object without omitted properties
 */
export function omit(obj, keys) {
    const result = Object.assign({}, obj);
    for (const key of keys) {
        delete result[key];
    }
    return result;
}
