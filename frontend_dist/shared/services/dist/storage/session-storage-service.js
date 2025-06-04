// Copy from apps/legacy/src/services/storage/session-storage-service.ts
import { getLogger } from '../utils/enhanced-logger';
const logger = getLogger('SessionStorageService');
export class SessionStorageService {
    getItem(key) {
        try {
            return sessionStorage.getItem(key);
        }
        catch (error) {
            logger.error(`Error getting item "${key}" from sessionStorage`, { error: error.message });
            return null;
        }
    }
    setItem(key, value) {
        try {
            sessionStorage.setItem(key, value);
        }
        catch (error) {
            logger.error(`Error setting item "${key}" in sessionStorage`, {
                error: error.message,
                valueLength: value.length
            });
        }
    }
    removeItem(key) {
        try {
            sessionStorage.removeItem(key);
        }
        catch (error) {
            logger.error(`Error removing item "${key}" from sessionStorage`, { error: error.message });
        }
    }
    clearAll() {
        try {
            sessionStorage.clear();
            logger.info('Cleared all sessionStorage items.');
        }
        catch (error) {
            logger.error('Error clearing sessionStorage', { error: error.message });
        }
    }
}
