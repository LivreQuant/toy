import { Model, Node, TabNode, Actions, DockLocation, Layout } from 'flexlayout-react';
import { Views, ViewInfo, LayoutManagerProps } from './layoutTypes';

export class LayoutManager {
  private model: Model;
  private layoutRef: React.RefObject<Layout>;
  private updateModel: (newModel: Model) => void;

  constructor({ model, updateModel, layoutRef }: LayoutManagerProps) {
    this.model = model;
    this.updateModel = updateModel;
    this.layoutRef = layoutRef;
  }

  isViewInLayout = (viewType: Views): boolean => {
    let found = false;
    
    this.model.visitNodes((node: Node) => {
      if (node.getType() === "tab") {
        const tabNode = node as TabNode;
        if (tabNode.getComponent() === viewType) {
          found = true;
        }
      }
    });
    
    return found;
  };
  
  getAvailableViews = (): ViewInfo[] => {
    const views: ViewInfo[] = [];
    
    /*
    if (!this.isViewInLayout(Views.Portfolio)) {
      views.push({ type: Views.Portfolio, name: "Portfolio", icon: "th" });
    }
    
    if (!this.isViewInLayout(Views.MockMarketData)) {
      views.push({ type: Views.MockMarketData, name: "Mock Market Data", icon: "chart" });
    }
    */

    if (!this.isViewInLayout(Views.MarketData)) {
      views.push({ type: Views.MarketData, name: "Market Data", icon: "chart" });
    }
    
    /*
    if (!this.isViewInLayout(Views.RiskAnalysis)) {
      views.push({ type: Views.RiskAnalysis, name: "Risk Analysis", icon: "shield" });
    }
    
    if (!this.isViewInLayout(Views.Orders)) {
      views.push({ type: Views.Orders, name: "Orders", icon: "document-open" });
    }
    */
    
    if (!this.isViewInLayout(Views.OrderBlotter)) {
      views.push({ type: Views.OrderBlotter, name: "Order Blotter", icon: "import" });
    }
    return views;
  };
  
  addViewDirectly = (viewType: Views, viewName: string) => {
    const rootChildren = this.model.getRoot().getChildren();
    if (rootChildren.length === 0) return;
    
    const tabsetId = rootChildren[0].getId();
    
    this.model.doAction(
      Actions.addNode(
        {
          type: "tab",
          name: viewName,
          component: viewType
        },
        tabsetId,
        DockLocation.CENTER,
        -1
      )
    );
    
    this.updateModel(this.model);
  };
}