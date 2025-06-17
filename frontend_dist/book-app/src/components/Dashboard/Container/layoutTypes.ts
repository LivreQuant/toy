import { TabNode, Layout, Model } from 'flexlayout-react';
import { IconName } from "@blueprintjs/icons";
import { ViewColumnState } from '../AgGrid/columnStateService';

// Define the view types
export enum Views {
  //Portfolio = "portfolio",
  //MockMarketData = "mockmarket",
  //RiskAnalysis = "risk",
  MarketData = "marketdata",
  //Orders = "orders",
  OrderBlotter = "orderblotter",
}

// Define the structure for the complete configuration
export interface CompleteConfiguration {
  layout: any;
  columnStates?: ViewColumnState;
}

export interface ViewInfo {
  type: Views;
  name: string;
  icon: IconName;
}

export interface LayoutManagerProps {
  model: Model;
  updateModel: (newModel: Model) => void;
  layoutRef: React.RefObject<Layout>;
}

