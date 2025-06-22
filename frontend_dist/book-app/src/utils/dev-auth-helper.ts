// frontend_dist/book-app/src/utils/dev-auth-helper.ts
import { getLogger } from '@trading-app/logging';
import ServiceManager from '../services/ServiceManager';

const logger = getLogger('DevAuthHelper');

export interface DevAuthConfig {
  enabled: boolean;
  credentials: {
    username: string;
    password: string;
  };
  defaultBookId: string;
}

export const DEV_AUTH_CONFIG: DevAuthConfig = {
  enabled: process.env.NODE_ENV === 'development' && process.env.REACT_APP_USE_DEV_AUTH === 'true',
  credentials: {
    username: process.env.REACT_APP_DEV_USERNAME || '',
    password: process.env.REACT_APP_DEV_PASSWORD || ''
  },
  defaultBookId: process.env.REACT_APP_DEFAULT_BOOK_ID || '26d41a49-ec77-45b3-aa4c-75cb202e5890'
};

// Debug logging for configuration
console.log('🔧 DEV_AUTH_CONFIG DEBUG:', {
  NODE_ENV: process.env.NODE_ENV,
  REACT_APP_USE_DEV_AUTH: process.env.REACT_APP_USE_DEV_AUTH,
  enabled: DEV_AUTH_CONFIG.enabled,
  hasUsername: !!DEV_AUTH_CONFIG.credentials.username,
  hasPassword: !!DEV_AUTH_CONFIG.credentials.password,
  defaultBookId: DEV_AUTH_CONFIG.defaultBookId
});

export async function attemptDevAuthentication(): Promise<boolean> {
  console.log('🔧 DEV MODE: attemptDevAuthentication called', {
    enabled: DEV_AUTH_CONFIG.enabled,
    hasUsername: !!DEV_AUTH_CONFIG.credentials.username,
    hasPassword: !!DEV_AUTH_CONFIG.credentials.password
  });

  if (!DEV_AUTH_CONFIG.enabled) {
    console.log('🔧 DEV MODE: Dev auth not enabled');
    return false;
  }

  if (!DEV_AUTH_CONFIG.credentials.username || !DEV_AUTH_CONFIG.credentials.password) {
    console.log('🔧 DEV MODE: Missing credentials');
    return false;
  }

  console.log('🔧 DEV MODE: Attempting development auto-login');
  console.log(`🔧 DEV MODE: Username: ${DEV_AUTH_CONFIG.credentials.username}`);

  try {
    const serviceManager = ServiceManager.getInstance();
    const services = await serviceManager.initialize();

    console.log('🔧 DEV MODE: Auth services created, attempting login...');

    // Attempt login
    const response = await services.apiClients.auth.login(
      DEV_AUTH_CONFIG.credentials.username, 
      DEV_AUTH_CONFIG.credentials.password
    );

    console.log('🔧 DEV MODE: Login response:', response);

    if (response.success && response.accessToken && response.refreshToken && response.userId) {
      // Store tokens
      const tokenData = {
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + (response.expiresIn || 3600) * 1000,
        userId: response.userId
      };
      
      services.authServices.tokenManager.storeTokens(tokenData);
      
      console.log('🔧 DEV MODE: Tokens stored successfully');
      console.log('🔧 DEV MODE: Auto-login successful');
      console.log(`🔧 DEV MODE: User ID: ${response.userId}`);
      
      // Verify tokens were stored
      const storedTokens = services.authServices.tokenManager.getTokens();
      console.log('🔧 DEV MODE: Verification - tokens in storage:', !!storedTokens);
      console.log('🔧 DEV MODE: Verification - isAuthenticated:', services.authServices.tokenManager.isAuthenticated());
      
      return true;
    } else if (response.requiresVerification) {
      console.warn('🔧 DEV MODE: Email verification required for dev user');
      console.warn(`🔧 DEV MODE: User ID: ${response.userId}, Email: ${response.email}`);
      return false;
    } else {
      console.error('🔧 DEV MODE: Auto-login failed:', response.error);
      return false;
    }
  } catch (error: any) {
    console.error('🔧 DEV MODE: Auto-login error:', error.message);
    console.error('🔧 DEV MODE: Full error:', error);
    return false;
  }
}

