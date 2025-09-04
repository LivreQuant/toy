// src/components/Dashboard/Viewers/ConvictionBlotter/ConvictionBlotterDashboard.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../../Container/controllers/Controllers';
import ConvictionBlotterToolbar from './ConvictionBlotterToolbar';
import ConvictionBlotterGrid from './ConvictionBlotterGrid';
import { ColumnStateService, ColumnStateDetails } from '../../../AgGrid/services/columnStateService';
import { getConvictionColumnDefs, validateConvictionData } from '../configs/convictionColumnDefinitions';
import { useConvictionData, ConvictionDataStatus } from '../hooks/useConvictionBlotterData';
import { useParams } from 'react-router-dom';
import { useBookManager } from '../../../../../hooks/useBookManager';
import { useToast } from '../../../../../hooks/useToast';
import { ConvictionModelConfig } from '@trading-app/types-core';

import FileUploadZone from '../../../../Simulator/FileUploadZone';
import ConvictionFileProcessor from '../../../../Simulator/ConvictionFileProcessor';
import ConvictionFormatInfo from './ConvictionFormatInfo';
import { useConvictionManager } from '../../../../../contexts/ConvictionContext';

interface ConvictionBlotterDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
  onColumnHandlerReady?: (handler: () => void) => void;
}

const ConvictionBlotterDashboard: React.FC<ConvictionBlotterDashboardProps> = ({ 
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
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const convictionManager = useConvictionManager();
  const bookManager = useBookManager();
  const { addToast } = useToast();
  const { bookId } = useParams<{ bookId: string }>();

  const columnDefsRef = useRef(columnDefsState);
  const preventUpdateRef = useRef(false);
  const hasAppliedColumnOrder = useRef(false); // ← ADD THIS TO PREVENT INFINITE LOOP
  
  const {
    convictionData,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    processFile,
    clearData,
    updateConvictionData
  } = useConvictionData(viewId);

  // Debug logging for component state
  console.log('[ConvictionBlotter] Component state:', {
    bookId,
    convictionDataLength: convictionData.length,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    convictionSchema: convictionSchema ? 'loaded' : 'not loaded',
    isLoadingSchema,
    columnDefsStateLength: columnDefsState.length
  });

  // Load book's conviction schema
  useEffect(() => {
    const loadConvictionSchema = async () => {
      if (!bookId) {
        console.log('[ConvictionBlotter] No bookId, skipping schema load');
        return;
      }
      
      console.log('[ConvictionBlotter] Loading conviction schema for book:', bookId);
      setIsLoadingSchema(true);
      
      try {
        const response = await bookManager.fetchBook(bookId);
        console.log('[ConvictionBlotter] Book fetch response:', {
          success: response.success,
          hasBook: !!response.book,
          hasConvictionSchema: !!response.book?.convictionSchema
        });
        
        if (response.success && response.book?.convictionSchema) {
          setConvictionSchema(response.book.convictionSchema);
          
          const newColumnDefs = getConvictionColumnDefs(response.book.convictionSchema);
          console.log('[ConvictionBlotter] Generated column defs:', {
            count: newColumnDefs.length,
            fields: newColumnDefs.map(def => def.field).filter(Boolean)
          });
          setColumnDefs(newColumnDefs);
          
          addToast('info', `Loaded conviction schema: ${response.book.convictionSchema.portfolioApproach}/${response.book.convictionSchema.portfolioApproach === 'target' ? response.book.convictionSchema.targetConvictionMethod : response.book.convictionSchema.incrementalConvictionMethod}`);
        } else {
          console.log('[ConvictionBlotter] Using default conviction schema');
          const defaultColumnDefs = getConvictionColumnDefs(null);
          setColumnDefs(defaultColumnDefs);
          addToast('warning', 'Using default conviction schema');
        }
      } catch (error: any) {
        console.error('[ConvictionBlotter] Error loading conviction schema:', error);
        const defaultColumnDefs = getConvictionColumnDefs(null);
        setColumnDefs(defaultColumnDefs);
        addToast('error', 'Failed to load conviction schema, using defaults');
      } finally {
        setIsLoadingSchema(false);
        console.log('[ConvictionBlotter] Schema loading completed');
      }
    };

    loadConvictionSchema();
  }, [bookId, bookManager, addToast]);

  useEffect(() => {
    columnDefsRef.current = columnDefsState;
  }, [columnDefsState]);

  // FIX: Only apply column order ONCE when columns are first loaded
  useEffect(() => {
    if (columnDefsState.length === 0 || hasAppliedColumnOrder.current) return;
    
    console.log('[ConvictionBlotter] Applying saved column order (one-time)');
    
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
      
      hasAppliedColumnOrder.current = true; // ← MARK AS APPLIED
      setColumnDefs(orderedDefs);
    } else {
      hasAppliedColumnOrder.current = true; // ← MARK AS APPLIED EVEN IF NO SAVED ORDER
    }
  }, [viewId, columnDefsState.length]); // ← CHANGED: Only depend on length, not the array itself

  const handleFileAccepted = (file: File | null) => {
    console.log('[ConvictionBlotter] handleFileAccepted called with:', file);
    
    if (!file) {
      console.log('[ConvictionBlotter] No file provided');
      return;
    }
    
    console.log('[ConvictionBlotter] Processing file:', {
      name: file.name,
      size: file.size,
      type: file.type,
      convictionSchemaAvailable: !!convictionSchema
    });
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      console.log('[ConvictionBlotter] File content loaded:', {
        contentLength: content.length,
        firstLine: content.split('\n')[0],
        lineCount: content.split('\n').length,
        convictionSchema: convictionSchema ? 'available' : 'not available'
      });
      
      const processor = new ConvictionFileProcessor(convictionSchema, addToast);
      
      const parsedConvictions = processor.processSubmitCsv(content);
      console.log('[ConvictionBlotter] Parsed convictions:', {
        count: parsedConvictions.length,
        sample: parsedConvictions.slice(0, 2),
        allFields: parsedConvictions.length > 0 ? Object.keys(parsedConvictions[0]) : []
      });
      
      if (parsedConvictions.length > 0) {
        const validation = validateConvictionData(parsedConvictions, convictionSchema);
        console.log('[ConvictionBlotter] Validation result:', validation);
        
        if (!validation.isValid) {
          addToast('warning', `Missing required fields: ${validation.missingFields.join(', ')}`);
        }
        
        if (validation.unexpectedFields.length > 0) {
          addToast('info', `Unexpected fields found: ${validation.unexpectedFields.join(', ')}`);
        }
        
        const convictionDataWithIds = parsedConvictions.map((conviction, index) => ({
          ...conviction,
          id: `CONV-${Date.now()}-${index}`,
          status: conviction.status || 'READY'
        }));
        
        console.log('[ConvictionBlotter] Final conviction data being set:', {
          count: convictionDataWithIds.length,
          sample: convictionDataWithIds.slice(0, 2),
          isDropzoneVisibleBefore: isDropzoneVisible,
          statusBefore: status
        });
        
        updateConvictionData(convictionDataWithIds);
        addToast('success', `Loaded ${parsedConvictions.length} convictions`);
        
        // Check state after update
        setTimeout(() => {
          console.log('[ConvictionBlotter] State after update (delayed check):', {
            convictionDataLength: convictionData.length,
            isDropzoneVisible,
            status,
            dataCount
          });
        }, 100);
      } else {
        console.log('[ConvictionBlotter] No convictions parsed from file');
        addToast('warning', 'No valid convictions found in the CSV file');
      }
    };
    
    reader.onerror = (error) => {
      console.error('[ConvictionBlotter] File reader error:', error);
      addToast('error', 'Failed to read the file');
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
    console.log('[ConvictionBlotter] Selection changed, gridApi available:', !!gridApi);
    if (gridApi) {
      const selected = gridApi.getSelectedRows();
      console.log('[ConvictionBlotter] Selected rows:', selected.length);
      setSelectedConvictions(selected);
    }
  };
  
  const handleReplaceFile = () => {
    console.log('[ConvictionBlotter] Replace file clicked');
    clearData();
  };
  
  const handleFilterChange = (text: string) => {
    console.log('[ConvictionBlotter] Filter changed to:', text);
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

  // Debug the render decision
  console.log('[ConvictionBlotter] Render decision:', {
    isLoadingSchema,
    isDropzoneVisible,
    convictionDataLength: convictionData.length,
    error,
    status,
    columnDefsLength: columnDefsState.length
  });

  if (isLoadingSchema) {
    console.log('[ConvictionBlotter] Rendering loading state');
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
        <ConvictionBlotterToolbar
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
          
          <div style={{ flex: '1 1 auto', overflow: 'auto' }}>
            <ConvictionFormatInfo 
              convictionSchema={convictionSchema}
              isLoadingSchema={isLoadingSchema}
            />
          </div>
        </div>
      ) : (
        <ConvictionBlotterGrid
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

export default ConvictionBlotterDashboard;