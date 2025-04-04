// src/services/session/session-manager.ts
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
  sessionId: string;
  simulatorId?: string | null;
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
  private static readonly DEVICE_ID_KEY = 'trading_device_id';
  private static readonly SESSION_ACTIVE_CHANNEL = 'trading_session_status';
  
  // Session validation check interval handle
  private static sessionCheckInterval: number | null = null;
  private static sessionInvalidatedHandler: ((reason: string) => void) | null = null;

  // Generate a unique device ID if not exists
  public static getDeviceId(): string {
    let deviceId = localStorage.getItem(this.DEVICE_ID_KEY);
    if (!deviceId) {
      deviceId = `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      localStorage.setItem(this.DEVICE_ID_KEY, deviceId);
    }
    return deviceId;
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
    } as SessionData; // Use type assertion to fix the type error
    
    try {
      localStorage.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
      localStorage.setItem(this.LAST_ACTIVE_KEY, Date.now().toString());
      
      // Notify other tabs about session update
      this.broadcastSessionUpdate(updatedData);
    } catch (e) {
      console.error('Failed to save session data', e);
    }
  }
  
  // Initialize session with user preferences and account settings
  public static async initSession(sessionId: string, userId: string | number): Promise<boolean> {
    const deviceId = this.getDeviceId();
    
    try {
      // Register this device with the backend
      const response = await fetch('/api/sessions/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId,
          userId,
          deviceId,
          userAgent: navigator.userAgent
        })
      });
      
      const result = await response.json();
      
      if (!result.success) {
        console.error('Failed to register session:', result.message);
        return false;
      }
      
      // If backend says this is the only active session, save it locally
      this.saveSession({
        sessionId,
        deviceId,
        lastActive: Date.now(),
        reconnectAttempts: 0
      });
      
      // Start session validity check
      this.startSessionValidityCheck();
      
      return true;
    } catch (error) {
      console.error('Session initialization failed:', error);
      return false;
    }
  }
  
  
  // Set up session validation check
  public static startSessionValidityCheck(checkIntervalMs: number = 30000): void {
    // Clear any existing interval
    if (this.sessionCheckInterval !== null) {
      window.clearInterval(this.sessionCheckInterval);
    }
    
    this.sessionCheckInterval = window.setInterval(async () => {
      try {
        const session = this.getSession();
        if (!session) return;
        
        // Call backend to validate session
        const response = await fetch('/api/sessions/validate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sessionId: session.sessionId,
            deviceId: session.deviceId
          })
        });
        
        const result = await response.json();
        
        if (!result.valid) {
          this.invalidateSession(result.reason || 'Session invalidated by server');
        }
      } catch (error) {
        console.error('Session validation check failed:', error);
      }
    }, checkIntervalMs);
  }
  
  // Stop session validity check
  public static stopSessionValidityCheck(): void {
    if (this.sessionCheckInterval !== null) {
      window.clearInterval(this.sessionCheckInterval);
      this.sessionCheckInterval = null;
    }
  }
  
  // Set handler for session invalidation
  public static setSessionInvalidatedHandler(handler: (reason: string) => void): void {
    this.sessionInvalidatedHandler = handler;
  }
  
  // Handle session invalidation
  public static invalidateSession(reason: string): void {
    // Clear all local session data
    this.clearSession();
    
    // Stop checking for validity
    this.stopSessionValidityCheck();
    
    // Show message to user and redirect to login
    if (this.sessionInvalidatedHandler) {
      this.sessionInvalidatedHandler(reason);
    } else {
      alert(`Your session has ended: ${reason}`);
      window.location.href = '/login';
    }
  }
  
  // Check if session is still valid
  private static async checkSessionValidity(): Promise<boolean> {
    const session = this.getSession();
    if (!session) return false;
    
    try {
      const response = await fetch('/api/sessions/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId: session.sessionId,
          deviceId: session.deviceId
        })
      });
      
      const result = await response.json();
      
      if (!result.valid) {
        this.invalidateSession(result.reason || 'Session is no longer valid');
        return false;
      }
      
      return true;
    } catch (error) {
      console.error('Session validation failed:', error);
      return false;
    }
  }
  
  // Listen for session changes from other tabs
  public static initSessionListener(callback: (session: SessionData) => void): () => void {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === this.SESSION_KEY && e.newValue) {
        try {
          const sessionData = JSON.parse(e.newValue) as SessionData;
          callback(sessionData);
        } catch (err) {
          console.error('Error parsing session data from storage event', err);
        }
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    // Set up BroadcastChannel for more reliable cross-tab communication
    if ('BroadcastChannel' in window) {
      const channel = new BroadcastChannel(this.SESSION_ACTIVE_CHANNEL);
      
      channel.onmessage = (event) => {
        // If another tab claims to be master and this tab is also master,
        // handle the conflict based on timestamp (newer wins)
        if (event.data.type === 'claim_master' && event.data.deviceId !== this.getDeviceId()) {
          const currentSession = this.getSession();
          
          if (currentSession?.isMaster && event.data.timestamp > (currentSession.lastActive || 0)) {
            // The other tab has a newer session, so this one should become non-master
            this.invalidateSession('Another browser tab has taken control of your trading session');
          }
        }
      };
      
      // Claim master status periodically
      if (this.getSession()?.isMaster) {
        const claimInterval = setInterval(() => {
          if (!this.getSession()?.isMaster) {
            clearInterval(claimInterval);
            return;
          }
          
          channel.postMessage({
            type: 'claim_master',
            deviceId: this.getDeviceId(),
            timestamp: Date.now()
          });
        }, 5000);
        
        // Return cleanup function
        const originalCleanup = () => window.removeEventListener('storage', handleStorageChange);
        
        return () => {
          originalCleanup();
          clearInterval(claimInterval);
          channel.close();
        };
      }
    }
    
    // Return function to remove the listener
    return () => window.removeEventListener('storage', handleStorageChange);
  }

  private static broadcastSessionUpdate(data: SessionData): void {
    // Use BroadcastChannel API if available
    if ('BroadcastChannel' in window) {
      const channel = new BroadcastChannel('trading_session_updates');
      channel.postMessage({
        type: 'session_updated',
        data: data,
        timestamp: Date.now(),
        deviceId: this.getDeviceId()
      });
      channel.close();
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
  
  // Get session ID
  public static getSessionId(): string | null {
    const session = this.getSession();
    return session ? session.sessionId : null;
  }
  
  // Set session ID
  public static setSessionId(sessionId: string): void {
    this.saveSession({ sessionId });
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
    
    // Also stop any active checks
    this.stopSessionValidityCheck();
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
  
  // Force this browser to become the master session
  public static async forceTakeMasterStatus(): Promise<boolean> {
    try {
      // Call backend to invalidate other sessions
      const response = await fetch('/api/sessions/force-master', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId: this.getSessionId(),
          deviceId: this.getDeviceId()
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        // Update local session state
        this.saveSession({ isMaster: true });
        
        // Broadcast to other tabs
        if ('BroadcastChannel' in window) {
          const channel = new BroadcastChannel(this.SESSION_ACTIVE_CHANNEL);
          channel.postMessage({
            type: 'claim_master',
            deviceId: this.getDeviceId(),
            timestamp: Date.now(),
            forced: true
          });
          channel.close();
        }
        
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to force master status:', error);
      return false;
    }
  }
}