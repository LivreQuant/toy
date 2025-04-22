// src/services/session/session-manager.ts
import { DeviceIdManager } from '../auth/device-id-manager';
import { SessionStorageService } from '../storage/session-storage-service';
import { getLogger } from '../../boot/logging';

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  chartTimeframe: '1d' | '1w' | '1m' | '3m' | '1y';
  notificationsEnabled: boolean;
  language: string;
}

export interface AccountSettings {
  defaultTradeSize: number;
  riskLevel: 'low' | 'medium' | 'high';
  autoLogoutMinutes: number;
  twoFactorEnabled: boolean;
}

export interface SessionData {
  deviceId: string;
  userId: string | number | null;
  lastActive: number;
  userPreferences?: UserPreferences;
  accountSettings?: AccountSettings;
}


export class SessionManager {
  private readonly sessionStorageService: SessionStorageService;
  private readonly logger = getLogger('SessionManager');
  private readonly SESSION_KEY = 'trading_app_session';
  private readonly ACTIVITY_UPDATE_THROTTLE = 60 * 1000;
  private lastActivityUpdateTimestamp = 0;

  constructor(sessionStorageService: SessionStorageService) {
    this.sessionStorageService = sessionStorageService;
  }

  public getDeviceId(): string {
    return DeviceIdManager.getInstance().getDeviceId();
  }

   /**
    * Saves partial session data, merging it with existing data if present.
    * Automatically updates 'lastActive' timestamp on every save.
    * Ensures 'deviceId' is always present and correct.
    * FIX: Allow 'lastActive' to be passed in, omit only 'deviceId'.
    * @param dataToSave - Partial session data to save or update.
    */
   public saveSessionData(dataToSave: Partial<Omit<SessionData, 'deviceId'>>): void {
       const currentData = this.getSessionDataInternal(); // Get existing data or defaults
       const currentDeviceId = this.getDeviceId(); // Get current device ID

       // Merge, ensuring deviceId is correct and lastActive is updated
       const updatedData: SessionData = {
           ...currentData, // Start with existing or default
           ...dataToSave, // Overwrite with changes (including potentially lastActive)
           deviceId: currentDeviceId, // Always enforce current device ID
           // If lastActive wasn't in dataToSave, use current time as default update
           lastActive: dataToSave.lastActive ?? Date.now(),
       };

       try {
           this.sessionStorageService.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
           this.logger.debug('Session data saved successfully.');
       } catch (e: any) {
           this.logger.error('Failed to save session data', { error: e.message });
       }
   }

   public getSessionData(): SessionData | null {
       const session = this.getSessionDataInternal();
       if (!session.deviceId) return null;
       return session;
   }

   private getSessionDataInternal(): SessionData {
       try {
           const sessionStr = this.sessionStorageService.getItem(this.SESSION_KEY);
           const defaultSession: SessionData = { userId: null, lastActive: 0, deviceId: '', userPreferences: this.getDefaultUserPreferences(), accountSettings: this.getDefaultAccountSettings() };

           if (!sessionStr) {
               this.logger.info('No session data found in storage. Returning default structure.');
               return defaultSession;
           }

           const session = JSON.parse(sessionStr) as SessionData;

           if (typeof session.lastActive !== 'number' || typeof session.deviceId !== 'string') {
               this.logger.error('Invalid session data structure found, clearing.', { session });
               this.clearSessionData();
               return defaultSession;
           }

           const currentDeviceId = this.getDeviceId();
           if (session.deviceId !== currentDeviceId) {
               this.logger.warn('Session deviceId mismatch, clearing previous session data.', { sessionDeviceId: session.deviceId, currentDeviceId });
               this.clearSessionData();
                // Keep userId? Or clear? Clearing is safer.
               return { ...defaultSession, userId: null };
           }

           // Ensure preferences and settings exist (merge defaults if missing)
           session.userPreferences = { ...this.getDefaultUserPreferences(), ...(session.userPreferences || {}) };
           session.accountSettings = { ...this.getDefaultAccountSettings(), ...(session.accountSettings || {}) };


           return session;

       } catch (e: any) {
           this.logger.error('Failed to parse session data from storage, clearing.', { error: e.message });
           this.clearSessionData();
           return this.getSessionDataInternal(); // Return defaults after clearing
       }
   }


  public updateActivityTimestamp(): void {
    const now = Date.now();
    if (now - this.lastActivityUpdateTimestamp > this.ACTIVITY_UPDATE_THROTTLE) {
        const session = this.getSessionDataInternal();
        if (session) { // Only update if session exists (even default)
            this.logger.debug('Updating session last active timestamp.');
            this.lastActivityUpdateTimestamp = now;
            // FIX: Correct call to saveSessionData
            this.saveSessionData({ lastActive: now }); // Pass only the changed field
        }
    }
  }

  public clearSessionData(): void {
    try {
      this.sessionStorageService.removeItem(this.SESSION_KEY);
      this.lastActivityUpdateTimestamp = 0;
      this.logger.info('Session data cleared from storage.');
    } catch (e: any) {
       this.logger.error('Failed to clear session data', { error: e.message });
    }
  }

  // --- User Preferences Management ---

  public getUserPreferences(): UserPreferences { // Return default if not found
    return this.getSessionDataInternal().userPreferences || this.getDefaultUserPreferences();
  }

  public updateUserPreferences(preferences: Partial<UserPreferences>): void {
    const currentPrefs = this.getUserPreferences(); // Gets current or default
    const updatedPrefs = { ...currentPrefs, ...preferences };
    this.logger.info('Updating user preferences.');
    this.saveSessionData({ userPreferences: updatedPrefs });
  }

   private getDefaultUserPreferences(): UserPreferences {
       return {
           theme: 'system',
           chartTimeframe: '1d',
           notificationsEnabled: true,
           language: navigator.language || 'en-US' // Use browser language as default
       };
   }

  // --- Account Settings Management ---

  public getAccountSettings(): AccountSettings { // Return default if not found
    return this.getSessionDataInternal().accountSettings || this.getDefaultAccountSettings();
  }

  public updateAccountSettings(settings: Partial<AccountSettings>): void {
     const currentSettings = this.getAccountSettings(); // Gets current or default
     const updatedSettings = { ...currentSettings, ...settings };
     this.logger.info('Updating account settings in local session.');
     this.saveSessionData({ accountSettings: updatedSettings });
  }

   private getDefaultAccountSettings(): AccountSettings {
       return {
           defaultTradeSize: 1,
           riskLevel: 'medium',
           autoLogoutMinutes: 30,
           twoFactorEnabled: false
       };
   }

   // --- User ID Management ---

   public setUserId(userId: string | number | null): void {
       this.logger.info(`Setting session User ID to: ${userId}`);
       // Only update userId, preserve other fields
       this.saveSessionData({ userId: userId });
   }

    public getUserId(): string | number | null {
        return this.getSessionDataInternal()?.userId || null;
    }
}