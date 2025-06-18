// src/components/Dashboard/Container/ViewFactory.tsx
import React from 'react';
import { TabNode } from 'flexlayout-react';
import { Views } from './layoutTypes';
import MarketDataComponent from '../Viewers/MarketData/MarketDataDashboard';
import ConvictionBlotterComponent from '../Viewers/ConvictionBlotter/ConvictionBlotterDashboard';
import { AgGridColumnChooserController } from './Controllers';

interface ViewFactoryProps {
  columnChooserController: AgGridColumnChooserController;
  onViewColumnHandler?: (viewId: string, handler: () => void) => void;
}

export const createViewFactory = ({ columnChooserController, onViewColumnHandler }: ViewFactoryProps) => {
  return (node: TabNode) => {
    const component = node.getComponent();
    const viewId = node.getId(); // Get unique view ID
    
    switch(component) {
      case Views.MarketData:
        return (
          <MarketDataComponent 
            colController={columnChooserController}
            viewId="marketdata"
            onColumnHandlerReady={onViewColumnHandler ? (handler) => onViewColumnHandler(viewId, handler) : undefined}
          />
        );
      case Views.ConvictionBlotter:
        return (
          <ConvictionBlotterComponent 
            colController={columnChooserController}
            viewId="convictionblotter"
            onColumnHandlerReady={onViewColumnHandler ? (handler) => onViewColumnHandler(viewId, handler) : undefined}
          />
        );
      default:
        return <div>Unknown</div>;
    }
  };
};