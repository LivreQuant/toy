// src/components/Dashboard/Container/Container.tsx
import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { Layout, Model, TabNode } from 'flexlayout-react';
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
import CustomModal from './CustomModal';
import './Container.css';

// ViewNameStep component definition (keeping the existing implementation)
interface ViewNameStepProps {
  selectedViewType: Views;
  onBack: () => void;
  onCancel: () => void;
  onConfirm: (viewName: string) => void;
  getAllViewTypes: () => ViewInfo[];
  getViewDescription: (viewType: Views) => string;
  getViewDefaultName: (viewType: Views) => string;
}

const ViewNameStep: React.FC<ViewNameStepProps> = ({
  selectedViewType,
  onBack,
  onCancel,
  onConfirm,
  getAllViewTypes,
  getViewDescription,
  getViewDefaultName
}) => {
  const [viewName, setViewName] = useState('');

  useEffect(() => {
    if (selectedViewType) {
      setViewName(getViewDefaultName(selectedViewType));
    }
  }, [selectedViewType, getViewDefaultName]);

  const selectedViewInfo = getAllViewTypes().find(v => v.type === selectedViewType);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (viewName.trim()) {
      onConfirm(viewName.trim());
    }
  };

  return (
    <div>
      <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Configure New View</h4>
      <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
        You've selected <strong>{selectedViewInfo?.name}</strong>. Now give it a custom name:
      </p>
      
      <div style={{
        padding: '12px 16px',
        backgroundColor: '#e3f2fd',
        borderRadius: '6px',
        marginBottom: '20px',
        border: '1px solid #90caf9'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <Icon icon={selectedViewInfo?.icon as any} style={{ marginRight: '8px', color: '#1976d2' }} />
          <strong style={{ color: '#1976d2' }}>{selectedViewInfo?.name}</strong>
        </div>
        <div style={{ fontSize: '14px', color: '#555' }}>
          {getViewDescription(selectedViewType)}
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontWeight: '500',
            fontSize: '14px',
            color: '#333'
          }}>
            View Name <span style={{ color: '#e74c3c' }}>*</span>
          </label>
          <input
            type="text"
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            placeholder="Enter a name for this view..."
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              transition: 'border-color 0.2s'
            }}
            autoFocus
            required
          />
          {!viewName.trim() && (
            <div style={{ 
              fontSize: '12px', 
              color: '#e74c3c', 
              marginTop: '4px' 
            }}>
              Please enter a name for your view
            </div>
          )}
        </div>

        <div style={{ 
          display: 'flex', 
          gap: '12px', 
          justifyContent: 'flex-end',
          paddingTop: '20px',
          borderTop: '1px solid #eee'
        }}>
          <button 
            type="button"
            onClick={onBack}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#f8f9fa', 
              color: '#6c757d', 
              border: '1px solid #dee2e6', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            ← Back
          </button>
          <button 
            type="button"
            onClick={onCancel}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#6c757d', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button 
            type="submit"
            disabled={!viewName.trim()}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: viewName.trim() ? '#28a745' : '#6c757d',
              color: 'white', 
              border: 'none', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: viewName.trim() ? 'pointer' : 'not-allowed',
              opacity: viewName.trim() ? 1 : 0.6
            }}
          >
            ➕ Create View
          </button>
        </div>
      </form>
    </div>
  );
};

