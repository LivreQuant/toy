// frontend_dist/book-app/src/components/Dashboard/Container/hooks/useContainerLogic.ts
import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Layout, Model } from 'flexlayout-react';
import { defaultLayoutJson } from '../defaultLayout';
import { ConfigurationService } from '../ConfigurationService';
import { SimpleLayoutManager } from '../SimpleLayoutManager'; // Use SimpleLayoutManager instead
import { Views, ViewInfo } from '../layoutTypes';
import { 
  QuestionDialogController, 
  ViewNameDialogController, 
  AgGridColumnChooserController 
} from '../Controllers';
import { ClientConfigService } from '../../../../services/client-config/client-config-service';
import { useBookManager } from '../../../../hooks/useBookManager';
import { useTokenManager } from '../../../../hooks/useTokenManager';
import { ApiFactory } from '@trading-app/api';

export const useContainerLogic = () => {
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
  const [layoutManager, setLayoutManager] = useState<SimpleLayoutManager | null>(null);
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
        setConfigService(null);
      }
    };

    initializeConfigService();
  }, [tokenManager, bookId]);

  // Initialize LayoutManager after configService is available
  useEffect(() => {
    if (!configService || !bookId) return;
    
    const initializeLayoutManager = async () => {
      try {
        console.log('📋 Container: Initializing SimpleLayoutManager...');
        
        // Use SimpleLayoutManager with correct constructor
        const manager = new SimpleLayoutManager(model);
        
        setLayoutManager(manager);
        setAvailableViews(manager.getAllViewTypes());
        setIsLoading(false);
        
        console.log('✅ Container: SimpleLayoutManager initialized successfully');
      } catch (error) {
        console.error('❌ Container: Failed to initialize SimpleLayoutManager:', error);
        setIsLoading(false);
      }
    };

    initializeLayoutManager();
  }, [configService, bookId, model]);

  // Load saved layout on mount
  useEffect(() => {
    if (!layoutManager || !configService) return;
    
    const loadSavedLayout = async () => {
      try {
        const savedModel = await layoutManager.loadLayout();
        if (savedModel) {
          setModel(savedModel);
          console.log('✅ Container: Loaded saved layout');
        }
      } catch (error) {
        console.error('❌ Container: Failed to load saved layout:', error);
      }
    };

    loadSavedLayout();
  }, [layoutManager, configService]);

  // Event handlers
  const handleSaveLayout = async () => {
    if (!layoutManager || !configService) return;
    
    try {
      await layoutManager.saveLayout();
      setSaveLayoutModalOpen(false);
      console.log('✅ Container: Layout saved successfully');
    } catch (error) {
      console.error('❌ Container: Failed to save layout:', error);
    }
  };

  const handleAddView = (viewType: Views, viewName: string) => {
    if (!layoutManager) return;
    
    try {
      const newModel = layoutManager.addView(viewType, viewName);
      setModel(newModel);
      setAddViewModalOpen(false);
      setSelectedViewType(null);
      console.log('✅ Container: Added view successfully:', viewType, viewName);
    } catch (error) {
      console.error('❌ Container: Failed to add view:', error);
    }
  };

  const handleCancelAllConvictions = () => {
    console.log('🗑️ Container: Cancelling all convictions for book:', bookId);
    setCancelConvictionsModalOpen(false);
    // TODO: Implement actual cancellation logic
  };

  const updateLayoutModel = (newModel: Model) => {
    setModel(newModel);
    setLayoutUpdate(prev => prev + 1);
  };

  return {
    // Core state
    bookId: bookId || 'unknown',
    model,
    layoutUpdate,
    layoutRef,
    isLoading,
    
    // Services
    configService,
    layoutManager,
    availableViews,
    
    // Controllers
    questionDialogController,
    viewNameDialogController,
    columnChooserController,
    
    // Modal states
    testModalOpen,
    setTestModalOpen,
    saveLayoutModalOpen,
    setSaveLayoutModalOpen,
    addViewModalOpen,
    setAddViewModalOpen,
    selectedViewType,
    setSelectedViewType,
    cancelConvictionsModalOpen,
    setCancelConvictionsModalOpen,
    
    // Event handlers
    handleSaveLayout,
    handleAddView,
    handleCancelAllConvictions,
    updateLayoutModel,
    setLayoutUpdate
  };
};