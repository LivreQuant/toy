// src/services/storage/local-storage-service.ts (New File)
import { StorageService } from './storage-service';
export class LocalStorageService implements StorageService {
  getItem(key: string): string | null { return localStorage.getItem(key); }
  setItem(key: string, value: string): void { localStorage.setItem(key, value); }
  removeItem(key: string): void { localStorage.removeItem(key); }
}
