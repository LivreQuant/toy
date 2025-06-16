// frontend_dist/landing-app/src/services/credential-checker.ts
import { getLogger } from '@trading-app/logging';
import { TokenManager } from '@trading-app/auth';
import { environmentService } from '../config/environment';
import { landingApiService } from '../api';

const logger = getLogger('CredentialChecker');

export interface CredentialCheckResult {
  hasValidCredentials: boolean;
  shouldRedirect: boolean;
  redirectUrl?: string;
  userId?: string | number; // Changed from string | number | null to string | number | undefined
  error?: string;
}

class CredentialCheckerService {
  private static instance: CredentialCheckerService;
  private envService = environmentService;

  private constructor() {}

  public static getInstance(): CredentialCheckerService {
    if (!CredentialCheckerService.instance) {
      CredentialCheckerService.instance = new CredentialCheckerService();
    }
    return CredentialCheckerService.instance;
  }

  /**
   * Check if user has valid stored credentials and should be redirected to main app
   */
  async checkStoredCredentials(): Promise<CredentialCheckResult> {
    try {
      // Check if auto-redirect is enabled
      if (!this.envService.shouldAutoRedirectValidCredentials()) {
        if (this.envService.shouldLog()) {
          console.log('🔍 CREDENTIAL_CHECK: Auto-redirect disabled, skipping check');
        }
        return {
          hasValidCredentials: false,
          shouldRedirect: false
        };
      }

      if (this.envService.shouldLog()) {
        console.log('🔍 CREDENTIAL_CHECK: Starting credential validation');
      }

      // Get token manager from API service
      const tokenManager = await landingApiService.getTokenManager();
      
      // Quick check: are there any stored tokens?
      if (!tokenManager.isAuthenticated()) {
        if (this.envService.shouldLog()) {
          console.log('🔍 CREDENTIAL_CHECK: No stored tokens found');
        }
        return {
          hasValidCredentials: false,
          shouldRedirect: false
        };
      }

      const userId = tokenManager.getUserId();
      if (this.envService.shouldLog()) {
        console.log('🔍 CREDENTIAL_CHECK: Found stored tokens, validating...', { userId });
      }

      // Try to get a valid access token (this will auto-refresh if needed)
      const accessToken = await tokenManager.getAccessToken();
      
      if (!accessToken) {
        if (this.envService.shouldLog()) {
          console.log('🔍 CREDENTIAL_CHECK: Token refresh failed, clearing invalid tokens');
        }
        
        // Clear invalid tokens
        tokenManager.clearTokens();
        
        return {
          hasValidCredentials: false,
          shouldRedirect: false,
          error: 'Token refresh failed'
        };
      }

      // Tokens are valid, user should be redirected to main app
      const redirectUrl = this.envService.getMainAppRoutes().home;
      
      if (this.envService.shouldLog()) {
        console.log('🔍 CREDENTIAL_CHECK: Valid credentials found, should redirect', { 
          userId, 
          redirectUrl 
        });
      }

      return {
        hasValidCredentials: true,
        shouldRedirect: true,
        redirectUrl,
        userId: userId || undefined // Convert null to undefined
      };

    } catch (error: any) {
      logger.error('Error checking stored credentials', { error: error.message });
      
      // On error, clear any potentially corrupted tokens and don't redirect
      try {
        const tokenManager = await landingApiService.getTokenManager();
        tokenManager.clearTokens();
      } catch (clearError) {
        logger.error('Error clearing tokens after check failure', { error: clearError });
      }

      return {
        hasValidCredentials: false,
        shouldRedirect: false,
        error: error.message
      };
    }
  }

  /**
   * Perform the actual redirect to main app
   */
  redirectToMainApp(url?: string): void {
    const redirectUrl = url || this.envService.getMainAppRoutes().home;
    
    if (this.envService.shouldLog()) {
      console.log(`🔗 CREDENTIAL_CHECK: Redirecting to main app: ${redirectUrl}`);
    }

    // Force redirect to main app
    window.location.href = redirectUrl;
  }
}

// Export singleton instance
export const credentialChecker = CredentialCheckerService.getInstance();