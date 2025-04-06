// src/utils/device-id-manager.ts
import { LocalStorageService } from '../services/storage/local-storage-service'; // Assuming usage
import { StorageService } from '../services/storage/storage-service';
import { Logger } from './logger'; // Assuming logger usage

/**
 * Manages the unique device ID for the browser session using a Singleton pattern.
 * Uses dependency injection for storage and logging.
 */
export class DeviceIdManager {
    private static instance: DeviceIdManager | null = null;
    private readonly storageService: StorageService;
    private readonly logger: Logger;
    private readonly DEVICE_ID_KEY = 'trading_device_id';
    private deviceId: string | null = null; // Cache the ID in memory

    // Private constructor to enforce singleton pattern
    private constructor(storageService: StorageService, logger: Logger) {
        this.storageService = storageService;
        this.logger = logger.createChild('DeviceIdManager'); // Create child logger
        this.logger.info('DeviceIdManager instance created.');
        // Load existing ID on initialization
        this.deviceId = this.storageService.getItem(this.DEVICE_ID_KEY);
        if (!this.deviceId) {
            this.logger.info('No existing device ID found, will generate on first request.');
        } else {
            this.logger.info('Existing device ID loaded from storage.');
        }
    }

    /**
     * Gets the singleton instance of DeviceIdManager.
     * Initializes it on first call.
     * @param storageService - The storage service implementation (required on first call).
     * @param logger - The logger instance (required on first call).
     * @returns The singleton instance of DeviceIdManager.
     */
    public static getInstance(storageService?: StorageService, logger?: Logger): DeviceIdManager {
        if (!DeviceIdManager.instance) {
            if (!storageService || !logger) {
                throw new Error("StorageService and Logger must be provided for DeviceIdManager initialization.");
            }
            DeviceIdManager.instance = new DeviceIdManager(storageService, logger);
        }
        return DeviceIdManager.instance;
    }

    /**
     * Generates and stores a new device ID if one doesn't exist,
     * otherwise returns the existing/cached one.
     * @returns The device ID string.
     */
    public getDeviceId(): string {
        if (!this.deviceId) {
            this.logger.info('Generating new device ID.');
            this.deviceId = this.generateDeviceId();
            try {
                this.storageService.setItem(this.DEVICE_ID_KEY, this.deviceId);
                this.logger.info('New device ID stored successfully.');
            } catch (e: any) {
                this.logger.error('Failed to store new device ID', { error: e.message });
                // Handle storage error if necessary, maybe return temporary ID?
            }
        }
        return this.deviceId;
    }

    /**
     * Generates a new unique device ID.
     * @returns A new device ID string.
     */
    private generateDeviceId(): string {
        // Simple generation logic (consider using a more robust UUID library if needed)
        return `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    }

    /**
     * Clears the device ID from storage and the in-memory cache.
     */
    public clearDeviceId(): void {
        this.logger.warn('Clearing device ID from storage and memory.');
        try {
            this.storageService.removeItem(this.DEVICE_ID_KEY);
            this.deviceId = null;
        } catch (e: any) {
            this.logger.error('Failed to clear device ID from storage', { error: e.message });
        }
    }

    /**
     * Checks if a device ID exists in storage (without generating one).
     * @returns True if a device ID is found in storage, false otherwise.
     */
    public hasDeviceId(): boolean {
        // Check storage directly, don't rely on cache which might be populated by getDeviceId()
        return this.storageService.getItem(this.DEVICE_ID_KEY) !== null;
    }
}

// How to initialize and use (e.g., in your main application setup):
// import { LocalStorageService } from './services/storage/local-storage-service';
// import { Logger } from './utils/logger';
//
// const storageService = new LocalStorageService();
// const logger = Logger.getInstance(); // Assuming Logger is also a singleton
// const deviceIdManager = DeviceIdManager.getInstance(storageService, logger);
//
// // Later in other services:
// // constructor(..., deviceIdManager: DeviceIdManager) { this.deviceIdManager = deviceIdManager; }
// // const id = this.deviceIdManager.getDeviceId();

