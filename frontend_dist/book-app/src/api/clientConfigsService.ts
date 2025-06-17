// frontend_dist/book-app/src/services/api/services/clientConfigsService.ts

export interface ClientConfigResponse {
    config: string | null;
    success: boolean;
    error?: string;
  }
  
  export class ClientConfigService {
    private static instance: ClientConfigService;
  
    private constructor() {
      // Private constructor for singleton
    }
  
    static getInstance(): ClientConfigService {
      if (!ClientConfigService.instance) {
        ClientConfigService.instance = new ClientConfigService();
      }
      return ClientConfigService.instance;
    }
  
    async getClientConfig(deskId: string): Promise<ClientConfigResponse> {
      // Always return null config (no saved config found)
      return {
        config: null,
        success: true
      };
    }
  
    async storeClientConfig(deskId: string, config: string): Promise<boolean> {
      // Do nothing, just return success
      console.log(`[ClientConfigService] Would store config for desk: ${deskId} (${config.length} bytes)`);
      return true;
    }
  }