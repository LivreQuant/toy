// land-app/src/config/app-urls.ts
import { environmentService } from './environment';

// Define the route names type
type RouteNames = 'home' | 'signup' | 'login' | 'dashboard' | 'profile' | 'book' | 'simulator' | 'verifyEmail' | 'forgotPassword' | 'forgotUsername' | 'resetPassword' | 'enterpriseContact';

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

  // Updated to work with gateway routing
  public getMainAppRoute(route: 'login' | 'signup' | 'home' | 'main' | 'profile' | 'book' | 'simulator'): string {
    const routes = this.envService.getMainAppRoutes();
    
    // Handle the fact that signup is handled by landing app
    if (route === 'signup') {
      return this.envService.getSignupUrl();
    }
        
    // Now we can safely access the route
    type ValidMainAppRoute = Exclude<typeof route, 'signup'>;
    return routes[route as ValidMainAppRoute];
  }

  public redirectToMainApp(path: string = '/home', replace: boolean = false): void {
    const gatewayUrl = this.envService.getGatewayUrl();
    // Remove leading slash to avoid double slashes
    const cleanPath = path.startsWith('/') ? path.substring(1) : path;
    const fullUrl = `${gatewayUrl}/${cleanPath}`;
    
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
    const gatewayUrl = this.envService.getGatewayUrl();
    return url.startsWith(gatewayUrl);
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

  // New gateway-specific methods
  public getRoute(routeName: RouteNames): string {
    return this.envService.getRoute(routeName);
  }

  public redirectToRoute(routeName: RouteNames, replace: boolean = false): void {
    const url = this.getRoute(routeName);
    
    if (this.envService.shouldLog()) {
      console.log(`🔗 Redirecting to route ${routeName}: ${url}`);
    }

    if (replace) {
      window.location.replace(url);
    } else {
      window.location.href = url;
    }
  }
}

// Export singleton instance
export const appUrlService = AppUrlService.getInstance();

// Export commonly used methods for convenience
export const redirectToMainApp = appUrlService.redirectToMainApp.bind(appUrlService);
export const redirectToLandApp = appUrlService.redirectToLandApp.bind(appUrlService);
export const getMainAppRoute = appUrlService.getMainAppRoute.bind(appUrlService);
export const getRoute = appUrlService.getRoute.bind(appUrlService);
export const redirectToRoute = appUrlService.redirectToRoute.bind(appUrlService);