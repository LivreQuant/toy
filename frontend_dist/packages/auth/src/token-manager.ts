// src/token-manager.ts
import { LocalStorageService } from '@trading-app/storage';
import { DeviceIdManager } from './device-id-manager';
import { AuthApiInterface } from './auth-api-interface';
import { getLogger } from '@trading-app/logging';

export interface TokenData {
    accessToken: string;
    refreshToken: string;
    expiresAt: number; // timestamp in milliseconds
    userId: string | number;
    isLongLivedSession?: boolean;
}
  
export class TokenManager {
    private readonly logger = getLogger('TokenManager');
    private readonly STORAGE_KEY = 'auth_tokens';
    private readonly CSRF_TOKEN_KEY = 'csrf_token';
    private readonly CSRF_EXPIRY_KEY = 'csrf_expiry';

    private readonly expiryMargin = 5 * 60 * 1000; // 5 minutes in milliseconds
    private refreshPromise: Promise<boolean> | null = null;
    private refreshListeners: Set<Function> = new Set();
    private authApi: AuthApiInterface | null = null;

    constructor(
        private storageService: LocalStorageService,
        private deviceIdManager: DeviceIdManager
    ) {}

    // Set the auth API to break circular dependency during setup
    public setAuthApi(authApi: AuthApiInterface): void {
        if (!this.authApi) {
            this.authApi = authApi;
        } else {
            this.logger.warn('TokenManager: AuthApi already set.');
        }
    }

    // Store tokens using injected storage service
    public storeTokens(tokenData: TokenData): void {
        try {            
            this.storageService.setJson(this.STORAGE_KEY, tokenData);
            this.logger.debug('Tokens stored successfully');
        } catch (e: any) {
            this.logger.error(`Failed to store tokens: ${e.message}`);
        }
    }

    // Add automatic csrf protection for API calls
    public async getCsrfToken(): Promise<string> {
        // Generate a CSRF token if none exists or if it's expired
        let csrfToken = this.storageService.getItem(this.CSRF_TOKEN_KEY);
        const csrfExpiry = this.storageService.getItem(this.CSRF_EXPIRY_KEY);
        
        if (!csrfToken || !csrfExpiry || parseInt(csrfExpiry) < Date.now()) {
            // Create a new token using a random string
            csrfToken = this.generateRandomToken();
            // Set expiry for 2 hours
            const expiry = Date.now() + (2 * 60 * 60 * 1000);
            
            this.storageService.setItem(this.CSRF_TOKEN_KEY, csrfToken);
            this.storageService.setItem(this.CSRF_EXPIRY_KEY, expiry.toString());
        }
        
        return csrfToken;
    }

    private generateRandomToken(): string {
        // Generate a secure random token
        const array = new Uint8Array(32);
        window.crypto.getRandomValues(array);
        return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    }
    
    // Get stored tokens using injected storage service
    public getTokens(): TokenData | null {
        try {
            return this.storageService.getJson<TokenData>(this.STORAGE_KEY);
        } catch (e: any) {
            this.logger.error(`Failed to parse stored tokens: ${e.message}`);
            this.clearTokens(); // Clear invalid tokens
            return null;
        }
    }

    // Clear tokens using injected storage service
    public clearTokens(): void {
        try {
            this.storageService.removeItem(this.STORAGE_KEY);
            this.storageService.removeItem(this.CSRF_TOKEN_KEY);
            this.storageService.removeItem(this.CSRF_EXPIRY_KEY);
            this.logger.debug('Tokens cleared successfully');
        } catch (e: any) {
            this.logger.error(`Failed to clear tokens: ${e.message}`);
        }
    }

    // Check if tokens are present and valid
    public isAuthenticated(): boolean {
        const tokens = this.getTokens();
        return tokens !== null && tokens.expiresAt > Date.now();
    }

    // Add listener for token refresh events
    public addRefreshListener(listener: Function): void {
        this.refreshListeners.add(listener);
    }

    // Remove listener
    public removeRefreshListener(listener: Function): void {
        this.refreshListeners.delete(listener);
    }

    // Get access token (automatically refreshing if needed)
    public async getAccessToken(): Promise<string | null> {
        const tokens = this.getTokens();
        if (!tokens) return null;

        // If token expires soon, refresh it
        if (tokens.expiresAt - Date.now() < this.expiryMargin) {
            const success = await this.refreshAccessToken();
            // If refresh failed, we expect tokens might be cleared or invalid
            if (!success) return null;

            // Get updated tokens after successful refresh
            const updatedTokens = this.getTokens();
            return updatedTokens?.accessToken || null;
        }

        // Token is valid and doesn't need refresh
        return tokens.accessToken;
    }

    // Get userId from stored tokens
    public getUserId(): string | number | null {
        const tokens = this.getTokens();
        return tokens?.userId || null;
    }

    // Refresh the access token using refresh token
    public async refreshAccessToken(): Promise<boolean> {
        // If already refreshing, return the existing promise
        if (this.refreshPromise) {
            return this.refreshPromise;
        }
    
        const tokens = this.getTokens();
        if (!tokens?.refreshToken) {
            this.logger.error('No refresh token available');
            return false;
        }
    
        // Check if authApi has been set via setAuthApi
        if (!this.authApi) {
            this.logger.error('Auth API dependency not set in TokenManager');
            return false;
        }
    
        this.refreshPromise = new Promise<boolean>(async (resolve) => {
            try {
                // Use the assigned authApi instance
                const response = await this.authApi!.refreshToken(tokens.refreshToken);
    
                // Verify all required fields are present
                if (!response.accessToken || !response.refreshToken || !response.expiresIn || !response.userId) {
                    this.logger.error('Token refresh response missing required fields');
                    this.notifyRefreshListeners(false);
                    resolve(false);
                    return;
                }
    
                this.storeTokens({
                    accessToken: response.accessToken,
                    refreshToken: response.refreshToken,
                    expiresAt: Date.now() + (response.expiresIn * 1000),
                    userId: response.userId
                });
    
                // Notify listeners about the token refresh success
                this.notifyRefreshListeners(true);
                resolve(true);
    
            } catch (error: any) {
                this.logger.error('Token refresh API call failed', { error: error.message });
                // Notify listeners about the failed refresh
                this.notifyRefreshListeners(false);
                resolve(false);
            } finally {
                // Ensure the promise reference is cleared
                this.refreshPromise = null;
            }
        });
    
        return this.refreshPromise;
    }
    
    // Notify all registered listeners
    private notifyRefreshListeners(success: boolean): void {
        // Use a Set iterator for safety if listeners modify the Set during iteration
        const listenersToNotify = new Set(this.refreshListeners);
        listenersToNotify.forEach(listener => {
            try {
                listener(success);
            } catch (error: any) {
                this.logger.error(`Error in token refresh listener: ${error.message}`);
            }
        });
    }

    public isSessionDeactivated(): boolean {
        const tokens = this.getTokens();
        
        // Check if tokens exist but device ID is missing
        return tokens !== null && !this.deviceIdManager.hasStoredDeviceId();
    }
}