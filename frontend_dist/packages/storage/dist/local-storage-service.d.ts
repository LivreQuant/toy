import { JsonStorageService } from './storage-interface';
/**
 * Implements the StorageService interface using browser localStorage.
 * Includes basic error handling for scenarios like storage being full or disabled.
 */
export declare class LocalStorageService implements JsonStorageService {
    /**
     * Retrieves an item from localStorage.
     * @param key - The key of the item to retrieve.
     * @returns The item's string value, or null if not found or error occurs.
     */
    getItem(key: string): string | null;
    /**
     * Stores an item in localStorage.
     * @param key - The key under which to store the item.
     * @param value - The string value to store.
     */
    setItem(key: string, value: string): void;
    /**
     * Removes an item from localStorage.
     * @param key - The key of the item to remove.
     */
    removeItem(key: string): void;
    /**
     * Clears all items from localStorage.
     */
    clear(): void;
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
