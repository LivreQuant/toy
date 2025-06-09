// frontend_dist/landing-app/src/config/index.ts
// Export everything from environment
export {
    environmentService,
    landingConfig,
    mainAppRoutes,
    apiConfig,
    wsConfig
} from './environment';

// Export everything from app-urls (excluding mainAppRoutes to avoid conflict)
export {
    AppUrlService,
    appUrlService,
    redirectToMainApp,
    redirectToLanding,
    getMainAppRoute
} from './app-urls';

// Re-export from unified config for convenience
export { 
    config, 
    isLandingApp, 
    isMainApp, 
    isDevelopment, 
    isProduction, 
    shouldLog, 
    shouldDebug,
    APP_TYPE,
    ENVIRONMENT 
} from '@trading-app/config';