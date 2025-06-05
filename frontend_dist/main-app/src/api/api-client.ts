import { HttpClient } from './http-client';
import { AuthApi } from './auth';
import { ConvictionsApi } from './conviction';
import { BookApi } from './book'; // Add this
import { TokenManager } from '../services/auth/token-manager';
import { DeviceIdManager } from '../services/auth/device-id-manager';
import { LocalStorageService } from '../services/storage/local-storage-service';
import { SessionStorageService } from '../services/storage/session-storage-service';
import { FundApi } from './fund';

// Create storage services
const localStorageService = new LocalStorageService();
const sessionStorageService = new SessionStorageService();

// Create device ID manager
const deviceIdManager = DeviceIdManager.getInstance(sessionStorageService);

// Create token manager
export const tokenManager = new TokenManager(localStorageService, deviceIdManager);

// Create HTTP client
export const httpClient = new HttpClient(tokenManager);

// Create API clients
export const authApi = new AuthApi(httpClient);
export const bookApi = new BookApi(httpClient);
export const fundApi = new FundApi(httpClient);
export const convictionsApi = new ConvictionsApi(httpClient);

// Set the auth API on the token manager to handle token refreshes
tokenManager.setAuthApi(authApi);