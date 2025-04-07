// src/services/connection/connection-recovery-interface.ts

/**
 * Defines the essential methods required for a class that manages
 * connection state and recovery, allowing the RecoveryManager
 * to interact with it generically.
 */
export interface ConnectionRecoveryInterface {
  /**
   * Gets the current connection state.
   * Should return information about whether the connection is active,
   * in the process of connecting, or disconnected.
   */
  getState(): {
    isConnected: boolean;
    isConnecting: boolean;
    [key: string]: any; // Allow for additional state properties
  };

  /**
   * Initiates the disconnection process.
   */
  disconnect(reason?: string): void; // Add optional reason

  /**
   * Initiates the connection process.
   * @returns A promise that resolves to true if connection is successful, false otherwise.
   */
  connect(): Promise<boolean>;
}
