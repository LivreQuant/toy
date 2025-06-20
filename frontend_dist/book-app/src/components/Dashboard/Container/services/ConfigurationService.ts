// frontend_dist/book-app/src/components/Dashboard/Container/ConfigurationService.ts
import { Model } from 'flexlayout-react';
import { ClientConfigService } from '../../../../services/client-config/client-config-service';
import { ColumnStateService } from '../../AgGrid/services/columnStateService';
import { CompleteConfiguration } from '../core/layoutTypes';
import { defaultLayoutJson } from '../utils/defaultLayout';
import { getLogger } from '@trading-app/logging';

export class ConfigurationService {
  private logger = getLogger('ConfigurationService');
  private configService: ClientConfigService;
  private columnStateService: ColumnStateService;

  constructor(configService: ClientConfigService) {
    this.configService = configService;
    this.columnStateService = ColumnStateService.getInstance();
  }

  loadSavedLayout = async (bookId: string): Promise<Model> => {
    this.logger.info(`[ConfigService] Loading layout for book: ${bookId}`);
    
    try {
      const response = await this.configService.getClientConfig(bookId);
      
      if (response.success && response.config) {
        try {
          this.logger.info(`[ConfigService] Found saved config, parsing`);
          const config: CompleteConfiguration = JSON.parse(response.config);
          
          if (config.layout) {
            this.logger.info(`[ConfigService] Using saved layout`);
            const newModel = Model.fromJson(config.layout);
            
            if (config.columnStates) {
              this.columnStateService.resetColumnStates(config.columnStates);
            } else {
              this.columnStateService.resetColumnStates();
            }
            
            return newModel;
          }
        } catch (parseError) {
          this.logger.warn(`[ConfigService] Could not parse saved config, using default`, parseError);
        }
      } else if (!response.success && response.error) {
        this.logger.info(`[ConfigService] No saved config found: ${response.error}`);
      }
    } catch (error: any) {
      this.logger.error(`[ConfigService] Error loading configuration:`, error);
    }
    
    // For new users or any error cases, use default
    this.logger.info(`[ConfigService] Using default layout for book: ${bookId}`);
    const defaultModel = Model.fromJson(defaultLayoutJson);
    this.columnStateService.resetColumnStates();
    
    return defaultModel;
  };

  saveLayout = async (bookId: string, model: Model): Promise<boolean> => {
    try {
      this.logger.info(`[ConfigService] Saving layout for book: ${bookId}`);
      const layoutJson = model.toJson();
      const columnStates = this.columnStateService.getAllColumnStates();
      
      // Log any width information being saved
      Object.keys(columnStates).forEach(viewId => {
        const columnsWithWidth = Object.entries(columnStates[viewId])
          .filter(([, state]) => state.width !== undefined)
          .map(([colId, state]) => `${colId}: ${state.width}px`);
          
        if (columnsWithWidth.length > 0) {
          this.logger.info(`[ConfigService] Saving column widths for ${viewId}:`, columnsWithWidth);
        }
      });
      
      const config: CompleteConfiguration = {
        layout: layoutJson,
        columnStates: columnStates
      };
      
      const configJson = JSON.stringify(config);
      this.logger.info(`[ConfigService] Storing config to server (${configJson.length} bytes)`);
      
      const success = await this.configService.storeClientConfig(bookId, configJson);
      
      if (success) {
        this.logger.info(`[ConfigService] Layout saved successfully`);
        return true;
      } else {
        this.logger.error(`[ConfigService] Failed to save layout`);
        return false;
      }
    } catch (error) {
      this.logger.error("[ConfigService] Error saving layout:", error);
      
      // Log more details about the error
      if (error instanceof Error) {
        this.logger.error("[ConfigService] Error message:", error.message);
        this.logger.error("[ConfigService] Stack trace:", error.stack);
      }
      
      return false;
    }
  };
}