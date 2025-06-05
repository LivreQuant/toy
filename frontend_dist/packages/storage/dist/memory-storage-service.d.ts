import { JsonStorageService } from './storage-interface';
/**
 * In-memory storage service for testing or fallback scenarios.
 * Data is lost when the instance is garbage collected.
 */
export declare class MemoryStorageService implements JsonStorageService {
    private storage;
    /**
     * Retrieves an item from memory storage.
     */
    getItem(key: string): string | null;
    /**
     * Stores an item in memory storage.
     */
    setItem(key: string, value: string): void;
    /**
     * Removes an item from memory storage.
     */
    removeItem(key: string): void;
    /**
     * Clears all items from memory storage.
     */
    clear(): void;
    /**
     * Gets and parses a JSON value from storage
     */
    getJson<T>(key: string): T | null;
    /**
     * Stores an object as JSON
     */
    setJson<T>(key: string, value: T): void;
    /**
     * Get all stored keys (useful for testing)
     */
    getAllKeys(): string[];
    /**
     * Get the number of stored items
     */
    size(): number;
}
