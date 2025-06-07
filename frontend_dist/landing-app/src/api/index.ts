// frontend_dist/landing-app/src/api/index.ts
import { HttpClient, AuthClient } from '@trading-app/api';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { LocalStorageService } from '@trading-app/storage';

// Simplified auth setup for landing app
const storageService = new LocalStorageService();
const deviceIdManager = DeviceIdManager.getInstance();
const tokenManager = new TokenManager(storageService, deviceIdManager);
const httpClient = new HttpClient(tokenManager);

export const authApi = new AuthClient(httpClient, tokenManager);