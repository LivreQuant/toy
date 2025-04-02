// src/services/session/session-store.ts
export interface SessionData {
    sessionId: string;
    simulatorId?: string | null;
    lastActive: number;
    reconnectAttempts: number;
    podName?: string | null;
  }
  
  export class SessionStore {
    private static readonly SESSION_KEY = 'trading_simulator_session';
    private static readonly SESSION_EXPIRY = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
    private static readonly LAST_ACTIVE_KEY = 'trading_session_last_active';
    private static readonly BROWSER_ID_KEY = 'trading_browser_id';
      
    // Generate a unique browser instance ID if not exists
    public static getBrowserId(): string {
      let browserId = localStorage.getItem(this.BROWSER_ID_KEY);
      if (!browserId) {
        browserId = `browser_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        localStorage.setItem(this.BROWSER_ID_KEY, browserId);
      }
      return browserId;
    }
    
    // Save session with broadcast to other tabs
    public static saveSession(data: Partial<SessionData>): void {
      const existingData = this.getSession() || {
        reconnectAttempts: 0,
        lastActive: Date.now()
      };
      
      const updatedData = {
        ...existingData,
        ...data,
        lastActive: Date.now()
      };
      
      try {
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
        localStorage.setItem(this.LAST_ACTIVE_KEY, Date.now().toString());
        
        // Notify other tabs about session update
        this.broadcastSessionUpdate(updatedData);
      } catch (e) {
        console.error('Failed to save session data', e);
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
          browserId: this.getBrowserId()
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
  }