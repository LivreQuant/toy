// Copy from apps/legacy/src/services/storage/local-storage-service.ts
import { getLogger } from '../utils/enhanced-logger';
const logger = getLogger('LocalStorageService');
export class LocalStorageService {
    getItem(key) {
        try {
            return localStorage.getItem(key);
        }
        catch (error) {
            logger.error(`Error getting item "${key}" from localStorage`, { error: error.message });
            return null;
        }
    }
    setItem(key, value) {
        try {
            localStorage.setItem(key, value);
        }
        catch (error) {
            logger.error(`Error setting item "${key}" in localStorage`, {
                error: error.message,
                valueLength: value.length
            });
        }
    }
    removeItem(key) {
        try {
            localStorage.removeItem(key);
        }
        catch (error) {
            logger.error(`Error removing item "${key}" from localStorage`, { error: error.message });
        }
    }
}
