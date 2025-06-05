// src/memory-storage-service.ts
import { getLogger } from '@trading-app/logging';
const logger = getLogger('MemoryStorageService');
/**
 * In-memory storage service for testing or fallback scenarios.
 * Data is lost when the instance is garbage collected.
 */
export class MemoryStorageService {
    constructor() {
        this.storage = new Map();
    }
    /**
     * Retrieves an item from memory storage.
     */
    getItem(key) {
        return this.storage.get(key) || null;
    }
    /**
     * Stores an item in memory storage.
     */
    setItem(key, value) {
        this.storage.set(key, value);
    }
    /**
     * Removes an item from memory storage.
     */
    removeItem(key) {
        this.storage.delete(key);
    }
    /**
     * Clears all items from memory storage.
     */
    clear() {
        this.storage.clear();
        logger.info('Cleared all memory storage items.');
    }
    /**
     * Gets and parses a JSON value from storage
     */
    getJson(key) {
        const value = this.getItem(key);
        if (!value)
            return null;
        try {
            return JSON.parse(value);
        }
        catch (error) {
            logger.error(`Error parsing JSON for key "${key}"`, { error: error.message });
            return null;
        }
    }
    /**
     * Stores an object as JSON
     */
    setJson(key, value) {
        try {
            const jsonString = JSON.stringify(value);
            this.setItem(key, jsonString);
        }
        catch (error) {
            logger.error(`Error stringifying JSON for key "${key}"`, { error: error.message });
        }
    }
    /**
     * Get all stored keys (useful for testing)
     */
    getAllKeys() {
        return Array.from(this.storage.keys());
    }
    /**
     * Get the number of stored items
     */
    size() {
        return this.storage.size;
    }
}
