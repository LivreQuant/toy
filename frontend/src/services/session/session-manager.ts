// src/services/session/session-manager.ts
import { DeviceIdManager } from '../../utils/device-id-manager';
import { StorageService } from '../storage/storage-service'; // Adjust path as needed
import { Logger } from '../../utils/logger';

// Define the UserPreferences interface for managing user-specific settings
export interface UserPreferences {
  theme: 'light' | 'dark' | 'system'; // UI theme preference
  chartTimeframe: '1d' | '1w' | '1m' | '3m' | '1y'; // Default chart timeframe
  notifications: boolean; // Whether notifications are enabled
  language: string; // User's preferred language
}

// Define the AccountSettings interface for account-related configurations
export interface AccountSettings {
  defaultTradeSize: number; // Default quantity for trades
  riskLevel: 'low' | 'medium' | 'high'; // User-defined risk tolerance
  autoLogoutMinutes: number; // Inactivity timeout in minutes
  twoFactorEnabled: boolean; // Whether 2FA is active
}

// Define the structure for session data stored
export interface SessionData {
  deviceId: string; // Unique identifier for the device/browser session
  lastActive: number; // Timestamp (milliseconds) of the last user activity
  reconnectAttempts: number; // Counter for connection recovery attempts
  podName?: string | null; // Optional: Identifier for the backend pod serving the session
  userPreferences?: UserPreferences; // Nested user preferences object
  accountSettings?: AccountSettings; // Nested account settings object
  isMaster?: boolean; // Flag indicating if this is the primary/master browser tab/session
}

/**
 * Manages user session data, including preferences, settings, and activity.
 * Uses dependency injection for storage and logging, making it testable.
 */
export class SessionManager {
  // Injected StorageService instance for persistence
  private readonly storageService: StorageService;
  // Injected Logger instance for logging
  private readonly logger: Logger;
  // Key used for storing session data in the StorageService
  private readonly SESSION_KEY = 'trading_simulator_session';
  // Duration in milliseconds after which a session is considered expired locally
  private readonly SESSION_EXPIRY = 8 * 60 * 60 * 1000; // 8 hours

  /**
   * Creates an instance of SessionManager.
   * @param storageService - An instance conforming to the StorageService interface (e.g., LocalStorageService).
   * @param logger - An instance of the Logger utility.
   */
  constructor(storageService: StorageService, logger: Logger) {
    this.storageService = storageService;
    // Create a child logger specific to SessionManager for better context in logs
    this.logger = logger.createChild('SessionManager');
    this.logger.info('SessionManager Initialized');
  }

  /**
   * Retrieves the unique device ID using the centralized DeviceIdManager.
   * @returns The device ID string.
   */
  public getDeviceId(): string {
    // Uses the static DeviceIdManager as per previous decision
    return DeviceIdManager.getDeviceId();
  }

  /**
   * Saves the provided session data, merging it with existing data.
   * Always updates the 'lastActive' timestamp.
   * @param data - Partial session data to save or update.
   */
  public saveSession(data: Partial<SessionData>): void {
    // Retrieve current session data or create a default structure if none exists
    const existingData = this.getSession() || {
      reconnectAttempts: 0,
      lastActive: Date.now(),
      deviceId: this.getDeviceId(), // Ensure deviceId is included
      isMaster: true // Default assumption for a new session
    };

    // Merge existing data with the new partial data, ensuring lastActive is current
    const updatedData = {
      ...existingData,
      ...data,
      lastActive: Date.now()
    } as SessionData;

    try {
      // Persist the updated session data using the injected storage service
      this.storageService.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
      this.logger.info('Session data saved successfully.');
    } catch (e: any) {
      // Log any errors during the save operation
      this.logger.error('Failed to save session data', { error: e.message, stack: e.stack });
    }
  }

  /**
   * Retrieves the current session data from storage.
   * Performs validation and expiry checks.
   * @returns The SessionData object if valid and not expired, otherwise null.
   */
  public getSession(): SessionData | null {
    try {
      // Retrieve the raw session string from storage
      const sessionStr = this.storageService.getItem(this.SESSION_KEY);
      if (!sessionStr) {
        // Log if no session data is found (this is normal on first visit or after clearing)
        this.logger.info('No session data found in storage.');
        return null;
      }

      // Parse the JSON string into a SessionData object
      const session = JSON.parse(sessionStr) as SessionData;

      // Basic validation: check for essential fields
      if (!session.deviceId || !session.lastActive) {
         this.logger.error('Invalid session data structure found, clearing.', { session });
         this.clearSession(); // Clear corrupted data
         return null;
      }

      // Check for local session expiry based on last activity time
      if (Date.now() - session.lastActive > this.SESSION_EXPIRY) {
        this.logger.warn(`Session expired locally (last active: ${new Date(session.lastActive).toISOString()}). Clearing.`);
        this.clearSession();
        return null;
      }

      // Consistency check: Ensure the deviceId in the stored session matches the current one
      const currentDeviceId = this.getDeviceId();
      if (session.deviceId !== currentDeviceId) {
          this.logger.warn('Session deviceId mismatch, clearing session.', { sessionDeviceId: session.deviceId, currentDeviceId: currentDeviceId });
          this.clearSession();
          return null;
      }

      // Return the valid session data
      return session;
    } catch (e: any) {
      // Log errors during parsing (e.g., corrupted JSON)
      this.logger.error('Failed to parse session data from storage', { error: e.message, stack: e.stack });
      this.clearSession(); // Clear potentially corrupted data
      return null;
    }
  }

