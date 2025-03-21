// src/services/session/SessionStore.ts
export interface SessionData {
    token: string;
    sessionId: string;
    simulatorId?: string;
    lastActive: number;
    reconnectAttempts: number;
  }
  
  export class SessionStore {
    private static readonly SESSION_KEY = 'trading_simulator_session';
    private static readonly SESSION_EXPIRY = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
    
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
      
      localStorage.setItem(this.SESSION_KEY, JSON.stringify(updatedData));
    }
    
    public static getSession(): SessionData | null {
      const sessionStr = localStorage.getItem(this.SESSION_KEY);
      if (!sessionStr) return null;
      
      try {
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
    
    public static updateActivity(): void {
      const session = this.getSession();
      if (session) {
        session.lastActive = Date.now();
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(session));
      }
    }
    
    public static clearSession(): void {
      localStorage.removeItem(this.SESSION_KEY);
    }
    
    public static incrementReconnectAttempts(): number {
      const session = this.getSession();
      if (!session) return 0;
      
      session.reconnectAttempts += 1;
      localStorage.setItem(this.SESSION_KEY, JSON.stringify(session));
      return session.reconnectAttempts;
    }
    
    public static resetReconnectAttempts(): void {
      const session = this.getSession();
      if (session) {
        session.reconnectAttempts = 0;
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(session));
      }
    }
  }