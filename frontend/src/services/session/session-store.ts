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
    
    // Save session data
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