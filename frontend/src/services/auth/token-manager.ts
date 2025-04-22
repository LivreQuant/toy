// src/services/auth/token-manager.ts
import { AuthApi } from '../../api/auth';
import { LocalStorageService } from '../storage/local-storage-service';
import { DeviceIdManager } from './device-id-manager';
import { getLogger } from '../../boot/logging';

export interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // timestamp in milliseconds
  userId: string | number; // Add userId to the token data
}
  
export class TokenManager {
    private readonly logger = getLogger('TokenManager');
    private readonly STORAGE_KEY = 'auth_tokens'; // Instance property

    private readonly expiryMargin = 5 * 60 * 1000; // 5 minutes in milliseconds, instance property
    private refreshPromise: Promise<boolean> | null = null;
    private refreshListeners: Set<Function> = new Set();
    private authApi: AuthApi | null = null; // Injected later via setAuthApi

    // Inject StorageService and ErrorHandler
    constructor(
        private storageService: LocalStorageService,
        private deviceIdManager: DeviceIdManager
    ) {}

    // Keep this method to break the circular dependency during setup
    public setAuthApi(authApi: AuthApi): void {
      if (!this.authApi) { // Prevent overriding
         this.authApi = authApi;
      } else {
          // Optional: Log a warning if trying to set it again
          this.logger.warn('TokenManager: AuthApi already set.');
      }
    }

    // Store tokens using injected storage service
    public storeTokens(tokenData: TokenData): void {
        try {
             this.storageService.setItem(this.STORAGE_KEY, JSON.stringify(tokenData));
        } catch (e: any) {
            this.logger.error(`Failed to store tokens: ${e.message}`);
        }
    }

    // Get stored tokens using injected storage service
    public getTokens(): TokenData | null {
        const tokenStr = this.storageService.getItem(this.STORAGE_KEY);
        if (!tokenStr) return null;

        try {
            return JSON.parse(tokenStr) as TokenData;
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
        } catch (e: any) {
            this.logger.error(`Failed to clear tokens: ${e.message}`);
        }
    }

    // Check if tokens are present and valid (no change needed here)
    public isAuthenticated(): boolean {
        const tokens = this.getTokens();
        return tokens !== null && tokens.expiresAt > Date.now();
    }

    // Add listener for token refresh events (no change needed here)
    public addRefreshListener(listener: Function): void {
        this.refreshListeners.add(listener);
    }

    // Remove listener (no change needed here)
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

    // Get userId from stored tokens (no change needed here)
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
            // Use error handler
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
                const response = await this.authApi!.refreshToken(tokens.refreshToken); // Safe to use non-null assertion due to check above

                this.storeTokens({
                    accessToken: response.accessToken,
                    refreshToken: response.refreshToken, // Store the new refresh token if provided
                    expiresAt: Date.now() + (response.expiresIn * 1000),
                    userId: response.userId  // Store userId with the tokens
                });

                // Notify listeners about the token refresh success
                this.notifyRefreshListeners(true);
                resolve(true);

            } catch (error: any) {
                // Use error handler for refresh failure
                this.logger.error('Token refresh API call failed');

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

    // Notify all registered listeners (no change needed here)
    private notifyRefreshListeners(success: boolean): void {
        // Use a Set iterator for safety if listeners modify the Set during iteration
        const listenersToNotify = new Set(this.refreshListeners);
        listenersToNotify.forEach(listener => {
            try {
                listener(success);
            } catch (error: any) {
                // Use error handler for listener errors
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