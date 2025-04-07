// src/services/storage/storage-service.ts

/**
 * Defines a generic interface for key-value storage.
 * This allows for easy swapping of storage mechanisms (e.g., localStorage, sessionStorage, IndexedDB).
 */
export interface StorageService {
  /**
   * Retrieves an item from storage.
   * @param key - The key of the item to retrieve.
   * @returns The item's string value, or null if not found or error occurs.
   */
  getItem(key: string): string | null;

  /**
   * Stores an item in storage.
   * @param key - The key under which to store the item.
   * @param value - The string value to store.
   */
  setItem(key: string, value: string): void;

  /**
   * Removes an item from storage.
   * @param key - The key of the item to remove.
   */
  removeItem(key: string): void;
}