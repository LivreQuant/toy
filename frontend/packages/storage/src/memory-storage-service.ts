// src/memory-storage-service.ts
import { getLogger } from '@trading-app/logging';
import { StorageService, JsonStorageService } from './storage-interface';

const logger = getLogger('MemoryStorageService');

/**
 * In-memory storage service for testing or fallback scenarios.
 * Data is lost when the instance is garbage collected.
 */
export class MemoryStorageService implements JsonStorageService {
  private storage = new Map<string, string>();

  /**
   * Retrieves an item from memory storage.
   */
  getItem(key: string): string | null {
    return this.storage.get(key) || null;
  }

  /**
   * Stores an item in memory storage.
   */
  setItem(key: string, value: string): void {
    this.storage.set(key, value);
  }

  /**
   * Removes an item from memory storage.
   */
  removeItem(key: string): void {
    this.storage.delete(key);
  }

  /**
   * Clears all items from memory storage.
   */
  clear(): void {
    this.storage.clear();
    logger.info('Cleared all memory storage items.');
  }

  /**
   * Gets and parses a JSON value from storage
   */
  getJson<T>(key: string): T | null {
    const value = this.getItem(key);
    if (!value) return null;

    try {
      return JSON.parse(value) as T;
    } catch (error: any) {
      logger.error(`Error parsing JSON for key "${key}"`, { error: error.message });
      return null;
    }
  }

  /**
   * Stores an object as JSON
   */
  setJson<T>(key: string, value: T): void {
    try {
      const jsonString = JSON.stringify(value);
      this.setItem(key, jsonString);
    } catch (error: any) {
      logger.error(`Error stringifying JSON for key "${key}"`, { error: error.message });
    }
  }

  /**
   * Get all stored keys (useful for testing)
   */
  getAllKeys(): string[] {
    return Array.from(this.storage.keys());
  }

  /**
   * Get the number of stored items
   */
  size(): number {
    return this.storage.size;
  }
}