  /**
   * Updates the 'lastActive' timestamp in the session data.
   * Includes throttling to avoid excessive writes to storage.
   */
  public updateActivity(): void {
    const session = this.getSession();
    if (session) {
      // Throttle updates: Only update if last activity was more than 60 seconds ago
      const throttleInterval = 60 * 1000; // 1 minute
      if (Date.now() - session.lastActive > throttleInterval) {
         this.logger.info('Updating session last active timestamp.');
         // Call saveSession with empty data to trigger merge and update lastActive
         this.saveSession({});
      }
    } else {
        // Log if trying to update activity without an active session
        this.logger.warn('Attempted to update activity on non-existent session.');
    }
  }

  /**
   * Removes the session data from storage.
   */
  public clearSession(): void {
    try {
      // Use the injected storage service to remove the item
      this.storageService.removeItem(this.SESSION_KEY);
      this.logger.info('Session data cleared from storage.');
    } catch (e: any) {
       // Log errors during removal
       this.logger.error('Failed to clear session data', { error: e.message, stack: e.stack });
    }
  }

  /**
   * Increments the connection recovery attempt counter stored in the session.
   * @returns The new reconnect attempt count, or 0 if no session exists.
   */
  public incrementReconnectAttempts(): number {
    const session = this.getSession();
    // Return 0 if there's no session to update
    if (!session) return 0;

    // Calculate the new count (defaulting to 0 if property doesn't exist yet)
    const reconnectAttempts = (session.reconnectAttempts || 0) + 1;
    // Save the updated count back to the session
    this.saveSession({ reconnectAttempts });
    this.logger.warn(`Reconnect attempt incremented to ${reconnectAttempts}`);
    return reconnectAttempts;
  }

  /**
   * Resets the connection recovery attempt counter to 0 in the session data.
   */
  public resetReconnectAttempts(): void {
    const session = this.getSession();
    // Only reset if there's a session and the count is currently greater than 0
    if (session?.reconnectAttempts && session.reconnectAttempts > 0) {
        this.logger.info('Resetting reconnect attempts to 0.');
        this.saveSession({ reconnectAttempts: 0 });
    }
  }

  /**
   * Retrieves the user preferences object from the session data.
   * @returns The UserPreferences object or null if not set or no session exists.
   */
  public getUserPreferences(): UserPreferences | null {
    const session = this.getSession();
    return session?.userPreferences || null;
  }

  /**
   * Updates the user preferences in the session data by merging new values.
   * @param preferences - A partial UserPreferences object with the values to update.
   */
  public updateUserPreferences(preferences: Partial<UserPreferences>): void {
    const session = this.getSession();
    if (!session) {
       this.logger.error('Cannot update preferences, no active session.');
       return; // Exit if no session exists
    }

    // Get current preferences or an empty object, then merge with new values
    const currentPrefs = session.userPreferences || {} as UserPreferences;
    const updatedPrefs = { ...currentPrefs, ...preferences };

    this.logger.info('Updating user preferences.');
    // Save the session with the updated preferences object
    this.saveSession({ userPreferences: updatedPrefs });
  }

  /**
   * Retrieves the account settings object from the session data.
   * @returns The AccountSettings object or null if not set or no session exists.
   */
  public getAccountSettings(): AccountSettings | null {
    const session = this.getSession();
    return session?.accountSettings || null;
  }

  /**
   * Updates the account settings in the session data by merging new values.
   * @param settings - A partial AccountSettings object with the values to update.
   */
  public updateAccountSettings(settings: Partial<AccountSettings>): void {
    const session = this.getSession();
    if (!session) {
        this.logger.error('Cannot update account settings, no active session.');
        return; // Exit if no session exists
    }

     // Get current settings or an empty object, then merge with new values
     const currentSettings = session.accountSettings || {} as AccountSettings;
     const updatedSettings = { ...currentSettings, ...settings };

     this.logger.info('Updating account settings.');
     // Save the session with the updated settings object
     this.saveSession({ accountSettings: updatedSettings });
  }

  /**
   * Sets the master status flag in the session data.
   * Used to coordinate behavior across multiple browser tabs/windows.
   * @param isMaster - Boolean indicating if this session instance is the master.
   */
   public setMasterStatus(isMaster: boolean): void {
        this.logger.info(`Setting master status to: ${isMaster}`);
        this.saveSession({ isMaster });
   }

   /**
    * Checks if the current session is marked as the master session.
    * @returns True if the session exists and is marked as master, false otherwise.
    */
   public isMasterSession(): boolean {
       const session = this.getSession();
       // Return the stored value, defaulting to false if the flag isn't present or no session exists
       return session?.isMaster ?? false;
   }
}
