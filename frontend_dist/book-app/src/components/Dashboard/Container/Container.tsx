import React, { useState, useEffect, useRef } from 'react';
import { Layout, Model } from 'flexlayout-react';
import 'flexlayout-react/style/dark.css';
import { Alignment, Button, Icon, Menu, MenuItem, Navbar, Popover, Position } from "@blueprintjs/core";
import { Views, ViewInfo } from './layoutTypes';
import { defaultLayoutJson } from './defaultLayout';
import { LayoutManager } from './LayoutManager';
import { createViewFactory } from './ViewFactory';
import { ConfigurationService } from './ConfigurationService';
import QuestionDialog from './QuestionDialog';
import ViewNameDialog from './ViewNameDialog';
import ColumnChooserAgGrid from '../AgGrid/ColumnChooseAgGrid';
import { QuestionDialogController, ViewNameDialogController, AgGridColumnChooserController } from './Controllers';
import { useAuth } from '../../Login/AuthProvider';

const Container = () => {
  // Access auth context to get desk_id
  
  // Create the initial model
  const [model, setModel] = useState<Model>(() => Model.fromJson(defaultLayoutJson));
  const [layoutUpdate, setLayoutUpdate] = useState(0);
  const layoutRef = useRef<Layout>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Initialize controllers and services
  const [questionDialogController] = useState(new QuestionDialogController());
  const [viewNameDialogController] = useState(new ViewNameDialogController());
  const [columnChooserController] = useState(new AgGridColumnChooserController());
  const [configService] = useState(new ConfigurationService());
  
  // Initialize layout manager after model is available
  const [layoutManager, setLayoutManager] = useState<LayoutManager | null>(null);
  const [availableViews, setAvailableViews] = useState<ViewInfo[]>([]);
  
  // Update model and force re-render
  const updateLayoutModel = (newModel: Model) => {
    setModel(newModel);
    setLayoutUpdate(prev => prev + 1);
  };
  
  // Initialize the layout manager when model changes
  useEffect(() => {
    if (model) {
      const manager = new LayoutManager({
        model,
        updateModel: updateLayoutModel,
        layoutRef
      });
      setLayoutManager(manager);
      setAvailableViews(manager.getAvailableViews());
    }
  }, [model, layoutUpdate]);
  
  // Load saved configuration on component mount
  useEffect(() => {
    const loadSavedLayout = async () => {
      
      setIsLoading(true);
      const newModel = await configService.loadSavedLayout("DESK_ID_0");
      setModel(newModel);
      setIsLoading(false);
    };
    
    loadSavedLayout();
  }, [configService]);
  
  // Factory function using the view factory module
  const factory = createViewFactory({ columnChooserController });
  
  const onSaveLayout = () => {    
    questionDialogController.open("Save Layout?", "Save Layout", async (response) => {
      if (response) {
        const success = await configService.saveLayout("DESK_ID_0", model);
        if (success) {
          alert("Layout and column configurations saved successfully");
        } else {
          alert("Failed to save layout");
        }
      }
    });
  };

  const onCancelAllOrders = () => {
    questionDialogController.open("Cancel all desk orders?", "Cancel All Desk Orders", (response) => {
      if (response) {
        // In a real app, we would cancel all orders here
        console.log("All orders canceled");
        alert("All orders canceled");
      }
    });
  };
  
  // Function to add a view
  const addView = (viewType: Views, defaultName: string) => {
    if (layoutRef.current && layoutManager) {
      viewNameDialogController.open(
        viewType,
        defaultName,
        layoutRef.current,
        updateLayoutModel
      );
    } else if (layoutManager) {
      layoutManager.addViewDirectly(viewType, defaultName);
    }
  };
  
  // Create menu items from available views
  const viewsMenu = (
    <Menu>
      {availableViews.length > 0 ? (
        availableViews.map((view) => (
          <MenuItem 
            key={view.type}
            icon={view.icon}
            text={view.name} 
            onClick={() => addView(view.type, view.name)} 
          />
        ))
      ) : (
        <MenuItem text="All views are already open" disabled={true} />
      )}
    </Menu>
  );

  if (isLoading) {
    return <div>Loading dashboard configuration...</div>;
  }

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <Navbar className="bp3-dark" style={{ width: '100%' }}>
        <Navbar.Group align={Alignment.LEFT}>
          <Navbar.Heading>Trading Dashboard</Navbar.Heading>
          <Navbar.Divider />
          <Popover content={viewsMenu} position={Position.BOTTOM}>
            <Button minimal={true} icon="add-to-artifact" text="Add View..." />
          </Popover>
          <Button minimal={true} icon="floppy-disk" text="Save Layout" onClick={onSaveLayout} />
        </Navbar.Group>
      </Navbar>
      
      {/* Main Content Area */}
      <div style={{ flex: 1, width: '100%', position: 'relative' }}>
        <Layout 
          ref={layoutRef}
          model={model} 
          factory={factory}
          onModelChange={() => setLayoutUpdate(prev => prev + 1)}
          onRenderTab={(node, renderValues) => {
            const component = node.getComponent();
            let icon;
            
            switch (component) {
              /*
              case Views.Portfolio:
                icon = <Icon icon="th" style={{ paddingRight: 5 }}></Icon>;
                break;
              case Views.MockMarketData:
                icon = <Icon icon="chart" style={{ paddingRight: 5 }}></Icon>;
                break;
              */
              case Views.MarketData:
                icon = <Icon icon="chart" style={{ paddingRight: 5 }}></Icon>;
                break;
              /*
              case Views.RiskAnalysis:
                icon = <Icon icon="shield" style={{ paddingRight: 5 }}></Icon>;
                break;
              case Views.Orders:
                icon = <Icon icon="shield" style={{ paddingRight: 5 }}></Icon>;
                break;
              */
              case Views.OrderBlotter:
                icon = <Icon icon="shield" style={{ paddingRight: 5 }}></Icon>;
                break;
              default:
                icon = <Icon icon="document" style={{ paddingRight: 5 }}></Icon>;
                break;
            }
            
            renderValues.leading = icon;
            return null;
          }}
        />
      </div>
      
      {/* Bottom Navbar */}
      <Navbar className="bp3-dark" style={{ width: '100%' }}>
        <Navbar.Group align={Alignment.LEFT}>
          <Navbar.Heading>'{"trader@$DESK_ID_0"}'</Navbar.Heading>
          <Navbar.Divider />
        </Navbar.Group>
        <Navbar.Group align={Alignment.RIGHT}>
          <Button minimal={true} icon="delete" text="Cancel All Desk Orders" onClick={onCancelAllOrders} />
        </Navbar.Group>
      </Navbar>
      
      {/* Hidden Dialogs */}
      <div style={{ position: "relative", zIndex: 10 }}>
        <QuestionDialog controller={questionDialogController} />
        <ViewNameDialog 
          controller={viewNameDialogController} 
          updateLayoutModel={updateLayoutModel} 
        />
        <ColumnChooserAgGrid controller={columnChooserController} />
      </div>
    </div>
  );
};

export default Container;