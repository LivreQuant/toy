// src/services/storage/storage-service.ts (New File)
export interface StorageService {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
  }