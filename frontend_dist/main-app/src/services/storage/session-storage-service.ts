// src/services/storage/session-storage-service.ts
import { getLogger } from '../../boot/logging';

const logger = getLogger('SessionStorageService');

/**
 * Implements the StorageService interface using browser sessionStorage.
 * Provides a consistent interface with error handling for session-specific storage.
 */
export class SessionStorageService {
  /**
   * Retrieves an item from sessionStorage.
   * @param key - The key of the item to retrieve.
   * @returns The item's string value, or null if not found or error occurs.
   */
  getItem(key: string): string | null {
    try {
      return sessionStorage.getItem(key);
    } catch (error: any) {
      logger.error(`Error getting item "${key}" from sessionStorage`, { error: error.message });
      return null; // Return null on error
    }
  }

  /**
   * Stores an item in sessionStorage.
   * @param key - The key under which to store the item.
   * @param value - The string value to store.
   */
  setItem(key: string, value: string): void {
    try {
      sessionStorage.setItem(key, value);
    } catch (error: any) {
      logger.error(`Error setting item "${key}" in sessionStorage`, { 
        error: error.message, 
        valueLength: value.length 
      });
      // Potential for more sophisticated error handling if needed
    }
  }

  /**
   * Removes an item from sessionStorage.
   * @param key - The key of the item to remove.
   */
  removeItem(key: string): void {
    try {
      sessionStorage.removeItem(key);
    } catch (error: any) {
      logger.error(`Error removing item "${key}" from sessionStorage`, { error: error.message });
    }
  }

  /**
   * Clears all items from sessionStorage.
   * More aggressive than individual key removal, use with caution.
   */
  clearAll(): void {
    try {
      sessionStorage.clear();
      logger.info('Cleared all sessionStorage items.');
    } catch (error: any) {
      logger.error('Error clearing sessionStorage', { error: error.message });
    }
  }
}