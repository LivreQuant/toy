// src/components/Container/ViewFactory.tsx
import React from 'react';
import { TabNode } from 'flexlayout-react';
import { Views } from './layoutTypes';
//import MockMarketDataComponent from '../Viewers/MockMarketData/MarketData';
import MarketDataComponent from '../Viewers/MarketData/MarketDataDashboard';
//import PortfolioSummaryComponent from '../Viewers/Portfolio/PortfolioSummary';
//import RiskDataComponent from '../Viewers/Risk/RiskData';
//import OrdersComponent from '../Viewers/Orders/Orders';
import OrderBlotterComponent from '../Viewers/OrderBlotter/OrderBlotterDashboard';
import { AgGridColumnChooserController } from './Controllers';

interface ViewFactoryProps {
  columnChooserController: AgGridColumnChooserController;
}

export const createViewFactory = ({ columnChooserController }: ViewFactoryProps) => {
  return (node: TabNode) => {
    const component = node.getComponent();
    
    switch(component) {
      /*
      case Views.Portfolio:
        return (
          <PortfolioSummaryComponent 
            colController={columnChooserController} 
            viewId="portfolio"
          />
        );
      case Views.MockMarketData:
        return (
          <MockMarketDataComponent 
            colController={columnChooserController}
            viewId="mockmarket"
          />
        );
      */
      case Views.MarketData:
        return (
          <MarketDataComponent 
            colController={columnChooserController}
            viewId="marketdata"
          />
        );
      /*
      case Views.RiskAnalysis:
        return (
          <RiskDataComponent 
            colController={columnChooserController}
            viewId="risk"
          />
        );
      case Views.Orders:
        return (
          <OrdersComponent 
            colController={columnChooserController}
            viewId="orders"
          />
        );
      */
      case Views.OrderBlotter:
        return (
          <OrderBlotterComponent 
            colController={columnChooserController}
            viewId="orderblotter"
          />
        );
      default:
        return <div>Unknown</div>;
    }
  };
};