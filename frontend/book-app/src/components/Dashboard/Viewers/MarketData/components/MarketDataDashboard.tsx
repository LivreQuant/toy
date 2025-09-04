// src/components/Dashboard/Viewers/MarketData/MarketDataDashboard.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../../Container/controllers/Controllers';
import { useMarketData } from '../hooks/useMarketData';
import { getMarketDataColumnDefs } from '../config/columnDefinitions';
import MarketDataToolbar from './MarketDataToolbar';
import MarketDataGrid from './MarketDataGrid';
import ColumnChooserModal from '../../../Container/modals/ColumnChooserModal';
import { ColumnStateService, ColumnStateDetails } from '../../../AgGrid/services/columnStateService';
import { MarketDataStatus } from '../hooks/useMarketData';

interface MarketDataDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
  onColumnHandlerReady?: (handler: () => void) => void;
}

// Define StreamStatus locally since we removed the import
enum StreamStatus {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  DISCONNECTED = 'DISCONNECTED',
  FAILED = 'FAILED'
}

const getStreamStatus = (marketDataStatus: MarketDataStatus): StreamStatus => {
  switch (marketDataStatus) {
    case MarketDataStatus.LOADING:
      return StreamStatus.CONNECTING;
    case MarketDataStatus.READY:
      return StreamStatus.CONNECTED;
    case MarketDataStatus.ERROR:
      return StreamStatus.FAILED;
    case MarketDataStatus.NO_DATA:
    default:
      return StreamStatus.DISCONNECTED;
  }
};

