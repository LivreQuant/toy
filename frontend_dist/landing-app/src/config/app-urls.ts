// landing-app/src/config/app-urls.ts
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

  public getMainAppRoute(route: 'login' | 'signup' | 'home' | 'app' | 'profile' | 'books' | 'simulator'): string {
    const routes = this.envService.getMainAppRoutes();
    return routes[route];
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

  public getLandingUrl(): string {
    return this.envService.getLandingConfig().baseUrl;
  }

  public redirectToLanding(path: string = '/'): void {
    const landingUrl = this.getLandingUrl();
    const fullUrl = `${landingUrl}${path}`;
    
    if (this.envService.shouldLog()) {
      console.log(`🔗 Redirecting to landing: ${fullUrl}`);
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

// Export commonly used methods for convenience - REMOVED mainAppRoutes to avoid conflict
export const redirectToMainApp = appUrlService.redirectToMainApp.bind(appUrlService);
export const redirectToLanding = appUrlService.redirectToLanding.bind(appUrlService);
export const getMainAppRoute = appUrlService.getMainAppRoute.bind(appUrlService);