/**
 * Remove duplicates from array
 * @param array - Array to deduplicate
 * @param keyFn - Optional function to generate comparison key
 * @returns Array without duplicates
 */
export declare function uniqueArray<T>(array: T[], keyFn?: (item: T) => any): T[];
/**
 * Chunk array into smaller arrays
 * @param array - Array to chunk
 * @param size - Size of each chunk
 * @returns Array of chunks
 */
export declare function chunkArray<T>(array: T[], size: number): T[][];
/**
 * Flatten nested arrays
 * @param array - Array to flatten
 * @param depth - Depth to flatten (default: 1)
 * @returns Flattened array
 */
export declare function flattenArray<T>(array: any[], depth?: number): T[];
/**
 * Group array items by key
 * @param array - Array to group
 * @param keyFn - Function to generate grouping key
 * @returns Object with grouped items
 */
export declare function groupBy<T, K extends string | number | symbol>(array: T[], keyFn: (item: T) => K): Record<K, T[]>;
/**
 * Sort array by multiple criteria
 * @param array - Array to sort
 * @param sortKeys - Array of sort criteria
 * @returns Sorted array
 */
export declare function sortBy<T>(array: T[], sortKeys: Array<{
    key: keyof T | ((item: T) => any);
    direction?: 'asc' | 'desc';
}>): T[];
/**
 * Find intersection of multiple arrays
 * @param arrays - Arrays to intersect
 * @returns Array with common elements
 */
export declare function intersectArrays<T>(...arrays: T[][]): T[];
/**
 * Find difference between two arrays
 * @param array1 - First array
 * @param array2 - Second array
 * @returns Elements in array1 but not in array2
 */
export declare function arrayDifference<T>(array1: T[], array2: T[]): T[];
