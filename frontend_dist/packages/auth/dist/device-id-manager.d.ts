import { SessionStorageService } from '@trading-app/storage';
export declare class DeviceIdManager {
    private readonly logger;
    private readonly DEVICE_ID_KEY;
    private static instance;
    private readonly storageService;
    private deviceId;
    private constructor();
    private initializeDeviceId;
    static getInstance(storageService?: SessionStorageService): DeviceIdManager;
    private generateDeviceId;
    private isValidDeviceId;
    getDeviceId(): string;
    clearDeviceId(): void;
    hasStoredDeviceId(): boolean;
    regenerateDeviceId(): string;
}
