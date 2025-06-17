// src/components/MarketData/MarketDataDashboard.tsx
import React, { useState, useRef, useEffect } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../Container/Controllers';
import { useMarketData } from './useMarketData';
import { getMarketDataColumnDefs } from './columnDefinitions';
import MarketDataToolbar from './MarketDataToolbar';
import MarketDataGrid from './MarketDataGrid';
import { ColumnStateService, ColumnStateDetails } from '../../AgGrid/columnStateService';
import { StreamStatus } from '../../../../services/stream/services/exchangeDataStream';
import { MarketDataStatus } from './useMarketData';

interface MarketDataDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
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


const MarketDataDashboard: React.FC<MarketDataDashboardProps> = ({ colController, viewId }) => {
  const [filterText, setFilterText] = useState<string>('');
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [columnDefsState, setColumnDefs] = useState<ColDef[]>(getMarketDataColumnDefs());
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

  const editVisibleColumns = () => {
    try {
      // Skip grid API calls entirely and just use our column definitions
      const columnDefs = columnDefsRef.current;
      
      // Create column states directly from column definitions
      const columnStates = columnDefs.map(def => ({
        colId: def.field || '',
        hide: def.hide === true
      }));
      
      // Create columns-like objects for header mapping
      const columnLikes = columnDefs.map(def => ({
        getColId: () => def.field || '',
        getDefinition: () => ({ headerName: def.headerName || def.field || '' })
      }));
      
      colController.open(
        "Live Market Data",
        columnStates,
        columnLikes as any,
        (newColumnsState) => {
          if (!newColumnsState) {
            return;
          }
          
          try {
            // Check if anything has actually changed
            const hasChanges = newColumnsState.some(state => {
              const columnDef = columnDefsRef.current.find(def => def.field === state.colId);
              return columnDef && (columnDef.hide !== state.hide);
            });
            
            if (!hasChanges) {
              return;
            }
            
            console.log("[DEBUG A] Column visibility changed via column chooser");
            
            // Create new column definitions with updated visibility
            const updatedColumnDefs = columnDefs.map(colDef => {
              if (!colDef.field) return colDef;
              
              const newState = newColumnsState.find(state => state.colId === colDef.field);
              if (newState !== undefined) {
                return {
                  ...colDef,
                  hide: newState.hide === true  // Make sure this matches AG Grid's 'hide' property
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
            newColumnsState.forEach((state, index) => {
              if (state.colId) {
                // Preserve width from current state if available
                const currentWidth = currentState[state.colId]?.width;
                
                columnState[state.colId] = {
                  visibility: !state.hide,  // Note the NOT operator here
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
        }
      );
    } catch (error) {
      console.error("Error opening column chooser:", error);
    }
  };

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
    </div>
  );
};

export default MarketDataDashboard;