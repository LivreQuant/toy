// land-app/src/config/app-urls.ts
import { environmentService } from './environment';

export class AppUrlService {
  private static instance: AppUrlService;
  private envService = environmentService;

  private constructor() {}

  public static getInstance(): AppUrlService {
    if (!AppUrlService.instance) {
      AppUrlService.instance = new AppUrlService();
    }
    return AppUrlService.instance;
  }

  public getMainAppRoutes() {
    return this.envService.getMainAppRoutes();
  }

  // Updated to include 'signup' in the type, even though main app doesn't have it
  public getMainAppRoute(route: 'login' | 'signup' | 'home' | 'main' | 'profile' | 'books' | 'simulator'): string {
    const routes = this.envService.getMainAppRoutes();
    
    // Handle the fact that main app routes don't include 'signup'
    if (route === 'signup') {
      // Main app doesn't have signup, redirect to login instead
      return routes.login;
    }
        
    // Now we can safely access the route since we've filtered out 'signup' and handled 'app'
    type ValidMainAppRoute = Exclude<typeof route, 'signup' | 'app'>;
    return routes[route as ValidMainAppRoute];
  }

  public redirectToMainApp(path: string = '/home', replace: boolean = false): void {
    const mainAppUrl = this.envService.getMainAppUrl();
    const fullUrl = `${mainAppUrl}${path}`;
    
    if (this.envService.shouldLog()) {
      console.log(`🔗 Redirecting to main app: ${fullUrl}`);
    }

    if (replace) {
      window.location.replace(fullUrl);
    } else {
      window.location.href = fullUrl;
    }
  }

  public isMainAppUrl(url: string): boolean {
    const mainAppUrl = this.envService.getMainAppUrl();
    return url.startsWith(mainAppUrl);
  }

  public getLandAppUrl(): string {
    return this.envService.getLandAppConfig().baseUrl;
  }

  public redirectToLandApp(path: string = '/'): void {
    const landUrl = this.getLandAppUrl();
    const fullUrl = `${landUrl}${path}`;
    
    if (this.envService.shouldLog()) {
      console.log(`🔗 Redirecting to land: ${fullUrl}`);
    }
    
    window.location.href = fullUrl;
  }

  public buildUrl(baseUrl: string, path: string = '', params: Record<string, string> = {}): string {
    let url = `${baseUrl}${path}`;
    
    const searchParams = new URLSearchParams(params);
    const queryString = searchParams.toString();
    
    if (queryString) {
      url += `?${queryString}`;
    }
    
    return url;
  }

  public getCurrentDomainInfo() {
    return {
      hostname: window.location.hostname,
      port: window.location.port,
      protocol: window.location.protocol,
      href: window.location.href,
      environment: this.envService.getAppConfig().environment,
    };
  }
}

// Export singleton instance
export const appUrlService = AppUrlService.getInstance();

// Export commonly used methods for convenience
export const redirectToMainApp = appUrlService.redirectToMainApp.bind(appUrlService);
export const redirectToLandApp = appUrlService.redirectToLandApp.bind(appUrlService);
export const getMainAppRoute = appUrlService.getMainAppRoute.bind(appUrlService);