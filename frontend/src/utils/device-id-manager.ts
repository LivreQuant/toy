// UPDATED device-id-manager.ts
import { StorageService } from '../services/storage/storage-service';
import { EnhancedLogger } from './enhanced-logger';

export class DeviceIdManager {
    private static instance: DeviceIdManager | null = null;
    private readonly storageService: StorageService;
    private readonly logger: EnhancedLogger;
    private readonly DEVICE_ID_KEY = 'app_device_identifier';
    private deviceId: string | null = null;
    
    // Add browser fingerprint components
    private readonly BROWSER_SESSION_KEY = 'browser_session_key';
    private sessionKey: string | null = null;

    private constructor(storageService: StorageService, parentLogger: EnhancedLogger) {
        this.storageService = storageService;
        this.logger = parentLogger.createChild('DeviceIdManager');
        this.logger.info('DeviceIdManager instance initializing...');
        
        // Generate a browser session key first (unique per browser instance)
        this.generateBrowserSessionKey();
        
        // Then load or generate device ID
        this.loadOrGenerateDeviceId();
    }

    /**
     * Creates a unique key for this browser session (lost when browser is closed)
     */
    private generateBrowserSessionKey(): void {
        // Try to get from sessionStorage first (persists within current tab only)
        try {
            let sessionKey = null;
            if (typeof sessionStorage !== 'undefined') {
                sessionKey = sessionStorage.getItem(this.BROWSER_SESSION_KEY);
            }
            
            if (!sessionKey) {
                // Generate a new session key
                const timestamp = Date.now().toString(36);
                const randomPart = crypto.getRandomValues(new Uint32Array(2))
                    .join('-')
                    .toString();
                    
                sessionKey = `session-${timestamp}-${randomPart}`;
                
                // Store in sessionStorage so it persists only for this browser tab
                if (typeof sessionStorage !== 'undefined') {
                    sessionStorage.setItem(this.BROWSER_SESSION_KEY, sessionKey);
                }
                
                this.logger.info(`Generated new browser session key: ${sessionKey}`);
            } else {
                this.logger.info(`Loaded existing browser session key: ${sessionKey}`);
            }
            
            this.sessionKey = sessionKey;
        } catch (error: any) {
            this.logger.error('Failed to generate browser session key', { error: error.message });
            // Generate an in-memory only fallback
            this.sessionKey = `memory-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 10)}`;
        }
    }

    public static getInstance(storageService?: StorageService, parentLogger?: EnhancedLogger): DeviceIdManager {
        if (!DeviceIdManager.instance) {
            if (!storageService || !parentLogger) {
                throw new Error("DeviceIdManager requires StorageService and Logger for first initialization.");
            }
            DeviceIdManager.instance = new DeviceIdManager(storageService, parentLogger);
        } else if (storageService || parentLogger) {
            const logger = DeviceIdManager.instance?.logger || console;
            logger.warn("DeviceIdManager already initialized. Provided dependencies were ignored.");
        }
        return DeviceIdManager.instance;
    }
    
    private loadOrGenerateDeviceId(): void {
        try {
            // Try to get from sessionStorage first
            let deviceId = null;
            
            if (typeof sessionStorage !== 'undefined') {
                deviceId = sessionStorage.getItem(this.DEVICE_ID_KEY);
            }
            
            if (deviceId && this.isValidDeviceId(deviceId)) {
                this.deviceId = deviceId;
                this.logger.info(`Loaded existing device ID from sessionStorage: ${this.deviceId}`);
            } else {
                // Generate a new device ID
                this.deviceId = this.generateBaseDeviceId(); // Corrected method name
                
                // Store in sessionStorage
                if (typeof sessionStorage !== 'undefined' && this.deviceId) { // Added null check
                    sessionStorage.setItem(this.DEVICE_ID_KEY, this.deviceId);
                }
                
                this.logger.info(`New device ID generated and stored in sessionStorage: ${this.deviceId}`);
            }
        } catch (error: any) {
            this.logger.error('Error accessing storage during device ID load/generation', { error: error.message });
            // Fallback: generate an ID for temporary use in memory if storage fails
            if (!this.deviceId) {
                this.deviceId = this.generateBaseDeviceId(); // Corrected method name
                this.logger.warn(`Using temporary in-memory device ID due to storage error: ${this.deviceId}`);
            }
        }
    }

    private createCombinedId(baseDeviceId: string): string {
        // Combine the base device ID with the browser session key
        return `${baseDeviceId}:${this.sessionKey}`;
    }

    public getDeviceId(): string {
        if (!this.deviceId) {
            this.logger.error("Device ID requested but not initialized. Attempting re-initialization.");
            this.loadOrGenerateDeviceId();
            if(!this.deviceId) {
                throw new Error("Failed to load or generate Device ID.");
            }
        }
        return this.deviceId;
    }

    // Generate a persistent device ID that identifies this browser/device
    private generateBaseDeviceId(): string {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        
        // Enhanced fallback with more entropy
        const timestamp = Date.now().toString(36);
        const randomA = Math.random().toString(36).substring(2, 10);
        const randomB = Math.random().toString(36).substring(2, 10);
        return `device-${timestamp}-${randomA}-${randomB}`;
    }

    private isValidDeviceId(id: string | null): boolean {
        if (!id) return false;
        
        // Base validation (check for base device ID only - we'll combine with session key later)
        const isUuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(id);
        const isCustomFormat = id.startsWith('device-') && id.length > 15 && !id.includes(':');
        
        return typeof id === 'string' && (isUuid || isCustomFormat);
    }

    public clearDeviceId(): void {
        this.logger.warn('Clearing device ID from storage and memory.');
        try {
            this.storageService.removeItem(this.DEVICE_ID_KEY);
            this.deviceId = null;
            
            // Also clear session storage
            if (typeof sessionStorage !== 'undefined') {
                sessionStorage.removeItem(this.BROWSER_SESSION_KEY);
            }
            this.sessionKey = null;
        } catch (e: any) {
            this.logger.error('Failed to clear device ID from storage', { error: e.message });
        }
    }

    public hasStoredDeviceId(): boolean {
        try {
            const storedId = this.storageService.getItem(this.DEVICE_ID_KEY);
            return this.isValidDeviceId(storedId);
        } catch (error) {
            this.logger.error('Failed to check for stored device ID', { error });
            return false;
        }
    }
}