const MarketDataDashboard: React.FC<MarketDataDashboardProps> = ({ 
  colController, 
  viewId,
  onColumnHandlerReady
}) => {
  const [filterText, setFilterText] = useState<string>('');
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [columnDefsState, setColumnDefs] = useState<ColDef[]>(getMarketDataColumnDefs());
  const [columnChooserOpen, setColumnChooserOpen] = useState(false);
  const preventUpdateRef = useRef(false);
  
  // Use a ref to store column definitions to prevent regeneration on data changes
  const columnDefsRef = useRef(columnDefsState);
  
  const {
    marketData,
    status,
    error,
    dataCount,
    lastUpdated,
    clearData,
  } = useMarketData(viewId);

  // Only update the ref if column definitions have explicitly changed
  useEffect(() => {
    columnDefsRef.current = columnDefsState;
  }, [columnDefsState]);

  // Add this effect at the beginning of the MarketDataDashboard component
  // Modified useEffect to include width handling
  useEffect(() => {
    // Get the saved column order
    const columnStateService = ColumnStateService.getInstance();
    const savedState = columnStateService.getViewColumnState(viewId);
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (savedColumnOrder.length > 0) {
      // Get the default column definitions
      const defaultDefs = getMarketDataColumnDefs();
      
      // Create a new ordered array based on the saved order
      const orderedDefs: ColDef[] = [];
      
      // First add columns in the saved order
      savedColumnOrder.forEach(colId => {
        const def = defaultDefs.find(d => d.field === colId);
        if (def) {
          // Apply saved visibility and width
          orderedDefs.push({
            ...def,
            hide: !savedState[colId]?.visibility,
            // Use saved width if available, otherwise use the default width from column definition
            width: savedState[colId]?.width || def.width
          });
        }
      });
      
      // Then add any remaining columns not in the saved order
      defaultDefs.forEach(def => {
        if (def.field && !savedColumnOrder.includes(def.field)) {
          orderedDefs.push(def);
        }
      });
      
      console.log("[DEBUG A] Setting initial ordered column definitions");
      
      // Update the column definitions state
      setColumnDefs(orderedDefs);
    }
  }, [viewId]); // This effect should run once when component mounts

  // Custom column chooser function that opens the modal
  const editVisibleColumns = useCallback(() => {
    setColumnChooserOpen(true);
  }, []);

  // Handler for the custom column chooser modal
  const handleColumnChooserApply = useCallback((newColumns: any[]) => {
    try {
      // Check if anything has actually changed
      const hasChanges = newColumns.some(state => {
        const columnDef = columnDefsRef.current.find(def => def.field === state.colId);
        return columnDef && (columnDef.hide !== state.hide);
      });

      if (!hasChanges) {
        return;
      }

      console.log("[DEBUG A] Column visibility changed via modal");
      
      // Create new column definitions with updated visibility
      const updatedColumnDefs = columnDefsRef.current.map(colDef => {
        if (!colDef.field) return colDef;
        
        const newState = newColumns.find(state => state.colId === colDef.field);
        if (newState !== undefined) {
          return {
            ...colDef,
            hide: newState.hide === true
          };
        }
        return colDef;
      });
      
      // Update the state with new column definitions
      preventUpdateRef.current = true;
      setColumnDefs(updatedColumnDefs);
      
      // Get current column state to preserve widths
      const columnStateService = ColumnStateService.getInstance();
      const currentState = columnStateService.getViewColumnState(viewId);
      const columnState: ColumnStateDetails = {};
      
      // Convert from column state to our detailed state format
      newColumns.forEach((state, index) => {
        if (state.colId) {
          // Preserve width from current state if available
          const currentWidth = currentState[state.colId]?.width;
          
          columnState[state.colId] = {
            visibility: !state.hide,
            order: index,
            ...(currentWidth !== undefined ? { width: currentWidth } : {})
          };
        }
      });
      
      columnStateService.setViewColumnState(viewId, columnState);
      
      // Force refresh the grid
      if (gridApi) {
        console.log("[DEBUG A] Updating grid with new column definitions");
        gridApi.setGridOption('columnDefs', updatedColumnDefs);
      }
      
      setTimeout(() => {
        preventUpdateRef.current = false;
      }, 0);
    } catch (error) {
      console.error("Error applying column state:", error);
    }
  }, [viewId, gridApi]);

  // Prepare data for the modal
  const getModalData = useCallback(() => {
    const columnDefs = columnDefsRef.current;
    
    // Create column states directly from column definitions
    const columnStates = columnDefs
      .filter(def => def.field) // Only include columns with fields
      .map(def => ({
        colId: def.field || '',
        hide: def.hide === true
      }));
    
    // Create header mapping
    const columnHeaders = columnDefs.reduce((acc, def) => {
      if (def.field) {
        acc[def.field] = def.headerName || def.field || '';
      }
      return acc;
    }, {} as { [key: string]: string });
    
    return { columnStates, columnHeaders };
  }, []);

  // Register the column handler with the container
  useEffect(() => {
    if (onColumnHandlerReady) {
      console.log('📋 MarketData: Registering column handler');
      onColumnHandlerReady(editVisibleColumns);
    }
  }, [onColumnHandlerReady, editVisibleColumns]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <MarketDataToolbar
        status={getStreamStatus(status)}
        dataCount={dataCount}
        lastUpdated={lastUpdated}
        filterText={filterText}
        onFilterChange={setFilterText}
        onClearData={clearData}
        onEditColumns={editVisibleColumns}
      />

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

      <MarketDataGrid
        columnDefs={columnDefsRef.current}
        rowData={marketData}
        viewId={viewId}
        filterText={filterText}
        onGridReady={setGridApi}
        onColumnDefsChange={(newColDefs) => {
          if (preventUpdateRef.current) return;
          
          console.log("[DEBUG A] Column definitions changed from grid");
          
          // Compare with current state to avoid unnecessary updates
          if (JSON.stringify(newColDefs) !== JSON.stringify(columnDefsRef.current)) {
            setColumnDefs(newColDefs);
          }
        }}
      />

      {/* Column Chooser Modal */}
      <ColumnChooserModal
        isOpen={columnChooserOpen}
        title="Market Data"
        columns={getModalData().columnStates}
        columnHeaders={getModalData().columnHeaders}
        onClose={() => setColumnChooserOpen(false)}
        onApply={handleColumnChooserApply}
      />
    </div>
  );
};

export default MarketDataDashboard;