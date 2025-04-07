// src/services/storage/local-storage-service.ts
import { StorageService } from './storage-service';
import { getLogger } from '../../boot/logging'; // Use your logger

const logger = getLogger('LocalStorageService');

/**
 * Implements the StorageService interface using browser localStorage.
 * Includes basic error handling for scenarios like storage being full or disabled.
 */
export class LocalStorageService implements StorageService {

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

   /**
    * Clears all items managed by this application from localStorage.
    * Note: This is potentially destructive. Use application-specific keys
    * or a prefixing strategy if you need to avoid clearing unrelated localStorage items.
    */
   // clearAll(): void {
   //   try {
   //     // Be cautious with localStorage.clear() - it removes everything!
   //     // It's often better to remove specific keys known to the application.
   //     // Example: Find all keys with a specific prefix and remove them.
   //     const keysToRemove: string[] = [];
   //     for (let i = 0; i < localStorage.length; i++) {
   //       const key = localStorage.key(i);
   //       if (key && key.startsWith('trading_app_')) { // Example prefix
   //         keysToRemove.push(key);
   //       }
   //     }
   //     keysToRemove.forEach(key => this.removeItem(key));
   //     logger.info('Cleared application-specific localStorage items.');
   //
   //   } catch (error: any) {
   //     logger.error('Error clearing localStorage', { error: error.message });
   //   }
   // }
}