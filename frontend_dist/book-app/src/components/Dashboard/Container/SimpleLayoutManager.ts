// frontend_dist/book-app/src/components/Dashboard/Container/SimpleLayoutManager.ts
import { Model } from 'flexlayout-react';
import { Views, ViewInfo } from './layoutTypes';

/**
 * Simplified Layout Manager until we implement the full one
 */
export class SimpleLayoutManager {
  constructor(private model: Model) {}

  getAllViewTypes(): ViewInfo[] {
    return [
      { type: Views.MarketData, name: 'Market Data', icon: 'chart' },
      { type: Views.ConvictionBlotter, name: 'Conviction Blotter', icon: 'shield' }
    ];
  }

  getViewDescription(viewType: Views): string {
    const descriptions: Record<Views, string> = {
      [Views.MarketData]: 'Real-time market data and price feeds',
      [Views.ConvictionBlotter]: 'Trading convictions and position management'
    };
    return descriptions[viewType] || 'Custom view component';
  }

  getViewDefaultName(viewType: Views): string {
    const defaultNames: Record<Views, string> = {
      [Views.MarketData]: 'Market Data View',
      [Views.ConvictionBlotter]: 'Conviction Blotter'
    };
    return defaultNames[viewType] || `${viewType} View`;
  }

  addView(viewType: Views, viewName: string): Model {
    const newTabId = `${viewType}_${Date.now()}`;
    
    // Create a properly typed tab node
    const newTabJson = {
      type: 'tab' as const,
      id: newTabId,
      name: viewName,
      component: viewType,
      config: {}
    };
    
    // Get current layout and add to the first tabset
    const currentJson = this.model.toJson();
    
    // Find the first tabset and add the new tab
    if (currentJson.layout.children && currentJson.layout.children.length > 0) {
      const firstChild = currentJson.layout.children[0];
      
      // Check if it's a tabset and cast to any to bypass TypeScript strictness
      if (firstChild.type === 'tabset' && firstChild.children) {
        // Use type assertion to bypass the strict typing issue
        (firstChild.children as any[]).push(newTabJson);
      } else {
        // If it's not a tabset, we need to create one or find an existing one
        // For now, let's add to the layout as a new tabset
        const newTabset = {
          type: 'tabset' as const,
          id: `tabset_${Date.now()}`,
          children: [newTabJson]
        };
        (currentJson.layout.children as any[]).push(newTabset);
      }
    } else {
      // No children, create a new tabset
      const newTabset = {
        type: 'tabset' as const,
        id: `tabset_${Date.now()}`,
        children: [newTabJson]
      };
      currentJson.layout.children = [newTabset as any];
    }
    
    return Model.fromJson(currentJson);
  }

  async saveLayout(): Promise<void> {
    // For now, just save to localStorage
    const layoutJson = this.model.toJson();
    localStorage.setItem('dashboard_layout', JSON.stringify(layoutJson));
    console.log('✅ Layout saved to localStorage');
  }

  async loadLayout(): Promise<Model | null> {
    try {
      const saved = localStorage.getItem('dashboard_layout');
      if (saved) {
        const layoutJson = JSON.parse(saved);
        return Model.fromJson(layoutJson);
      }
    } catch (error) {
      console.error('❌ Failed to load layout from localStorage:', error);
    }
    return null;
  }
}