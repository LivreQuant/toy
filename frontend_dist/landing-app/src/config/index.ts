// landing-app/src/config/index.ts
// Export everything from environment
export {
    environmentService,
    config,
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