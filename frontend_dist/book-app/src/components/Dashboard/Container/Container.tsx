// frontend_dist/book-app/src/components/Dashboard/Container/Container.tsx (MODIFIED)
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
import BottomNavbar from './BottomNavbar';
import TopNavbar from './TopNavbar'; // Add this import
import DebugPanel from './DebugPanel'; // Add this import
import CustomModals from './CustomModals'; // Add this import
import ViewNameStep from './ViewNameStep'; // Add this import
import MainContentArea from './MainContentArea'; // Add this import
import DialogOverlay from './DialogOverlay'; // Add this import
import LoadingSpinner from './LoadingSpinner'; // Add this import
import './Container.css';

// Import the services we need
import { ClientConfigService } from '../../../services/client-config/client-config-service';
import { useBookManager } from '../../../hooks/useBookManager';
import { useTokenManager } from '../../../hooks/useTokenManager';
import { useParams } from 'react-router-dom';
import { ApiFactory } from '@trading-app/api';

const Container = () => {
  // Get bookId from route params
  const { bookId } = useParams<{ bookId: string }>();
  
  // Get dependencies for ClientConfigService
  const bookManager = useBookManager();
  const tokenManager = useTokenManager();
  
  // Create the initial model
  const [model, setModel] = useState<Model>(() => Model.fromJson(defaultLayoutJson));
  const [layoutUpdate, setLayoutUpdate] = useState(0);
  const layoutRef = useRef<Layout>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Initialize controllers and services
  const [questionDialogController] = useState(new QuestionDialogController());
  const [viewNameDialogController] = useState(new ViewNameDialogController());
  const [columnChooserController] = useState(new AgGridColumnChooserController());
  
  // Initialize configuration service with real implementation
  const [configService, setConfigService] = useState<ConfigurationService | null>(null);
  
  // Initialize layout manager after model is available
  const [layoutManager, setLayoutManager] = useState<LayoutManager | null>(null);
  const [availableViews, setAvailableViews] = useState<ViewInfo[]>([]);
  
  // Custom modal states
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [saveLayoutModalOpen, setSaveLayoutModalOpen] = useState(false);
  const [addViewModalOpen, setAddViewModalOpen] = useState(false);
  const [selectedViewType, setSelectedViewType] = useState<Views | null>(null);
  const [cancelConvictionsModalOpen, setCancelConvictionsModalOpen] = useState(false);

  // Initialize ConfigurationService with real API client
  useEffect(() => {
    const initializeConfigService = async () => {
      if (!tokenManager || !bookId) {
        console.log('📋 Container: Waiting for tokenManager and bookId...');
        return;
      }
      
      try {
        console.log('📋 Container: Initializing ConfigurationService for book:', bookId);
        
        // Create BookClient using the API factory
        const apiClients = ApiFactory.createClients(tokenManager);
        const clientConfigService = ClientConfigService.getInstance(apiClients.book, tokenManager);
        const configurationService = new ConfigurationService(clientConfigService);
        
        setConfigService(configurationService);
        console.log('✅ Container: ConfigurationService initialized successfully');
      } catch (error) {
        console.error('❌ Container: Failed to initialize configuration service:', error);
        // Set to null to indicate failure
        setConfigService(null);
      }
    };

    initializeConfigService();
  }, [tokenManager, bookId]);

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
      if (!configService || !bookId) {
        console.log('🔄 Container: ConfigService or bookId not ready, using default layout');
        setIsLoading(false);
        return;
      }
      
      console.log('🔄 Container: Loading saved layout for book:', bookId);
      setIsLoading(true);
      
      try {
        const newModel = await configService.loadSavedLayout(bookId);
        setModel(newModel);
        console.log('✅ Container: Layout loaded for book:', bookId);
      } catch (error) {
        console.error('❌ Container: Error loading layout for book:', bookId, error);
        // Keep the default model on error
      } finally {
        setIsLoading(false);
      }
    };
    
    loadSavedLayout();
  }, [configService, bookId]);
  
  // Factory function using the view factory module
  const factory = createViewFactory({ columnChooserController });
  
  // Custom modal handlers
  const handleSaveLayoutConfirm = async () => {
    console.log('💾 Container: Saving layout via custom modal');
    setSaveLayoutModalOpen(false);
    
    if (!configService || !bookId) {
      alert("Configuration service not available");
      return;
    }
    
    const success = await configService.saveLayout(bookId, model);
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

  const handleCancelConvictionsConfirm = () => {
    console.log('🗑️ Container: Cancelling all convictions via custom modal');
    setCancelConvictionsModalOpen(false);
    console.log("All convictions canceled");
    alert("All convictions canceled");
  };
  
  // Main handlers
  const onSaveLayout = () => {
    console.log('💾 Container: Save Layout button clicked - using CUSTOM MODAL');
    setSaveLayoutModalOpen(true);
  };

  const onCancelAllConvictions = () => {
    console.log('🗑️ Container: Cancel All Convictions button clicked - using CUSTOM MODAL');
    setCancelConvictionsModalOpen(true);
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
      case Views.ConvictionBlotter:
        return 'Conviction management interface for viewing and managing trades';
      default:
        return 'A new dashboard view';
    }
  };

  // Helper function to get view default name
  const getViewDefaultName = (viewType: Views) => {
    switch (viewType) {
      case Views.MarketData:
        return 'Market Data';
      case Views.ConvictionBlotter:
        return 'Conviction Blotter';
      default:
        return 'New View';
    }
  };

  // Get all possible view types (not just available ones)
  const getAllViewTypes = (): ViewInfo[] => {
    return [
      { type: Views.MarketData, name: "Market Data", icon: "chart" },
      { type: Views.ConvictionBlotter, name: "Conviction Blotter", icon: "import" }
    ];
  };

  if (isLoading) {
    return <LoadingSpinner/>;
  }

  if (!bookId) {
    return <LoadingSpinner/>;
  }

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Debug Panel - Now using extracted component */}
      <DebugPanel
        onTestCustomModal={testCustomModal}
        onAddView={onAddView}
        onTestQuestionDialog={testQuestionDialog}
        onTestViewNameDialog={testViewNameDialog}
        onTestColumnChooser={testColumnChooser}
        availableViews={availableViews.length}
        bookId={bookId}
        configServiceReady={!!configService}
      />

      {/* Top Navbar */}
      <TopNavbar
        onAddView={onAddView}
        onSaveLayout={onSaveLayout}
        configServiceReady={!!configService}
      />
      
      {/* Main Content Area */}
      <MainContentArea
        layoutRef={layoutRef}
        model={model}
        factory={factory}
        onModelChange={() => setLayoutUpdate(prev => prev + 1)}
      />
      
      {/* Bottom Navbar - Using extracted component */}
      <BottomNavbar 
        bookId={bookId}
        onCancelAllConvictions={onCancelAllConvictions}
      />
      
      {/* Blueprint Dialogs - Keep for column chooser that might still use Blueprint */}
      <DialogOverlay
        questionDialogController={questionDialogController}
        viewNameDialogController={viewNameDialogController}
        columnChooserController={columnChooserController}
        updateLayoutModel={updateLayoutModel}
      />

      {/* Test Custom Modal */}
      <CustomModals
        testModalOpen={testModalOpen}
        setTestModalOpen={setTestModalOpen}
        saveLayoutModalOpen={saveLayoutModalOpen}
        setSaveLayoutModalOpen={setSaveLayoutModalOpen}
        handleSaveLayoutConfirm={handleSaveLayoutConfirm}
        configServiceReady={!!configService}
        bookId={bookId}
        addViewModalOpen={addViewModalOpen}
        setAddViewModalOpen={setAddViewModalOpen}
        selectedViewType={selectedViewType}
        setSelectedViewType={setSelectedViewType}
        handleAddViewConfirm={handleAddViewConfirm}
        getAllViewTypes={getAllViewTypes}
        getViewDescription={getViewDescription}
        getViewDefaultName={getViewDefaultName}
        cancelConvictionsModalOpen={cancelConvictionsModalOpen}
        setCancelConvictionsModalOpen={setCancelConvictionsModalOpen}
        handleCancelConvictionsConfirm={handleCancelConvictionsConfirm}
      />
   </div>
 );
};

export default Container;