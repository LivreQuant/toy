// src/array-utils.ts
/**
 * Remove duplicates from array
 * @param array - Array to deduplicate
 * @param keyFn - Optional function to generate comparison key
 * @returns Array without duplicates
 */
export function uniqueArray(array, keyFn) {
    if (!keyFn) {
        return [...new Set(array)];
    }
    const seen = new Set();
    return array.filter(item => {
        const key = keyFn(item);
        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
}
/**
 * Chunk array into smaller arrays
 * @param array - Array to chunk
 * @param size - Size of each chunk
 * @returns Array of chunks
 */
export function chunkArray(array, size) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
        chunks.push(array.slice(i, i + size));
    }
    return chunks;
}
/**
 * Flatten nested arrays
 * @param array - Array to flatten
 * @param depth - Depth to flatten (default: 1)
 * @returns Flattened array
 */
export function flattenArray(array, depth = 1) {
    if (depth === 0)
        return array.slice();
    return array.reduce((acc, val) => {
        if (Array.isArray(val)) {
            acc.push(...flattenArray(val, depth - 1));
        }
        else {
            acc.push(val);
        }
        return acc;
    }, []);
}
/**
 * Group array items by key
 * @param array - Array to group
 * @param keyFn - Function to generate grouping key
 * @returns Object with grouped items
 */
export function groupBy(array, keyFn) {
    return array.reduce((groups, item) => {
        const key = keyFn(item);
        if (!groups[key]) {
            groups[key] = [];
        }
        groups[key].push(item);
        return groups;
    }, {});
}
/**
 * Sort array by multiple criteria
 * @param array - Array to sort
 * @param sortKeys - Array of sort criteria
 * @returns Sorted array
 */
export function sortBy(array, sortKeys) {
    return [...array].sort((a, b) => {
        for (const { key, direction = 'asc' } of sortKeys) {
            const aVal = typeof key === 'function' ? key(a) : a[key];
            const bVal = typeof key === 'function' ? key(b) : b[key];
            let comparison = 0;
            if (aVal > bVal)
                comparison = 1;
            if (aVal < bVal)
                comparison = -1;
            if (comparison !== 0) {
                return direction === 'desc' ? -comparison : comparison;
            }
        }
        return 0;
    });
}
/**
 * Find intersection of multiple arrays
 * @param arrays - Arrays to intersect
 * @returns Array with common elements
 */
export function intersectArrays(...arrays) {
    if (arrays.length === 0)
        return [];
    if (arrays.length === 1)
        return arrays[0];
    return arrays.reduce((acc, current) => acc.filter(item => current.includes(item)));
}
/**
 * Find difference between two arrays
 * @param array1 - First array
 * @param array2 - Second array
 * @returns Elements in array1 but not in array2
 */
export function arrayDifference(array1, array2) {
    return array1.filter(item => !array2.includes(item));
}
