import { SessionStorageService } from '../../../../../shared/services/src/storage/session-storage-service';
import { getLogger } from '../../boot/logging';

export class DeviceIdManager {
    private readonly logger = getLogger('DeviceIdManager');
    private readonly DEVICE_ID_KEY = 'app_device_identifier';

    private static instance: DeviceIdManager | null = null;
    private readonly storageService: SessionStorageService;
    private deviceId: string | null = null;

    private constructor(storageService: SessionStorageService) {
        this.storageService = storageService;
        this.initializeDeviceId();
    }

    private initializeDeviceId(): void {
        try {
            // Attempt to load existing device ID from sessionStorage
            let storedDeviceId = sessionStorage.getItem(this.DEVICE_ID_KEY);
            
            if (storedDeviceId && this.isValidDeviceId(storedDeviceId)) {
                this.deviceId = storedDeviceId;
                this.logger.info(`Loaded existing device ID: ${this.deviceId}`);
            } else {
                // Generate a new device ID
                this.deviceId = this.generateDeviceId();
                
                // Store in sessionStorage
                sessionStorage.setItem(this.DEVICE_ID_KEY, this.deviceId);
                
                this.logger.info(`New device ID generated: ${this.deviceId}`);
            }
        } catch (error: any) {
            this.logger.error('Error initializing device ID', { error: error.message });
            
            // Fallback to in-memory generation if storage fails
            this.deviceId = this.generateDeviceId();
            this.logger.warn(`Using temporary in-memory device ID: ${this.deviceId}`);
        }
    }

    public static getInstance(storageService?: SessionStorageService): DeviceIdManager {
        if (!DeviceIdManager.instance) {
            if (!storageService) {
                throw new Error("DeviceIdManager requires StorageService for first initialization.");
            }
            DeviceIdManager.instance = new DeviceIdManager(storageService);
        } else if (storageService) {
            const logger = getLogger('DeviceIdManager');
            logger.warn("DeviceIdManager already initialized. Provided dependencies were ignored.");
        }
        return DeviceIdManager.instance;
    }

    // Generate a unique device identifier
    private generateDeviceId(): string {
        // Prefer crypto.randomUUID if available
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        
        // Fallback generation with high entropy
        const timestamp = Date.now().toString(36);
        const randomA = Math.random().toString(36).substring(2, 10);
        const randomB = Math.random().toString(36).substring(2, 10);
        return `device-${timestamp}-${randomA}-${randomB}`;
    }

    // Validate the format of the device ID
    private isValidDeviceId(id: string | null): boolean {
        if (!id) return false;
        
        // Validation for UUID or our custom format
        const isUuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(id);
        const isCustomFormat = id.startsWith('device-') && id.length > 15;
        
        return typeof id === 'string' && (isUuid || isCustomFormat);
    }

    public getDeviceId(): string {
        if (!this.deviceId) {
            this.logger.error("Device ID not initialized. Regenerating.");
            this.initializeDeviceId();
            
            if (!this.deviceId) {
                throw new Error("Failed to generate Device ID.");
            }
        }
        return this.deviceId;
    }

    public clearDeviceId(): void {
        this.logger.warn('Clearing device ID from storage and memory.');
        try {
            sessionStorage.removeItem(this.DEVICE_ID_KEY);
            this.deviceId = null;
        } catch (e: any) {
            this.logger.error('Failed to clear device ID from storage', { error: e.message });
        }
    }

    public hasStoredDeviceId(): boolean {
        try {
            const storedId = sessionStorage.getItem(this.DEVICE_ID_KEY);
            return this.isValidDeviceId(storedId);
        } catch (error) {
            this.logger.error('Failed to check for stored device ID', { error });
            return false;
        }
    }

    // Regenerate device ID if needed
    public regenerateDeviceId(): string {
        this.initializeDeviceId();
        return this.getDeviceId();
    }
}