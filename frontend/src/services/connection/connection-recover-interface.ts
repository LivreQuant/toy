// src/services/connection/connection-recovery-interface.ts
export interface ConnectionRecoveryInterface {
    getState(): { 
      isConnected: boolean;
      isConnecting: boolean;
      [key: string]: any;
    };
    disconnect(): void;
    connect(): Promise<boolean>;
  }