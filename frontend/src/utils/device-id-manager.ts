// src/utils/device-id-manager.ts
import { StorageService } from '../services/storage/storage-service';
import { EnhancedLogger } from './enhanced-logger'; // Use your chosen logger class

/**
 * Manages a unique device ID for the browser session using a Singleton pattern.
 * Ensures the ID is generated once and persisted using the provided StorageService.
 * Uses dependency injection for storage and logging.
 */
export class DeviceIdManager {
    private static instance: DeviceIdManager | null = null;
    private readonly storageService: StorageService;
    private readonly logger: EnhancedLogger;
    // Use a specific, descriptive key for storage
    private readonly DEVICE_ID_KEY = 'app_device_identifier';
    private deviceId: string | null = null; // In-memory cache for the ID

    // Private constructor enforces singleton pattern and requires dependencies
    private constructor(storageService: StorageService, parentLogger: EnhancedLogger) {
        this.storageService = storageService;
        // Create a dedicated child logger for this manager
        this.logger = parentLogger.createChild('DeviceIdManager');
        this.logger.info('DeviceIdManager instance initializing...');
        // Attempt to load existing ID on initialization
        this.loadOrGenerateDeviceId();
    }

    /**
     * Gets the singleton instance of DeviceIdManager.
     * Initializes it on the first call using the provided dependencies.
     * Throws an error if called again without dependencies after initial setup.
     * @param storageService - The storage service implementation (required only on the first call).
     * @param parentLogger - The parent logger instance (required only on the first call).
     * @returns The singleton instance of DeviceIdManager.
     * @throws Error if dependencies are missing on the first call.
     */
    public static getInstance(storageService?: StorageService, parentLogger?: EnhancedLogger): DeviceIdManager {
        if (!DeviceIdManager.instance) {
            if (!storageService || !parentLogger) {
                throw new Error("DeviceIdManager requires StorageService and Logger for first initialization.");
            }
            DeviceIdManager.instance = new DeviceIdManager(storageService, parentLogger);
        } else {
            // Log a warning if called again with dependencies (they will be ignored)
            if (storageService || parentLogger) {
                 // Use the instance's logger if available, otherwise console
                 const logger = DeviceIdManager.instance?.logger || console;
                 logger.warn("DeviceIdManager already initialized. Provided dependencies were ignored.");
            }
        }
        return DeviceIdManager.instance;
    }

    /**
     * Loads the device ID from storage or generates a new one if not found or invalid.
     * Stores the newly generated ID.
     */
    private loadOrGenerateDeviceId(): void {
        try {
            const storedId = this.storageService.getItem(this.DEVICE_ID_KEY);
            if (storedId && this.isValidDeviceId(storedId)) {
                this.deviceId = storedId;
                this.logger.info(`Existing device ID loaded from storage: ${this.deviceId}`);
            } else {
                if (storedId) {
                   this.logger.warn(`Invalid device ID found in storage ("${storedId}"), generating a new one.`);
                } else {
                   this.logger.info('No existing device ID found in storage, generating a new one.');
                }
                this.deviceId = this.generateNewDeviceId();
                this.storageService.setItem(this.DEVICE_ID_KEY, this.deviceId);
                this.logger.info(`New device ID generated and stored: ${this.deviceId}`);
            }
        } catch (error: any) {
             this.logger.error('Error accessing storage during device ID load/generation', { error: error.message });
             // Fallback: generate an ID for temporary use in memory if storage fails?
             if (!this.deviceId) {
                 this.deviceId = this.generateNewDeviceId();
                 this.logger.warn(`Using temporary in-memory device ID due to storage error: ${this.deviceId}`);
             }
        }
    }


    /**
     * Gets the device ID.
     * If not already loaded/generated, it ensures initialization.
     * @returns The device ID string.
     */
    public getDeviceId(): string {
        // Should always be initialized by constructor or loadOrGenerateDeviceId
        if (!this.deviceId) {
            // This case should ideally not be hit if constructor logic is sound.
             this.logger.error("Device ID requested but not initialized. Attempting re-initialization.");
             this.loadOrGenerateDeviceId();
             // If still null after re-attempt (e.g., storage error during fallback), throw?
             if(!this.deviceId) {
                 throw new Error("Failed to load or generate Device ID.");
             }
        }
        return this.deviceId;
    }

    /**
     * Generates a new unique device ID string.
     * Uses a combination of timestamp and random characters for uniqueness.
     * Consider using `crypto.randomUUID()` in environments where it's available.
     * @returns A new device ID string.
     */
    private generateNewDeviceId(): string {
       // Use crypto.randomUUID() if available (more robust)
       if (typeof crypto !== 'undefined' && crypto.randomUUID) {
          return crypto.randomUUID();
       }
       // Fallback pseudo-random generator
        const timestamp = Date.now().toString(36);
        const randomPart = Math.random().toString(36).substring(2, 10); // Shorter random part
        return `device-${timestamp}-${randomPart}`;
    }

    /**
     * Validates the format of a potential device ID.
     * @param id The ID string to validate.
     * @returns True if the ID seems valid, false otherwise.
     */
    private isValidDeviceId(id: string | null): boolean {
        if (!id) return false;
        // Basic check: non-empty string, maybe length or prefix check
        // Example: Check if it starts with "device-" or is a UUID
        const isUuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(id);
        const isCustomFormat = id.startsWith('device-') && id.length > 10;
        return typeof id === 'string' && (isUuid || isCustomFormat);
    }


    /**
     * Clears the device ID from storage and the in-memory cache.
     * Primarily useful for testing or specific reset scenarios.
     */
    public clearDeviceId(): void {
        this.logger.warn('Clearing device ID from storage and memory.');
        try {
            this.storageService.removeItem(this.DEVICE_ID_KEY);
            this.deviceId = null; // Clear in-memory cache
             // Optionally, regenerate immediately after clearing?
             // this.loadOrGenerateDeviceId();
        } catch (e: any) {
            this.logger.error('Failed to clear device ID from storage', { error: e.message });
        }
    }

    /**
     * Checks if a device ID *currently exists* in storage (without generating one).
     * @returns True if a valid device ID is found in storage, false otherwise.
     */
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

// --- Initialization Example (in your main app setup, e.g., index.tsx or boot/index.ts) ---
// import { LocalStorageService } from './services/storage/local-storage-service';
// import { getLogger } from './boot/logging'; // Your logger setup
//
// const storageService = new LocalStorageService();
// const bootLogger = getLogger('AppBoot');
// // Initialize the DeviceIdManager singleton ONCE during startup
// DeviceIdManager.getInstance(storageService, bootLogger);
//
// // --- Usage Example (in another service or component) ---
// // import { DeviceIdManager } from './utils/device-id-manager';
// //
// // // Get the already initialized instance (no need for dependencies here)
// // const deviceId = DeviceIdManager.getInstance().getDeviceId();
// // console.log('Current Device ID:', deviceId);