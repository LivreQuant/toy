// src/local-storage-service.ts
import { getLogger } from '@trading-app/logging';
import { StorageService, JsonStorageService } from './storage-interface';

const logger = getLogger('LocalStorageService');

/**
 * Implements the StorageService interface using browser localStorage.
 * Includes basic error handling for scenarios like storage being full or disabled.
 */
export class LocalStorageService implements JsonStorageService {

  /**
   * Retrieves an item from localStorage.
   * @param key - The key of the item to retrieve.
   * @returns The item's string value, or null if not found or error occurs.
   */
  getItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch (error: any) {
      logger.error(`Error getting item "${key}" from localStorage`, { error: error.message });
      return null; // Return null on error
    }
  }

  /**
   * Stores an item in localStorage.
   * @param key - The key under which to store the item.
   * @param value - The string value to store.
   */
  setItem(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch (error: any) {
      logger.error(`Error setting item "${key}" in localStorage`, { error: error.message, valueLength: value.length });
      // Could implement quota exceeded handling here
    }
  }

  /**
   * Removes an item from localStorage.
   * @param key - The key of the item to remove.
   */
  removeItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (error: any) {
      logger.error(`Error removing item "${key}" from localStorage`, { error: error.message });
    }
  }

  /**
   * Clears all items from localStorage.
   */
  clear(): void {
    try {
      localStorage.clear();
      logger.info('Cleared all localStorage items.');
    } catch (error: any) {
      logger.error('Error clearing localStorage', { error: error.message });
    }
  }

  /**
   * Gets and parses a JSON value from storage
   * @param key - The storage key
   * @returns Parsed object or null if not found/invalid
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
   * @param key - The storage key  
   * @param value - The object to store
   */
  setJson<T>(key: string, value: T): void {
    try {
      const jsonString = JSON.stringify(value);
      this.setItem(key, jsonString);
    } catch (error: any) {
      logger.error(`Error stringifying JSON for key "${key}"`, { error: error.message });
    }
  }
}