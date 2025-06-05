// src/services/storage/local-storage-service.ts
import { getLogger } from '../../boot/logging'; // Use your logger

const logger = getLogger('LocalStorageService');

/**
 * Implements the StorageService interface using browser localStorage.
 * Includes basic error handling for scenarios like storage being full or disabled.
 */
export class LocalStorageService {

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
      // Optionally, implement more sophisticated error handling, e.g.,
      // - Notify user if storage is full (QuotaExceededError)
      // - Fallback to a different storage mechanism?
      // AppErrorHandler.handleGenericError(...)
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
}