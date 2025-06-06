// frontend_dist/packages/api/src/factories/api-factory.ts
import { TokenManager } from '@trading-app/auth';
import { HttpClient } from '../core/http-client';
import { AuthClient } from '../clients/auth-client';
import { BookClient } from '../clients/book-client';
import { ConvictionClient } from '../clients/conviction-client';
import { FundClient } from '../clients/fund-client';

export interface ApiClients {
  auth: AuthClient;
  book: BookClient;
  conviction: ConvictionClient;
  fund: FundClient;
}

export class ApiFactory {
  /**
   * Creates all API clients with shared dependencies
   */
  static createClients(tokenManager: TokenManager): ApiClients {
    const httpClient = new HttpClient(tokenManager);
    
    return {
      auth: new AuthClient(httpClient, tokenManager),
      book: new BookClient(httpClient, tokenManager),
      conviction: new ConvictionClient(httpClient, tokenManager),
      fund: new FundClient(httpClient, tokenManager)
    };
  }

  /**
   * Create individual clients if needed
   */
  static createAuthClient(tokenManager: TokenManager): AuthClient {
    const httpClient = new HttpClient(tokenManager);
    return new AuthClient(httpClient, tokenManager);
  }

  static createBookClient(tokenManager: TokenManager): BookClient {
    const httpClient = new HttpClient(tokenManager);
    return new BookClient(httpClient, tokenManager);
  }

  static createConvictionClient(tokenManager: TokenManager): ConvictionClient {
    const httpClient = new HttpClient(tokenManager);
    return new ConvictionClient(httpClient, tokenManager);
  }

  static createFundClient(tokenManager: TokenManager): FundClient {
    const httpClient = new HttpClient(tokenManager);
    return new FundClient(httpClient, tokenManager);
  }
}