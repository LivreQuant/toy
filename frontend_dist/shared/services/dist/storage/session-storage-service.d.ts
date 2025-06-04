export declare class SessionStorageService {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
    clearAll(): void;
}
