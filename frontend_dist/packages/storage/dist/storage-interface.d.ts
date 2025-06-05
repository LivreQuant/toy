/**
 * Common interface for storage services
 * Provides a consistent API for different storage mechanisms
 */
export interface StorageService {
    /**
     * Retrieves an item from storage
     * @param key - The key of the item to retrieve
     * @returns The item's string value, or null if not found
     */
    getItem(key: string): string | null;
    /**
     * Stores an item in storage
     * @param key - The key under which to store the item
     * @param value - The string value to store
     */
    setItem(key: string, value: string): void;
    /**
     * Removes an item from storage
     * @param key - The key of the item to remove
     */
    removeItem(key: string): void;
    /**
     * Clears all items from storage (optional)
     */
    clear?(): void;
}
/**
 * Storage service that supports JSON serialization
 */
export interface JsonStorageService extends StorageService {
    /**
     * Gets and parses a JSON value from storage
     * @param key - The storage key
     * @returns Parsed object or null if not found/invalid
     */
    getJson<T>(key: string): T | null;
    /**
     * Stores an object as JSON
     * @param key - The storage key
     * @param value - The object to store
     */
    setJson<T>(key: string, value: T): void;
}
