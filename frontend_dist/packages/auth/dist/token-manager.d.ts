import { LocalStorageService } from '@trading-app/storage';
import { DeviceIdManager } from './device-id-manager';
import { AuthApiInterface } from './auth-api-interface';
export interface TokenData {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
    userId: string | number;
    isLongLivedSession?: boolean;
}
export declare class TokenManager {
    private storageService;
    private deviceIdManager;
    private readonly logger;
    private readonly STORAGE_KEY;
    private readonly CSRF_TOKEN_KEY;
    private readonly CSRF_EXPIRY_KEY;
    private readonly expiryMargin;
    private refreshPromise;
    private refreshListeners;
    private authApi;
    constructor(storageService: LocalStorageService, deviceIdManager: DeviceIdManager);
    setAuthApi(authApi: AuthApiInterface): void;
    storeTokens(tokenData: TokenData): void;
    getCsrfToken(): Promise<string>;
    private generateRandomToken;
    getTokens(): TokenData | null;
    clearTokens(): void;
    isAuthenticated(): boolean;
    addRefreshListener(listener: Function): void;
    removeRefreshListener(listener: Function): void;
    getAccessToken(): Promise<string | null>;
    getUserId(): string | number | null;
    refreshAccessToken(): Promise<boolean>;
    private notifyRefreshListeners;
    isSessionDeactivated(): boolean;
}