// Development navigation helpers
export const DEV_NAVIGATION_HELPERS = {
  switchBook: (bookId: string) => {
    console.log(`🔧 DEV MODE: Switching to book: ${bookId}`);
    window.location.href = `/${bookId}`;
  },
  
  goToDefaultBook: () => {
    console.log(`🔧 DEV MODE: Going to default book: ${DEV_AUTH_CONFIG.defaultBookId}`);
    window.location.href = `/${DEV_AUTH_CONFIG.defaultBookId}`;
  },
  
  goHome: () => {
    console.log('🔧 DEV MODE: Going to home (default book)');
    window.location.href = '/';
  },
  
  goToSimulator: (simulationId: string) => {
    console.log(`🔧 DEV MODE: Going to simulator: ${simulationId}`);
    window.location.href = `/simulator/${simulationId}`;
  },
  
  getCurrentBookId: () => {
    const pathParts = window.location.pathname.split('/');
    const bookId = pathParts[1];
    console.log(`🔧 DEV MODE: Current book ID: ${bookId}`);
    return bookId;
  },
  
  getUrlInfo: () => {
    const info = {
      href: window.location.href,
      pathname: window.location.pathname,
      currentBookId: DEV_NAVIGATION_HELPERS.getCurrentBookId(),
      defaultBookId: DEV_AUTH_CONFIG.defaultBookId
    };
    console.log('🔧 DEV MODE: URL Info:', info);
    return info;
  }
};

// FIXED: Updated development authentication helpers
export const DEV_AUTH_HELPERS = {
  manualLogin: async (username?: string, password?: string) => {
    const user = username || prompt('Enter username:');
    const pass = password || prompt('Enter password:');
    if (user && pass) {
      try {
        const serviceManager = ServiceManager.getInstance();
        const services = await serviceManager.initialize();
        
        const response = await services.apiClients.auth.login(user, pass);
        console.log('🔧 DEV MODE: Manual login response:', response);
        
        if (response.success && response.accessToken && response.refreshToken && response.userId) {
          const tokenData = {
            accessToken: response.accessToken,
            refreshToken: response.refreshToken,
            expiresAt: Date.now() + (response.expiresIn || 3600) * 1000,
            userId: response.userId
          };
          services.authServices.tokenManager.storeTokens(tokenData);
          console.log('🔧 DEV MODE: Manual login successful! Refresh the page.');
          return response;
        }
        return response;
      } catch (error: any) {
        console.error('🔧 DEV MODE: Manual login failed:', error.message);
        return { success: false, error: error.message };
      }
    }
  },
  
  showCurrentAuth: () => {
    try {
      const serviceManager = ServiceManager.getInstance();
      const connectionManager = serviceManager.getConnectionManager();
      
      console.log('🔍 Current Auth Status:');
      console.log('ServiceManager connection manager:', !!connectionManager);
      
      if (connectionManager) {
        console.log('Services are initialized, connection manager exists');
      } else {
        console.log('Services not yet initialized');
      }
      
      return { hasConnectionManager: !!connectionManager };
    } catch (error: any) {
      console.error('🔧 DEV MODE: Error getting auth status:', error.message);
      return null;
    }
  },
  
  clearAuth: () => {
    try {
      ServiceManager.reset();
      console.log('🗑️ Authentication and all services cleared. Refresh the page.');
    } catch (error: any) {
      console.error('🔧 DEV MODE: Error clearing auth:', error.message);
    }
  },
  
  copyTokens: () => {
    try {
      const tokenString = localStorage.getItem('auth_tokens');
      if (tokenString) {
        navigator.clipboard.writeText(tokenString);
        console.log('🔧 DEV MODE: Tokens copied to clipboard');
      } else {
        console.log('🔧 DEV MODE: No tokens found');
      }
    } catch (error: any) {
      console.error('🔧 DEV MODE: Error copying tokens:', error.message);
    }
  },
  
  injectTokens: (tokenData: any) => {
    try {
      localStorage.setItem('auth_tokens', JSON.stringify(tokenData));
      console.log('🔧 DEV MODE: Tokens injected. Refresh the page.');
    } catch (error: any) {
      console.error('🔧 DEV MODE: Error injecting tokens:', error.message);
    }
  }
};

