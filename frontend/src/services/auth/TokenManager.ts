// src/services/auth/TokenManager.ts
export class TokenManager {
    private static readonly TOKEN_EXPIRY_BUFFER = 5 * 60 * 1000; // 5 minutes before expiry
    private refreshTimer: NodeJS.Timeout | null = null;
    
    // Start watching token expiry and refresh when needed
    public startTokenRefresh(onRefreshNeeded: () => Promise<boolean>): void {
      this.stopTokenRefresh(); // Clear any existing timers
      
      // Check token expiry every minute
      this.refreshTimer = setInterval(() => {
        const tokenData = this.getTokenData();
        if (tokenData && this.isTokenExpiringSoon(tokenData.exp)) {
          onRefreshNeeded();
        }
      }, 60000);
    }
    
    public stopTokenRefresh(): void {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
    }
    
    private getTokenData(): any {
      const token = localStorage.getItem('token');
      if (!token) return null;
      
      try {
        // JWT tokens are base64 encoded with 3 parts: header.payload.signature
        const payload = token.split('.')[1];
        return JSON.parse(atob(payload));
      } catch (e) {
        console.error('Failed to parse JWT token', e);
        return null;
      }
    }
    
    private isTokenExpiringSoon(expiryTimestamp: number): boolean {
      const expiryMs = expiryTimestamp * 1000; // Convert to milliseconds
      return Date.now() > expiryMs - TokenManager.TOKEN_EXPIRY_BUFFER;
    }
  }