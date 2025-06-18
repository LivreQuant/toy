// src/components/Dashboard/Viewers/OrderBlotter/OrderBlotterDashboard.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../Container/Controllers';
import OrderBlotterToolbar from './OrderBlotterToolbar';
import OrderBlotterGrid from './OrderBlotterGrid';
import { ColumnStateService, ColumnStateDetails } from '../../AgGrid/columnStateService';
import { getConvictionColumnDefs, validateConvictionData } from './convictionColumnDefinitions';
import { useOrderData, OrderDataStatus } from './useOrderBlotterData';
import { useParams } from 'react-router-dom';
import { useBookManager } from '../../../../hooks/useBookManager';
import { useToast } from '../../../../hooks/useToast';
import { ConvictionModelConfig } from '@trading-app/types-core';

import FileUploadZone from '../../../Simulator/FileUploadZone';
import ConvictionFileProcessor from '../../../Simulator/ConvictionFileProcessor';
import ConvictionFormatInfo from './ConvictionFormatInfo'; // NEW COMPONENT
import { useConvictionManager } from '../../../../contexts/ConvictionContext';

interface OrderBlotterDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
  onColumnHandlerReady?: (handler: () => void) => void;
}

const OrderBlotterDashboard: React.FC<OrderBlotterDashboardProps> = ({ 
  colController, 
  viewId,
  onColumnHandlerReady
}) => {
  const [filterText, setFilterText] = useState<string>('');
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [columnDefsState, setColumnDefs] = useState<ColDef[]>([]);
  const [selectedConvictions, setSelectedConvictions] = useState<any[]>([]);
  const [convictionSchema, setConvictionSchema] = useState<ConvictionModelConfig | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const preventUpdateRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const convictionManager = useConvictionManager();
  const bookManager = useBookManager();
  const { addToast } = useToast();
  const { bookId } = useParams<{ bookId: string }>();

  const columnDefsRef = useRef(columnDefsState);
  
  const {
    orderData: convictionData,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    processFile,
    clearData,
    updateOrderData: updateConvictionData
  } = useOrderData(viewId);

  // Load book's conviction schema
  useEffect(() => {
    const loadConvictionSchema = async () => {
      if (!bookId) return;
      
      setIsLoadingSchema(true);
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book?.convictionSchema) {
          setConvictionSchema(response.book.convictionSchema);
          
          const newColumnDefs = getConvictionColumnDefs(response.book.convictionSchema);
          setColumnDefs(newColumnDefs);
          
          addToast('info', `Loaded conviction schema: ${response.book.convictionSchema.portfolioApproach}/${response.book.convictionSchema.portfolioApproach === 'target' ? response.book.convictionSchema.targetConvictionMethod : response.book.convictionSchema.incrementalConvictionMethod}`);
        } else {
          const defaultColumnDefs = getConvictionColumnDefs(null);
          setColumnDefs(defaultColumnDefs);
          addToast('warning', 'Using default conviction schema');
        }
      } catch (error: any) {
        console.error('Error loading conviction schema:', error);
        const defaultColumnDefs = getConvictionColumnDefs(null);
        setColumnDefs(defaultColumnDefs);
        addToast('error', 'Failed to load conviction schema, using defaults');
      } finally {
        setIsLoadingSchema(false);
      }
    };

    loadConvictionSchema();
  }, [bookId, bookManager, addToast]);

  useEffect(() => {
    columnDefsRef.current = columnDefsState;
  }, [columnDefsState]);

  useEffect(() => {
    if (columnDefsState.length === 0) return;
    
    const columnStateService = ColumnStateService.getInstance();
    const savedState = columnStateService.getViewColumnState(viewId);
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (savedColumnOrder.length > 0) {
      const orderedDefs: ColDef[] = [];
      
      savedColumnOrder.forEach(colId => {
        const def = columnDefsState.find(d => d.field === colId);
        if (def) {
          orderedDefs.push({
            ...def,
            hide: !savedState[colId]?.visibility,
            width: savedState[colId]?.width || def.width
          });
        }
      });
      
      columnDefsState.forEach(def => {
        if (def.field && !savedColumnOrder.includes(def.field)) {
          orderedDefs.push(def);
        }
      });
      
      setColumnDefs(orderedDefs);
    }
  }, [viewId, columnDefsState]);

  const handleFileAccepted = (file: File | null) => {
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const processor = new ConvictionFileProcessor(convictionSchema, addToast);
      
      const parsedConvictions = processor.processSubmitCsv(content);
      
      if (parsedConvictions.length > 0) {
        const validation = validateConvictionData(parsedConvictions, convictionSchema);
        
        if (!validation.isValid) {
          addToast('warning', `Missing required fields: ${validation.missingFields.join(', ')}`);
        }
        
        if (validation.unexpectedFields.length > 0) {
          addToast('info', `Unexpected fields found: ${validation.unexpectedFields.join(', ')}`);
        }
        
        const convictionData = parsedConvictions.map((conviction, index) => ({
          ...conviction,
          id: `CONV-${Date.now()}-${index}`,
          status: conviction.status || 'READY'
        }));
        
        updateConvictionData(convictionData);
        addToast('success', `Loaded ${parsedConvictions.length} convictions`);
      }
    };
    
    reader.readAsText(file);
  };

  const handleSubmitConvictions = async () => {
    const selectedErrorConvictions = selectedConvictions.filter(conviction => conviction.status === 'ERROR');
    
    if (selectedErrorConvictions.length > 0) {
      addToast('error', 'Cannot submit convictions with ERROR status');
      return;
    }
    
    const convictionsToSubmit = selectedConvictions.length > 0 ? selectedConvictions : convictionData;
    const validConvictions = convictionsToSubmit.filter(conviction => conviction.status !== 'ERROR');
    
    if (validConvictions.length === 0) {
      addToast('error', 'No valid convictions to submit');
      return;
    }
    
    try {
      setIsSubmitting(true);
      
      const response = await convictionManager.submitConvictions({
        bookId: bookId!,
        convictions: validConvictions,
        notes: `Conviction submission: ${validConvictions.length} convictions`
      });
      
      if (response.success) {
        const updatedConvictions = [...convictionData];
        const submittedConvictionIds = new Set(validConvictions.map(conviction => conviction.id));
        
        updatedConvictions.forEach(conviction => {
          if (submittedConvictionIds.has(conviction.id)) {
            conviction.status = 'SUBMITTED';
          }
        });
        
        updateConvictionData(updatedConvictions);
        addToast('success', `${validConvictions.length} convictions submitted successfully!`);
      } else {
        addToast('error', 'Conviction submission failed');
      }
      
    } catch (error) {
      console.error('Error submitting convictions:', error);
      addToast('error', `Error submitting convictions: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteSelectedConvictions = () => {
    if (selectedConvictions.length === 0) {
      addToast('error', 'No convictions selected');
      return;
    }
    
    const selectedConvictionIds = new Set(selectedConvictions.map(conviction => conviction.id));
    const remainingConvictions = convictionData.filter(conviction => !selectedConvictionIds.has(conviction.id));
    
    updateConvictionData(remainingConvictions);
    setSelectedConvictions([]);
    
    if (remainingConvictions.length === 0) {
      clearData();
    }
    
    addToast('success', `Deleted ${selectedConvictions.length} convictions`);
  };
  
  const handleSelectionChanged = () => {
    if (gridApi) {
      const selected = gridApi.getSelectedRows();
      setSelectedConvictions(selected);
    }
  };
  
  const handleReplaceFile = () => {
    clearData();
  };
  
  const handleFilterChange = (text: string) => {
    setFilterText(text);
  };
  
  const editVisibleColumns = useCallback(() => {
    try {
      const columnDefs = columnDefsRef.current;
      const visibleColumnDefs = columnDefs.filter(def => def.field !== 'id');
      
      const columnStates = visibleColumnDefs.map(def => ({
        colId: def.field || '',
        hide: def.hide === true
      }));
      
      const columnLikes = visibleColumnDefs.map(def => ({
        getColId: () => def.field || '',
        getDefinition: () => ({ headerName: def.headerName || def.field || '' })
      }));
      
      colController.open(
        "Conviction Blotter",
        columnStates,
        columnLikes as any,
        (newColumnsState) => {
          if (!newColumnsState) return;
          
          const updatedColumnDefs = columnDefs.map(colDef => {
            if (!colDef.field) return colDef;
            
            const newState = newColumnsState.find(state => state.colId === colDef.field);
            if (newState !== undefined) {
              return {
                ...colDef,
                hide: newState.hide === true
              };
            }
            return colDef;
          });
          
          setColumnDefs(updatedColumnDefs);
          
          const columnStateService = ColumnStateService.getInstance();
          const currentState = columnStateService.getViewColumnState(viewId);
          const columnState: ColumnStateDetails = {};
          
          newColumnsState.forEach((state, index) => {
            if (state.colId) {
              const currentWidth = currentState[state.colId]?.width;
              columnState[state.colId] = {
                visibility: !state.hide,
                order: index,
                ...(currentWidth !== undefined ? { width: currentWidth } : {})
              };
            }
          });
          
          columnStateService.setViewColumnState(viewId, columnState);
          
          if (gridApi) {
            gridApi.setGridOption('columnDefs', updatedColumnDefs);
          }
        }
      );
    } catch (error) {
      console.error("Error opening column chooser:", error);
    }
  }, [colController, viewId, gridApi]);

  useEffect(() => {
    if (onColumnHandlerReady) {
      onColumnHandlerReady(editVisibleColumns);
    }
  }, [onColumnHandlerReady, editVisibleColumns]);

  if (isLoadingSchema) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '200px',
        fontSize: '16px'
      }}>
        Loading conviction schema...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {!isDropzoneVisible && (
        <OrderBlotterToolbar
          title="Conviction Blotter"
          onSubmitConvictions={handleSubmitConvictions}
          onDeleteSelected={handleDeleteSelectedConvictions}
          onReplaceFile={handleReplaceFile}
          onEditColumns={editVisibleColumns}
          filterText={filterText}
          onFilterChange={handleFilterChange}
          hasConvictions={convictionData.length > 0}
          hasErrors={convictionData.some(conviction => conviction.status === 'ERROR')}
          selectedCount={selectedConvictions.length}
          selectedConvictions={selectedConvictions}
          dataCount={dataCount}
          lastUpdated={lastUpdated}
          isSubmitting={isSubmitting}
          convictionSchema={convictionSchema}
        />
      )}

      {error && (
        <div style={{ 
          padding: '8px', 
          margin: '0 10px', 
          backgroundColor: '#f8d7da', 
          color: '#721c24', 
          borderRadius: '4px' 
        }}>
          {error}
        </div>
      )}
      
      {isDropzoneVisible ? (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {/* File Upload Section */}
          <div style={{ flex: '0 0 auto', marginBottom: '20px' }}>
            <FileUploadZone
              title="Conviction File"
              acceptedTypes=".csv"
              onFileSelect={handleFileAccepted}
              file={null}
              required={true}
              description="CSV file containing your convictions"
            />
          </div>
          
          {/* Format Information Section */}
          <div style={{ flex: '1 1 auto', overflow: 'auto' }}>
            <ConvictionFormatInfo 
              convictionSchema={convictionSchema}
              isLoadingSchema={isLoadingSchema}
            />
          </div>
        </div>
      ) : (
        <OrderBlotterGrid
          columnDefs={columnDefsRef.current}
          rowData={convictionData}
          viewId={viewId}
          filterText={filterText}
          onGridReady={setGridApi}
          onColumnDefsChange={(newColDefs) => {
            if (preventUpdateRef.current) return;
            if (JSON.stringify(newColDefs) !== JSON.stringify(columnDefsRef.current)) {
              setColumnDefs(newColDefs);
            }
          }}
          onSelectionChanged={handleSelectionChanged}
        />
      )}
    </div>
  );
};

export default OrderBlotterDashboard;