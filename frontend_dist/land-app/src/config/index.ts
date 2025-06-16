// frontend_dist/land-app/src/config/index.ts
// Export everything from environment
export {
    environmentService,
    landConfig,
    mainAppRoutes,
    apiConfig,
    wsConfig
} from './environment';

// Export everything from app-urls
export {
    AppUrlService,
    appUrlService,
    redirectToMainApp,
    redirectToLandApp,
    getMainAppRoute,
    getRoute,
    redirectToRoute
} from './app-urls';

// Re-export from unified config for convenience
export { 
    config, 
    isLandApp, 
    isMainApp, 
    isDevelopment, 
    isProduction, 
    shouldLog, 
    shouldDebug,
    APP_TYPE,
    ENVIRONMENT,
    GATEWAY_URL,
    getAllRoutes
} from '@trading-app/config';