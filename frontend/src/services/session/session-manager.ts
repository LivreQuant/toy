// src/services/session/session-manager.ts
import { DeviceIdManager } from '../../utils/device-id-manager';

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  chartTimeframe: '1d' | '1w' | '1m' | '3m' | '1y';
  notifications: boolean;
  language: string;
}

export interface AccountSettings {
  defaultTradeSize: number;
  riskLevel: 'low' | 'medium' | 'high';
  autoLogoutMinutes: number;
  twoFactorEnabled: boolean;
}

export interface SessionData {
  deviceId: string;  // Unique identifier for this device/browser
  lastActive: number;
  reconnectAttempts: number;
  podName?: string | null;
  userPreferences?: UserPreferences;
  accountSettings?: AccountSettings;
  isMaster?: boolean; // Indicates if this is the primary session
}

export class SessionManager {
  private static readonly SESSION_KEY = 'trading_simulator_session';
  private static readonly SESSION_EXPIRY = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
  private static readonly LAST_ACTIVE_KEY = 'trading_session_last_active';
  
  // Generate a unique device ID if not exists
  public static getDeviceId(): string {
    return DeviceIdManager.getDeviceId();
  }
  
  // Save session with broadcast to other tabs
  public static saveSession(data: Partial<SessionData>): void {
    const existingData = this.getSession() || {
      reconnectAttempts: 0,
      lastActive: Date.now(),
      deviceId: this.getDeviceId(),
      isMaster: true
    };
    
    const updatedData = {
      ...existingData,
      ...data,
      lastActive: Date.now()
    } as SessionData;
    
    try {
      localStorage.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
      localStorage.setItem(this.LAST_ACTIVE_KEY, Date.now().toString());
    } catch (e) {
      console.error('Failed to save session data', e);
    }
  }

  // Get session data
  public static getSession(): SessionData | null {
    try {
      const sessionStr = localStorage.getItem(this.SESSION_KEY);
      if (!sessionStr) return null;
      
      const session = JSON.parse(sessionStr) as SessionData;
      
      // Check if session has expired locally
      if (Date.now() - session.lastActive > this.SESSION_EXPIRY) {
        this.clearSession();
        return null;
      }
      
      return session;
    } catch (e) {
      console.error('Failed to parse session data', e);
      this.clearSession();
      return null;
    }
  }
  
  // Update activity timestamp
  public static updateActivity(): void {
    const session = this.getSession();
    if (session) {
      session.lastActive = Date.now();
      try {
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(session));
      } catch (e) {
        console.error('Failed to update session activity', e);
      }
    }
  }
  
  // Clear session data
  public static clearSession(): void {
    localStorage.removeItem(this.SESSION_KEY);
  }
  
  // Reconnection attempt management
  public static incrementReconnectAttempts(): number {
    const session = this.getSession();
    if (!session) return 0;
    
    const reconnectAttempts = (session.reconnectAttempts || 0) + 1;
    this.saveSession({ reconnectAttempts });
    return reconnectAttempts;
  }
  
  public static resetReconnectAttempts(): void {
    this.saveSession({ reconnectAttempts: 0 });
  }
  
  // User preferences management
  public static getUserPreferences(): UserPreferences | null {
    const session = this.getSession();
    return session?.userPreferences || null;
  }
  
  public static updateUserPreferences(preferences: Partial<UserPreferences>): void {
    const session = this.getSession();
    if (!session) return;
    
    this.saveSession({
      userPreferences: {
        ...session.userPreferences,
        ...preferences
      } as UserPreferences
    });
  }
  
  // Account settings management
  public static getAccountSettings(): AccountSettings | null {
    const session = this.getSession();
    return session?.accountSettings || null;
  }
  
  public static updateAccountSettings(settings: Partial<AccountSettings>): void {
    const session = this.getSession();
    if (!session) return;
    
    this.saveSession({
      accountSettings: {
        ...session.accountSettings,
        ...settings
      } as AccountSettings
    });
  }
}