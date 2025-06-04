// Copy from apps/legacy/src/services/storage/local-storage-service.ts
import { getLogger } from '../utils/enhanced-logger';

const logger = getLogger('LocalStorageService');

export class LocalStorageService {
  getItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch (error: any) {
      logger.error(`Error getting item "${key}" from localStorage`, { error: error.message });
      return null;
    }
  }

  setItem(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch (error: any) {
      logger.error(`Error setting item "${key}" in localStorage`, { 
        error: error.message, 
        valueLength: value.length 
      });
    }
  }

  removeItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (error: any) {
      logger.error(`Error removing item "${key}" from localStorage`, { error: error.message });
    }
  }
}