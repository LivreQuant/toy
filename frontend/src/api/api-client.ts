// src/api/api-client.ts
import { HttpClient } from './http-client';
import { AuthApi } from './auth';
import { OrdersApi } from './order';
import { TokenManager } from '../services/auth/token-manager';
import { DeviceIdManager } from '../services/auth/device-id-manager';
import { LocalStorageService } from '../services/storage/local-storage-service';
import { SessionStorageService } from '../services/storage/session-storage-service';

// Create storage services
const localStorageService = new LocalStorageService();
const sessionStorageService = new SessionStorageService();

// Create device ID manager
const deviceIdManager = DeviceIdManager.getInstance(sessionStorageService);

// Create token manager
const tokenManager = new TokenManager(localStorageService, deviceIdManager);

// Create HTTP client
const httpClient = new HttpClient(tokenManager);

// Create API clients
export const authApi = new AuthApi(httpClient);
export const ordersApi = new OrdersApi(httpClient);

// Set the auth API on the token manager to handle token refreshes
tokenManager.setAuthApi(authApi);

// Export token manager and device ID manager for use in other parts of the app
export { tokenManager, deviceIdManager };