// Development utilities
export const DEV_UTILITIES = {
  showConfig: () => {
    console.log('🔧 DEV MODE: Configuration:', {
      authConfig: DEV_AUTH_CONFIG,
      environment: {
        NODE_ENV: process.env.NODE_ENV,
        REACT_APP_ENV: process.env.REACT_APP_ENV,
        REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
        REACT_APP_WS_URL: process.env.REACT_APP_WS_URL
      }
    });
  },
  
  testApiConnection: async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/health`);
      const data = await response.json();
      console.log('🔧 DEV MODE: API Health Check:', data);
      return data;
    } catch (error: any) {
      console.error('🔧 DEV MODE: API connection failed:', error.message);
      return null;
    }
  },
  
  showLocalStorage: () => {
    const storage: { [key: string]: string | null } = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        storage[key] = localStorage.getItem(key);
      }
    }
    console.log('🔧 DEV MODE: Local Storage:', storage);
    return storage;
  },
  
  clearLocalStorage: () => {
    localStorage.clear();
    console.log('🔧 DEV MODE: Local storage cleared. Refresh the page.');
  }
};

// Combine all helpers
export const DEV_HELPERS = {
  ...DEV_NAVIGATION_HELPERS,
  ...DEV_AUTH_HELPERS,
  ...DEV_UTILITIES
};

// Make helpers available globally in development mode
if (process.env.NODE_ENV === 'development') {
  (window as any).devHelpers = DEV_HELPERS;
  (window as any).devNav = DEV_NAVIGATION_HELPERS;
  (window as any).devAuth = DEV_AUTH_HELPERS;
  (window as any).devUtils = DEV_UTILITIES;
  
  console.log('🔧 DEV MODE: Development helpers loaded!');
  console.log('');
  console.log('📍 NAVIGATION:');
  console.log('  devNav.switchBook("book-id") - Switch to specific book');
  console.log('  devNav.goToDefaultBook() - Go to default book');
  console.log('  devNav.goHome() - Go to home (default book)');
  console.log('  devNav.goToSimulator("sim-id") - Go to simulator');
  console.log('  devNav.getCurrentBookId() - Get current book ID');
  console.log('  devNav.getUrlInfo() - Show URL information');
  console.log('');
  console.log('🔒 AUTHENTICATION:');
  console.log('  devAuth.showCurrentAuth() - Show current auth state');
  console.log('  devAuth.manualLogin() - Login with prompts');
  console.log('  devAuth.manualLogin("user", "pass") - Direct login');
  console.log('  devAuth.clearAuth() - Clear authentication');
  console.log('  devAuth.copyTokens() - Copy tokens to clipboard');
  console.log('  devAuth.injectTokens(tokenData) - Inject token data');
  console.log('');
  console.log('🛠️ UTILITIES:');
  console.log('  devUtils.showConfig() - Show configuration');
  console.log('  devUtils.testApiConnection() - Test API connection');
  console.log('  devUtils.showLocalStorage() - Show local storage');
  console.log('  devUtils.clearLocalStorage() - Clear local storage');
  console.log('');
  console.log('🎯 SHORTCUTS:');
  console.log('  devHelpers - All helpers in one object');
  console.log(`  devNav.switchBook("${DEV_AUTH_CONFIG.defaultBookId}") - Go to your default book`);
}

export default DEV_HELPERS;