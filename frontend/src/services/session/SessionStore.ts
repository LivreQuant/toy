// src/services/session/SessionStore.ts
export interface SessionData {
  token?: string;
  sessionId: string;
  simulatorId?: string | null;
  podName?: string | null;
  lastActive: number;
  reconnectAttempts: number;
  connectionInfo?: {
    connectedAt: number;
    hostname: string;
    reconnectCount: number;
    initialPodName: string | null;
    currentPodName: string | null;
  };
}

export class SessionStore {
  private static readonly SESSION_KEY = 'trading_simulator_session';
  private static readonly SESSION_EXPIRY = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
  
  // Save session data with better EKS support
  public static saveSession(data: Partial<SessionData>): void {
    const existingData = this.getSession() || {
      reconnectAttempts: 0,
      lastActive: Date.now(),
      connectionInfo: {
        connectedAt: Date.now(),
        hostname: window.location.hostname,
        reconnectCount: 0,
        initialPodName: null,
        currentPodName: null
      }
    };
    
    // Update connection info
    const connectionInfo = {
      ...(existingData.connectionInfo || {}),
      hostname: window.location.hostname,
      reconnectCount: data.reconnectAttempts !== undefined ? 
                     data.reconnectAttempts : 
                     (existingData.connectionInfo?.reconnectCount || 0)
    };
    
    // Track pod changes
    if (data.podName) {
      if (!connectionInfo.initialPodName) {
        connectionInfo.initialPodName = data.podName;
      }
      connectionInfo.currentPodName = data.podName;
    }
    
    const updatedData = {
      ...existingData,
      ...data,
      lastActive: Date.now(),
      connectionInfo
    };
    
    // src/services/session/SessionStore.ts (continued)
  // Helper method to save to both storage types
  private static saveToStorage(data: any): void {
    try {
      localStorage.setItem(this.SESSION_KEY, JSON.stringify(data));
    } catch (e) {
      console.error('Failed to save to localStorage', e);
    }
    
    try {
      sessionStorage.setItem(this.SESSION_KEY, JSON.stringify(data));
    } catch (e) {
      console.error('Failed to save to sessionStorage', e);
    }
  }
  
  // Get session with fallback mechanism
  public static getSession(): SessionData | null {
    // Try localStorage first (faster)
    const localData = this.getSessionFromLocalStorage();
    
    if (localData) {
      return localData;
    }
    
    // Try sessionStorage as a backup
    return this.getSessionFromSessionStorage();
  }
  
  private static getSessionFromLocalStorage(): SessionData | null {
    try {
      const sessionStr = localStorage.getItem(this.SESSION_KEY);
      if (!sessionStr) return null;
      
      const session = JSON.parse(sessionStr) as SessionData;
      
      // Check if session has expired locally
      if (Date.now() - session.lastActive > this.SESSION_EXPIRY) {
        this.clearLocalStorage();
        return null;
      }
      
      return session;
    } catch (e) {
      console.error('Failed to parse session data from localStorage', e);
      this.clearLocalStorage();
      return null;
    }
  }
  
  private static getSessionFromSessionStorage(): SessionData | null {
    try {
      const sessionStr = sessionStorage.getItem(this.SESSION_KEY);
      if (!sessionStr) return null;
      
      const session = JSON.parse(sessionStr) as SessionData;
      
      // Check if session has expired locally
      if (Date.now() - session.lastActive > this.SESSION_EXPIRY) {
        this.clearSessionStorage();
        return null;
      }
      
      // Copy to localStorage for future access
      localStorage.setItem(this.SESSION_KEY, sessionStr);
      
      return session;
    } catch (e) {
      console.error('Failed to parse session data from sessionStorage', e);
      this.clearSessionStorage();
      return null;
    }
  }
  
  // Update activity timestamp
  public static updateActivity(): void {
    const session = this.getSession();
    if (session) {
      session.lastActive = Date.now();
      this.saveToStorage(session);
    }
  }
  
  // Clear all session data
  public static clearSession(): void {
    this.clearLocalStorage();
    this.clearSessionStorage();
  }
  
  private static clearLocalStorage(): void {
    localStorage.removeItem(this.SESSION_KEY);
  }
  
  private static clearSessionStorage(): void {
    sessionStorage.removeItem(this.SESSION_KEY);
  }
  
  // Reconnection attempt management
  public static incrementReconnectAttempts(): number {
    const session = this.getSession();
    if (!session) return 0;
    
    const reconnectAttempts = (session.reconnectAttempts || 0) + 1;
    session.reconnectAttempts = reconnectAttempts;
    
    if (session.connectionInfo) {
      session.connectionInfo.reconnectCount = reconnectAttempts;
    }
    
    this.saveToStorage(session);
    return reconnectAttempts;
  }
  
  public static resetReconnectAttempts(): void {
    const session = this.getSession();
    if (session) {
      session.reconnectAttempts = 0;
      this.saveToStorage(session);
    }
  }
  
  // EKS-specific helpers
  public static hasPodSwitched(): boolean {
    const session = this.getSession();
    if (!session || !session.connectionInfo) return false;
    
    const info = session.connectionInfo;
    return (
      !!info.initialPodName && 
      !!info.currentPodName && 
      info.initialPodName !== info.currentPodName
    );
  }
  
  public static getCurrentPodName(): string | null {
    const session = this.getSession();
    if (!session || !session.connectionInfo) return null;
    
    return session.connectionInfo.currentPodName;
  }
}