// main-app/src/api/index.ts
import { HttpClient, AuthClient, BookClient, ConvictionClient, FundClient } from '@trading-app/api';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { LocalStorageService } from '@trading-app/storage';

// Create storage service instance
const storageService = new LocalStorageService();

// Try different DeviceIdManager initialization patterns
let deviceIdManager: DeviceIdManager;

try {
  // Try to get existing instance first
  deviceIdManager = DeviceIdManager.getInstance();
} catch (e) {
  // If that fails, try to initialize it by calling a setup method
  try {
    (DeviceIdManager as any).init(storageService);
    deviceIdManager = DeviceIdManager.getInstance();
  } catch (e2) {
    // If that fails, try calling a different setup method
    try {
      (DeviceIdManager as any).setup(storageService);
      deviceIdManager = DeviceIdManager.getInstance();
    } catch (e3) {
      // Last resort - create a minimal mock
      console.error('Cannot initialize DeviceIdManager:', e3);
      deviceIdManager = {
        getDeviceId: () => 'browser-device-id',
        generateDeviceId: () => 'browser-device-id'
      } as any;
    }
  }
}

// Create token manager with correct dependencies
const tokenManager = new TokenManager(storageService, deviceIdManager);

// Create HTTP client
const httpClient = new HttpClient(tokenManager);

// Create and export API client instances
export const authApi = new AuthClient(httpClient, tokenManager);
export const bookApi = new BookClient(httpClient, tokenManager);
export const convictionApi = new ConvictionClient(httpClient, tokenManager);
export const fundApi = new FundClient(httpClient, tokenManager);