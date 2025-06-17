// hooks/useColumnManagement.ts
import { useEffect, useRef, useState, useMemo } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { ColumnStateService, ColumnStateDetails } from './columnStateService';

interface ColumnManagementOptions {
  viewId: string;
  columnDefs: ColDef[];
  onColumnDefsChange: (colDefs: ColDef[]) => void;
}

export const useColumnManagement = ({ viewId, columnDefs, onColumnDefsChange }: ColumnManagementOptions) => {
  const gridApiRef = useRef<GridApi | null>(null);
  const preventUpdateRef = useRef(false);
  const initialLoadCompletedRef = useRef(false);
  const updateTimeoutRef = useRef<number | null>(null);
  const columnStateService = ColumnStateService.getInstance();
  
  // Get saved column state
  const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
  const savedState = columnStateService.getViewColumnState(viewId);
  
  // Create ordered column definitions based on saved state
  // Create ordered column definitions based on saved state
  const orderedColumnDefs = useMemo(() => {
    // Create a map for faster lookup
    const colDefMap = new Map();
    columnDefs.forEach(def => {
      if (def.field) colDefMap.set(def.field, def);
    });
    
    // Create checkbox column definition if not present
    const checkboxColumnDef: ColDef = {
      headerCheckboxSelection: true,
      headerCheckboxSelectionFilteredOnly: true,
      checkboxSelection: true,
      width: 42,
      pinned: 'left' as const,
      lockPinned: true,
      field: undefined,
      headerName: undefined,
      resizable: false
    };
  
    if (savedColumnOrder.length > 0) {
      // Create new ordered array based on saved order, including checkbox column
      const orderedDefs = [
        checkboxColumnDef,
        ...savedColumnOrder
          .map(colId => {
            const colDef = colDefMap.get(colId);
            if (colDef) {
              return {
                ...colDef,
                hide: savedState[colId] ? !savedState[colId].visibility : false,
                width: savedState[colId]?.width || colDef.width
              };
            }
            return null;
          })
          .filter(Boolean)
      ];
  
      return orderedDefs;
    }
  
    // If no saved order, return checkbox column first
    return [
      checkboxColumnDef,
      ...columnDefs
    ];
  }, [columnDefs, savedColumnOrder, savedState]);
  
  // Use the ordered defs as initial state
  const [localColumnDefs, setLocalColumnDefs] = useState<ColDef[]>(orderedColumnDefs);

  // Helper to debounce grid updates
  const applyGridUpdate = (api: GridApi, columnDefs: ColDef[]) => {
    if (updateTimeoutRef.current !== null) {
      window.clearTimeout(updateTimeoutRef.current);
    }
    
    updateTimeoutRef.current = window.setTimeout(() => {
      api.setGridOption('columnDefs', columnDefs);
      updateTimeoutRef.current = null;
    }, 50);
  };

  // Create initial column state ONLY ONCE
  useEffect(() => {
    if (initialLoadCompletedRef.current) return;
    
    const currentState = columnStateService.getViewColumnState(viewId);
    
    if (Object.keys(currentState).length === 0) {
      const initialColumnState: ColumnStateDetails = {};
      
      // Initialize with column def order and width
      columnDefs.forEach((col, index) => {
        if (col.field) {
          initialColumnState[col.field] = {
            visibility: col.hide !== true,
            order: index,
            width: col.width
          };
        }
      });
      
      // Save this initial state
      columnStateService.setViewColumnState(viewId, initialColumnState);
    }
  }, [viewId, columnDefs]);

  // Listen for column definition changes from parent
  useEffect(() => {
    if (preventUpdateRef.current) {
      return;
    }
    
    if (!initialLoadCompletedRef.current || JSON.stringify(columnDefs) === JSON.stringify(localColumnDefs)) {
      return;
    }
    
    setLocalColumnDefs(columnDefs);
  }, [columnDefs, localColumnDefs]);

  // Event handlers
  const handleGridReady = (api: GridApi) => {
    gridApiRef.current = api;
    
    // Only apply saved column state on first initialization
    if (!initialLoadCompletedRef.current) {
      // Force a column refresh to ensure the grid respects our column order
      setTimeout(() => {
        try {
          const orderedColumnDefs: ColDef[] = [];
          
          // Add columns in the saved order first
          savedColumnOrder.forEach(colId => {
            const existingCol = localColumnDefs.find(col => col.field === colId);
            if (existingCol) {
              orderedColumnDefs.push({
                ...existingCol,
                hide: savedState[colId] ? !savedState[colId].visibility : false,
                width: savedState[colId]?.width || existingCol.width
              });
            }
          });
          
          // Add any columns that weren't in the saved order
          localColumnDefs.forEach(col => {
            if (col.field && !savedColumnOrder.includes(col.field)) {
              orderedColumnDefs.push({
                ...col,
                hide: col.hide === true
              });
            }
          });
          
          // Apply the final column definitions with debounce
          applyGridUpdate(api, orderedColumnDefs);
        } catch (error) {
          console.error('Error applying column state:', error);
        }
        
        initialLoadCompletedRef.current = true;
      }, 100);
    }
  };

  const handleColumnResized = (event: any) => {
    if (event.source !== 'uiColumnResized' || !event.finished) return;
    
    if (!gridApiRef.current) return;
    
    try {
      if (event.column) {
        const columnId = event.column.getColId();
        const newWidth = event.column.getActualWidth();
        
        // Get current state
        const currentState = columnStateService.getViewColumnState(viewId);
        const updatedState = { ...currentState };
        
        // Update width while preserving other properties
        if (updatedState[columnId]) {
          updatedState[columnId] = {
            ...updatedState[columnId],
            width: newWidth
          };
        } else {
          updatedState[columnId] = {
            visibility: true,
            order: Object.keys(currentState).length,
            width: newWidth
          };
        }
        
        // Save updated state
        columnStateService.setViewColumnState(viewId, updatedState);
        
        // Set flag to prevent unnecessary updates
        preventUpdateRef.current = true;
        
        // Update local column definitions
        const updatedColDefs = localColumnDefs.map(colDef => {
          if (colDef.field === columnId) {
            return {
              ...colDef,
              width: newWidth
            };
          }
          return colDef;
        });
        
        setLocalColumnDefs(updatedColDefs);
        onColumnDefsChange(updatedColDefs);
        
        // Clear flag after the update
        setTimeout(() => {
          preventUpdateRef.current = false;
        }, 0);
      }
    } catch (error) {
      console.error("Error handling column resize:", error);
    }
  };

  const handleColumnMoved = (event: any) => {
    if (event.source !== 'uiColumnMoved') return;
    
    if (!gridApiRef.current) return;
    
    try {
      const movedColumn = event.column?.getColId();
      const toIndex = event.toIndex;
      
      if (!movedColumn || toIndex === undefined) return;
      
      // Get current column state from state service
      const currentState = columnStateService.getViewColumnState(viewId);
      
      // Get current column definitions
      const currentColumns = [...localColumnDefs];
      
      // Find the moved column
      const originalIndex = currentColumns.findIndex(col => col.field === movedColumn);
      
      if (originalIndex === -1) return;
      
      // Remove column from its original position
      const [removedColumn] = currentColumns.splice(originalIndex, 1);
      
      // Insert at the new position
      currentColumns.splice(toIndex, 0, removedColumn);
      
      // Extract the column order for the state service
      const newColumnOrder = currentColumns
        .filter(def => def.field)
        .map(def => def.field as string);
      
      // Create a new state object with updated order but preserved visibility AND WIDTH
      const updatedState: ColumnStateDetails = {};
      
      // Create a new state object that maintains visibility and width from current state
      newColumnOrder.forEach((colId, index) => {
        updatedState[colId] = {
          visibility: currentState[colId]?.visibility ?? true,
          order: index,
          width: currentState[colId]?.width
        };
      });
      
      // Add any remaining columns from the current state
      Object.keys(currentState).forEach(colId => {
        if (!updatedState[colId]) {
          updatedState[colId] = currentState[colId];
        }
      });
      
      // Now save the complete state
      columnStateService.setViewColumnState(viewId, updatedState);
      
      // Set flag to prevent unnecessary updates
      preventUpdateRef.current = true;
      
      // Update local column definitions
      setLocalColumnDefs(currentColumns);
      onColumnDefsChange(currentColumns);
      
      // Clear flag after the update
      setTimeout(() => {
        preventUpdateRef.current = false;
      }, 0);
      
      // Apply just the column order without changing visibility or width
      if (event.finished && gridApiRef.current) {
        try {
          // Create ordered column defs with correct properties
          const orderedColumnDefs = newColumnOrder.map(colId => {
            const colDef = currentColumns.find(col => col.field === colId);
            if (colDef) {
              return {
                ...colDef,
                hide: !updatedState[colId]?.visibility,
                width: updatedState[colId]?.width || colDef.width
              };
            }
            return null;
          }).filter(Boolean) as ColDef[];
          
          // Apply the column definitions with debounce
          applyGridUpdate(gridApiRef.current, orderedColumnDefs);
        } catch (e) {
          console.error("Error applying column order:", e);
        }
      }
    } catch (error) {
      console.error('Error handling column move:', error);
    }
  };

  const handleColumnVisible = (event: any) => {
    if (!gridApiRef.current) return;
    
    try {
      if (event.visible !== undefined && event.column) {
        const columnId = event.column.getColId();
        const isVisible = event.visible;
        
        // Get current state
        const currentState = columnStateService.getViewColumnState(viewId);
        const updatedState = { ...currentState };
        
        // Update visibility while preserving order and width
        if (updatedState[columnId]) {
          updatedState[columnId] = {
            ...updatedState[columnId],
            visibility: isVisible
          };
        } else {
          updatedState[columnId] = {
            visibility: isVisible,
            order: Object.keys(currentState).length
          };
        }
        
        // Save updated state
        columnStateService.setViewColumnState(viewId, updatedState);
        
        // Set flag to prevent unnecessary updates
        preventUpdateRef.current = true;
        
        // Update local column definitions
        const updatedColDefs = localColumnDefs.map(colDef => {
          if (colDef.field === columnId) {
            return {
              ...colDef,
              hide: !isVisible
            };
          }
          return colDef;
        });
        
        setLocalColumnDefs(updatedColDefs);
        onColumnDefsChange(updatedColDefs);
        
        // Clear flag after the update
        setTimeout(() => {
          preventUpdateRef.current = false;
        }, 0);
      }
    } catch (error) {
      console.error("Error handling column visibility change:", error);
    }
  };

  const handleDisplayedColumnsChanged = (event: any) => {
    // If this is from a grid options change, restore our column visibility
    if (event.source === 'gridOptionsChanged' && gridApiRef.current) {
      // Get current state from the service
      const currentState = columnStateService.getViewColumnState(viewId);
      
      // Use setTimeout to ensure this runs after AG Grid has finished its updates
      setTimeout(() => {
        try {
          // Create updated column defs with proper visibility AND WIDTH
          const updatedDefs = [...localColumnDefs];
          
          // Update visibility based on current state
          Object.entries(currentState).forEach(([colId, state]) => {
            const colIndex = updatedDefs.findIndex(def => def.field === colId);
            if (colIndex >= 0) {
              updatedDefs[colIndex] = {
                ...updatedDefs[colIndex],
                hide: !state.visibility,
                width: state.width || updatedDefs[colIndex].width
              };
            }
          });
          
          // Apply the updated column definitions with debounce
          if (gridApiRef.current) {
            applyGridUpdate(gridApiRef.current, updatedDefs);
          }
        } catch (e) {
          console.error("Error preserving column visibility:", e);
        }
      }, 0);
    }
  };

  // Listen for external column state changes
  useEffect(() => {
    const handleColumnStateChange = (state: ColumnStateDetails) => {
      // Skip updates we triggered ourselves
      if (preventUpdateRef.current) {
        return;
      }
    };
    
    columnStateService.addListener(viewId, handleColumnStateChange);
    
    return () => {
      columnStateService.removeListener(viewId, handleColumnStateChange);
    };
  }, [viewId]);

  return {
    localColumnDefs,
    handleGridReady,
    handleColumnResized,
    handleColumnMoved,
    handleColumnVisible,
    handleDisplayedColumnsChanged,
    applyGridUpdate
  };
};