const Container = () => {
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
  
  // Custom modal states
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [saveLayoutModalOpen, setSaveLayoutModalOpen] = useState(false);
  const [addViewModalOpen, setAddViewModalOpen] = useState(false);
  const [selectedViewType, setSelectedViewType] = useState<Views | null>(null);
  const [cancelOrdersModalOpen, setCancelOrdersModalOpen] = useState(false);

  // Update model and force re-render
  const updateLayoutModel = (newModel: Model) => {
    console.log('📝 Container: Updating layout model');
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
      console.log('📋 Container: Layout manager initialized, available views:', manager.getAvailableViews());
    }
  }, [model, layoutUpdate]);
  
  // Load saved configuration on component mount
  useEffect(() => {
    const loadSavedLayout = async () => {
      console.log('🔄 Container: Loading saved layout');
      setIsLoading(true);
      const newModel = await configService.loadSavedLayout("DESK_ID_0");
      setModel(newModel);
      setIsLoading(false);
      console.log('✅ Container: Layout loaded');
    };
    
    loadSavedLayout();
  }, [configService]);
  
  // Factory function using the view factory module
  const factory = createViewFactory({ columnChooserController });
  
  // Custom modal handlers
  const handleSaveLayoutConfirm = async () => {
    console.log('💾 Container: Saving layout via custom modal');
    setSaveLayoutModalOpen(false);
    
    const success = await configService.saveLayout("DESK_ID_0", model);
    if (success) {
      alert("Layout and column configurations saved successfully");
    } else {
      alert("Failed to save layout");
    }
  };

  const handleAddViewConfirm = (viewType: Views, viewName: string) => {
    if (layoutManager) {
      console.log('➕ Container: Adding view via custom modal:', viewType, viewName);
      layoutManager.addViewDirectly(viewType, viewName);
      setAddViewModalOpen(false);
      setSelectedViewType(null);
    }
  };

  const handleCancelOrdersConfirm = () => {
    console.log('🗑️ Container: Cancelling all orders via custom modal');
    setCancelOrdersModalOpen(false);
    console.log("All orders canceled");
    alert("All orders canceled");
  };
  
  // Main handlers
  const onSaveLayout = () => {
    console.log('💾 Container: Save Layout button clicked - using CUSTOM MODAL');
    setSaveLayoutModalOpen(true);
  };

  const onCancelAllOrders = () => {
    console.log('🗑️ Container: Cancel All Orders button clicked - using CUSTOM MODAL');
    setCancelOrdersModalOpen(true);
  };

  // Direct handler for Add View button
  const onAddView = () => {
    console.log('➕ Container: Add View button clicked - opening custom modal');
    setAddViewModalOpen(true);
  };
  
  // Test functions for debugging Blueprint dialogs
  const testCustomModal = () => {
    console.log('🧪 Testing Custom Modal');
    setTestModalOpen(true);
  };

  const testQuestionDialog = () => {
    console.log('🧪 Testing Question Dialog directly');
    questionDialogController.open("Test Question?", "Test Dialog", (response) => {
      console.log('🧪 Test dialog response:', response);
      alert(`Test response: ${response}`);
    });
  };

  const testViewNameDialog = () => {
    console.log('🧪 Testing ViewName Dialog directly');
    if (layoutRef.current) {
      viewNameDialogController.open(
        Views.MarketData,
        "Test View",
        layoutRef.current,
        updateLayoutModel
      );
    }
  };

  const testColumnChooser = () => {
    console.log('🧪 Testing Column Chooser directly');
    columnChooserController.open(
      "Test Table",
      [
        { colId: 'test1', hide: false },
        { colId: 'test2', hide: true }
      ],
      [
        { getColId: () => 'test1', getDefinition: () => ({ headerName: 'Test 1' }) },
        { getColId: () => 'test2', getDefinition: () => ({ headerName: 'Test 2' }) }
      ] as any,
      (result) => {
        console.log('🧪 Column chooser result:', result);
      }
    );
  };

  // Helper function to get view description
  const getViewDescription = (viewType: Views) => {
    switch (viewType) {
      case Views.MarketData:
        return 'Real-time market data display with price feeds and charts';
      case Views.OrderBlotter:
        return 'Order management interface for viewing and managing trades';
      default:
        return 'A new dashboard view';
    }
  };

  // Helper function to get view default name
  const getViewDefaultName = (viewType: Views) => {
    switch (viewType) {
      case Views.MarketData:
        return 'Market Data';
      case Views.OrderBlotter:
        return 'Order Blotter';
      default:
        return 'New View';
    }
  };

  // Get all possible view types (not just available ones)
  const getAllViewTypes = (): ViewInfo[] => {
    return [
      { type: Views.MarketData, name: "Market Data", icon: "chart" },
      { type: Views.OrderBlotter, name: "Order Blotter", icon: "import" }
    ];
  };

  if (isLoading) {
    return <div>Loading dashboard configuration...</div>;
  }

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Debug Panel - Remove in production */}
      <div style={{ 
        backgroundColor: '#ffe6e6', 
        padding: '10px', 
        fontSize: '12px',
        borderBottom: '1px solid #ccc',
        display: 'flex',
        gap: '10px',
        flexWrap: 'wrap',
        alignItems: 'center'
      }}>
        <span>🐛 DEBUG MODALS:</span>
        <button onClick={testCustomModal} style={{ padding: '4px 8px', fontSize: '11px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '3px' }}>
          Test Custom Modal
        </button>
        <button onClick={onAddView} style={{ padding: '4px 8px', fontSize: '11px', backgroundColor: '#FF5722', color: 'white', border: 'none', borderRadius: '3px' }}>
          Test Add View Modal
        </button>
        <button onClick={testQuestionDialog} style={{ padding: '4px 8px', fontSize: '11px', backgroundColor: '#2196F3', color: 'white', border: 'none', borderRadius: '3px' }}>
          Test Blueprint Question
        </button>
        <button onClick={testViewNameDialog} style={{ padding: '4px 8px', fontSize: '11px', backgroundColor: '#FF9800', color: 'white', border: 'none', borderRadius: '3px' }}>
          Test Blueprint ViewName
        </button>
        <button onClick={testColumnChooser} style={{ padding: '4px 8px', fontSize: '11px', backgroundColor: '#9C27B0', color: 'white', border: 'none', borderRadius: '3px' }}>
          Test Blueprint Column
        </button>
        <span style={{ marginLeft: '20px' }}>STATUS:</span>
        <span>Available Views: {availableViews.length}</span>
      </div>

      {/* Top Navbar */}
      <Navbar className="bp3-dark" style={{ width: '100%', zIndex: 100 }}>
        <Navbar.Group align={Alignment.LEFT}>
          <Navbar.Heading>Trading Dashboard</Navbar.Heading>
          <Navbar.Divider />
          <Button 
            minimal={true} 
            icon="add-to-artifact" 
            text="Add View..." 
            onClick={onAddView}
          />
          <Button 
            minimal={true} 
            icon="floppy-disk" 
            text="Save Layout" 
            onClick={onSaveLayout}
          />
        </Navbar.Group>
      </Navbar>
      
      {/* Main Content Area */}
      <div style={{ flex: 1, width: '100%', position: 'relative', zIndex: 1 }}>
        <Layout 
          ref={layoutRef}
          model={model} 
          factory={factory}
          onModelChange={() => setLayoutUpdate(prev => prev + 1)}
          onRenderTab={(node, renderValues) => {
            const component = node.getComponent();
            let icon;
            
            switch (component) {
              case Views.MarketData:
                icon = <Icon icon="chart" style={{ paddingRight: 5 }}></Icon>;
                break;
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
      <Navbar className="bp3-dark" style={{ width: '100%', zIndex: 100 }}>
        <Navbar.Group align={Alignment.LEFT}>
          <Navbar.Heading>'{"trader@$DESK_ID_0"}'</Navbar.Heading>
          <Navbar.Divider />
        </Navbar.Group>
        <Navbar.Group align={Alignment.RIGHT}>
          <Button 
            minimal={true} 
            icon="delete" 
            text="Cancel All Desk Orders" 
            onClick={onCancelAllOrders} 
          />
        </Navbar.Group>
      </Navbar>
      
      {/* Blueprint Dialogs - Keep for column chooser that might still use Blueprint */}
      <div style={{ 
        position: 'fixed', 
        top: 0, 
        left: 0, 
        width: '100%', 
        height: '100%', 
        pointerEvents: 'none', 
        zIndex: 5000 
      }}>
        <div style={{ pointerEvents: 'auto' }}>
          <QuestionDialog controller={questionDialogController} />
          <ViewNameDialog 
            controller={viewNameDialogController} 
            updateLayoutModel={updateLayoutModel} 
          />
          <ColumnChooserAgGrid controller={columnChooserController} />
        </div>
      </div>

      {/* Test Custom Modal */}
      <CustomModal
        isOpen={testModalOpen}
        title="🧪 Test Custom Modal"
        onClose={() => setTestModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4>Custom Modal Test</h4>
          <p>This is a test modal to verify modal functionality works properly.</p>
          <p>If you can see this modal clearly on top of everything else, then custom modals work!</p>
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => setTestModalOpen(false)}
              style={{ padding: '8px 16px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px' }}
            >
              Success - Close
            </button>
            <button 
              onClick={() => alert('Button clicked!')}
              style={{ padding: '8px 16px', backgroundColor: '#2196F3', color: 'white', border: 'none', borderRadius: '4px' }}
            >
              Test Alert
            </button>
          </div>
        </div>
      </CustomModal>

      {/* Save Layout Custom Modal */}
      <CustomModal
        isOpen={saveLayoutModalOpen}
        title="💾 Save Layout"
        onClose={() => setSaveLayoutModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Save Layout</h4>
          <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
            Do you want to save the current dashboard layout and column configurations? 
            This will preserve your current view arrangement, column visibility, and sizing.
          </p>
          <div style={{ 
            padding: '12px 16px', 
            backgroundColor: '#f8f9fa', 
            borderRadius: '6px', 
            marginBottom: '20px',
            border: '1px solid #e9ecef'
          }}>
            <div style={{ fontSize: '13px', color: '#666' }}>
              <strong>What will be saved:</strong>
            </div>
            <ul style={{ fontSize: '12px', color: '#888', marginTop: '8px', paddingLeft: '20px' }}>
              <li>Current tab layout and arrangement</li>
              <li>Column visibility and order</li>
              <li>Column widths and sizing</li>
              <li>View configurations</li>
            </ul>
          </div>
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'flex-end',
            paddingTop: '10px',
            borderTop: '1px solid #eee'
          }}>
            <button 
              onClick={() => setSaveLayoutModalOpen(false)}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#6c757d', 
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button 
              onClick={handleSaveLayoutConfirm}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#28a745', 
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              💾 Save Layout
            </button>
          </div>
        </div>
      </CustomModal>

      {/* Add View Custom Modal */}
      <CustomModal
        isOpen={addViewModalOpen}
        title="➕ Add New View"
        onClose={() => {
          setAddViewModalOpen(false);
          setSelectedViewType(null);
        }}
      >
        <div style={{ padding: '20px' }}>
          {!selectedViewType ? (
            <div>
              <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Choose View Type</h4>
              <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
                Select the type of view you want to add to your dashboard:
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {getAllViewTypes().map((viewInfo) => (
                  <div
                    key={viewInfo.type}
                    onClick={() => {
                      console.log('📋 Selected view type:', viewInfo.type);
                      setSelectedViewType(viewInfo.type);
                    }}
                    style={{
                      padding: '16px',
                      border: '2px solid #e9ecef',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      backgroundColor: '#f8f9fa'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.borderColor = '#007bff';
                      e.currentTarget.style.backgroundColor = '#e3f2fd';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.borderColor = '#e9ecef';
                      e.currentTarget.style.backgroundColor = '#f8f9fa';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                      <Icon icon={viewInfo.icon as any} style={{ marginRight: '12px', fontSize: '18px', color: '#007bff' }} />
                      <strong style={{ fontSize: '16px', color: '#333' }}>{viewInfo.name}</strong>
                    </div>
                    <div style={{ fontSize: '14px', color: '#666', paddingLeft: '30px' }}>
                      {getViewDescription(viewInfo.type)}
                    </div>
                  </div>
                ))}
              </div>
              
              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end',
                paddingTop: '20px',
                borderTop: '1px solid #eee'
              }}>
                <button 
                  onClick={() => setAddViewModalOpen(false)}
                  style={{ 
                    padding: '10px 20px', 
                    backgroundColor: '#6c757d', 
                    color: 'white', 
                    border: 'none', 
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '500',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <ViewNameStep 
              selectedViewType={selectedViewType}
              onBack={() => setSelectedViewType(null)}
              onCancel={() => {
                setAddViewModalOpen(false);
                setSelectedViewType(null);
              }}
              onConfirm={(viewName: string) => {
                console.log('📋 Creating view:', selectedViewType, viewName);
                handleAddViewConfirm(selectedViewType, viewName);
              }}
              getAllViewTypes={getAllViewTypes}
              getViewDescription={getViewDescription}
              getViewDefaultName={getViewDefaultName}
            />
          )}
        </div>
      </CustomModal>

      {/* Cancel Orders Custom Modal */}
      <CustomModal
        isOpen={cancelOrdersModalOpen}
        title="🗑️ Cancel All Orders"
        onClose={() => setCancelOrdersModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Cancel All Desk Orders</h4>
          <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
            Are you sure you want to cancel all active orders for this trading desk? This action cannot be undone.
          </p>
          <div style={{ 
            padding: '12px 16px', 
            backgroundColor: '#fff3cd', 
            borderRadius: '6px', 
            marginBottom: '20px',
            border: '1px solid #ffeaa7'
          }}>
            <div style={{ fontSize: '13px', color: '#856404' }}>
              <strong>⚠️ Warning:</strong> This will cancel all pending and partially filled orders
            </div>
          </div>
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'flex-end',
            paddingTop: '10px',
            borderTop: '1px solid #eee'
          }}>
            <button 
              onClick={() => setCancelOrdersModalOpen(false)}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#6c757d', 
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              Keep Orders
            </button>
            <button 
              onClick={handleCancelOrdersConfirm}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#dc3545', 
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              🗑️ Cancel All Orders
            </button>
          </div>
        </div>
      </CustomModal>
    </div>
  );
};

export default Container;