import { Model } from 'flexlayout-react';

//import { ClientConfigService } from '../../../services_old/api/clientConfigsService';
import { ClientConfigService } from '../../../services/api/services/clientConfigsService';

import { ColumnStateService } from '../AgGrid/columnStateService';
import { CompleteConfiguration } from './layoutTypes';
import { defaultLayoutJson } from './defaultLayout';

export class ConfigurationService {
  private configService: ClientConfigService;
  private columnStateService: ColumnStateService;

  constructor() {
    this.configService = ClientConfigService.getInstance();
    this.columnStateService = ColumnStateService.getInstance();
  }

  loadSavedLayout = async (deskId: string): Promise<Model> => {
    console.log(`[ConfigService] Loading layout for desk: ${deskId}`);
    
    try {
      const response = await this.configService.getClientConfig(deskId);
      
      if (response && response.config) {
        try {
          console.log(`[ConfigService] Found saved config, parsing`);
          const config: CompleteConfiguration = JSON.parse(response.config);
          
          if (config.layout) {
            console.log(`[ConfigService] Using saved layout`);
            const newModel = Model.fromJson(config.layout);
            
            if (config.columnStates) {
              this.columnStateService.resetColumnStates(config.columnStates);
            } else {
              this.columnStateService.resetColumnStates();
            }
            
            return newModel;
          }
        } catch (parseError) {
          console.warn(`[ConfigService] Could not parse saved config, using default`, parseError);
        }
      }
    } catch (error: any) {
      // Only log real errors, not the "not found" case which is already handled by clientConfigService
      if (error.message && !error.message.includes('not found') && !error.message.includes('Failed to fetch config')) {
        console.error(`[ConfigService] Error loading configuration:`, error);
      }
    }
    
    // For new users or any error cases, use default
    console.log(`[ConfigService] Using default layout for desk: ${deskId}`);
    const defaultModel = Model.fromJson(defaultLayoutJson);
    this.columnStateService.resetColumnStates();
    
    return defaultModel;
  };

  saveLayout = async (deskId: string, model: Model): Promise<boolean> => {
    try {
      console.log(`[ConfigService] Saving layout for desk: ${deskId}`);
      const layoutJson = model.toJson();
      const columnStates = this.columnStateService.getAllColumnStates();
      
      // Log any width information being saved
      Object.keys(columnStates).forEach(viewId => {
        const columnsWithWidth = Object.entries(columnStates[viewId])
          .filter(([, state]) => state.width !== undefined)
          .map(([colId, state]) => `${colId}: ${state.width}px`);
          
        if (columnsWithWidth.length > 0) {
          console.log(`[ConfigService] Saving column widths for ${viewId}:`, columnsWithWidth);
        }
      });
      
      const config: CompleteConfiguration = {
        layout: layoutJson,
        columnStates: columnStates
      };
      
      const configJson = JSON.stringify(config);
      console.log(`[ConfigService] Storing config to server (${configJson.length} bytes)`);
      
      await this.configService.storeClientConfig(deskId, configJson);
      console.log(`[ConfigService] Layout saved successfully`);
      
      return true;
    } catch (error) {
      console.error("[ConfigService] Error saving layout:", error);
      
      // Log more details about the error
      if (error instanceof Error) {
        console.error("[ConfigService] Error message:", error.message);
        console.error("[ConfigService] Stack trace:", error.stack);
      }
      
      return false;
    }
  };
}