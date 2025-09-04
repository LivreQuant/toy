// columnStateService.ts
export interface ColumnVisibility {
  [columnId: string]: boolean;
}

export interface ColumnState {
  visibility: boolean;
  order: number;
  width?: number; // Added width parameter as optional
}

export interface ColumnStateDetails {
  [columnId: string]: ColumnState;
}

export interface ViewColumnState {
  [viewId: string]: ColumnStateDetails;
}

type ColumnStateListener = (state: ColumnStateDetails) => void;

export class ColumnStateService {
  private static instance: ColumnStateService;
  private columnStates: ViewColumnState = {};
  private listeners: Map<string, Set<ColumnStateListener>> = new Map();
  
  private constructor() {}
  
  static getInstance(): ColumnStateService {
      if (!ColumnStateService.instance) {
          ColumnStateService.instance = new ColumnStateService();
      }
      return ColumnStateService.instance;
  }
  
  // Register a view's column state with ordering
  setViewColumnState(viewId: string, columnState: ColumnStateDetails): void {
    // Don't override existing state with empty state
    if (Object.keys(columnState).length === 0 && Object.keys(this.columnStates[viewId] || {}).length > 0) {
        return;
    }
    
    this.columnStates[viewId] = { ...columnState };
    this.notifyListeners(viewId);
  }

  // Backward compatibility method - use this instead of directly calling setViewColumnState
  setViewColumnVisibility(viewId: string, columnVisibility: ColumnVisibility): void {
    // Convert from old format to new format
    const existingState = this.columnStates[viewId] || {};
    const newState: ColumnStateDetails = {};
    
    // Get all column IDs
    const allColumnIds = new Set<string>([
      ...Object.keys(existingState), 
      ...Object.keys(columnVisibility)
    ]);
    
    // Preserve order if it exists, otherwise use index for ordering
    let index = 0;
    allColumnIds.forEach(colId => {
      const isVisible = columnVisibility[colId] !== undefined ? 
        columnVisibility[colId] : 
        (existingState[colId]?.visibility ?? true);
        
      // Use existing order or assign a new one
      const order = existingState[colId]?.order ?? index;
      
      // Preserve width if it exists
      const width = existingState[colId]?.width;
      
      newState[colId] = {
        visibility: isVisible,
        order: order,
        ...(width !== undefined ? { width } : {})
      };
      
      index++;
    });
    
    this.columnStates[viewId] = newState;
    this.notifyListeners(viewId);
  }
  
  // Set column width
  setColumnWidth(viewId: string, columnId: string, width: number): void {
    const state = this.columnStates[viewId] || {};
    const columnState = state[columnId] || { visibility: true, order: Object.keys(state).length };
    
    // Update the width
    columnState.width = width;
    
    // Update the state
    const newState = { ...state, [columnId]: columnState };
    this.columnStates[viewId] = newState;
    this.notifyListeners(viewId);
  }
  
  // Get column width
  getColumnWidth(viewId: string, columnId: string): number | undefined {
    const state = this.columnStates[viewId] || {};
    return state[columnId]?.width;
  }
  
  // Backward compatibility method for getting just visibility
  getViewColumnVisibility(viewId: string): ColumnVisibility {
    const state = this.columnStates[viewId] || {};
    const visibilityMap: ColumnVisibility = {};
    
    Object.entries(state).forEach(([colId, colState]) => {
      visibilityMap[colId] = colState.visibility;
    });
    
    return visibilityMap;
  }
  
  // Update column order based on array of column IDs in desired order
  setColumnOrder(viewId: string, orderedColumnIds: string[]): void {
    const existingState = this.columnStates[viewId] || {};
    const newState: ColumnStateDetails = {};
    
    // Ensure all columns from the order are in the state
    orderedColumnIds.forEach((colId, index) => {
      newState[colId] = {
        // Preserve visibility from existing state if available
        visibility: existingState[colId]?.visibility ?? true,
        order: index,
        ...(existingState[colId]?.width !== undefined ? { width: existingState[colId].width } : {})
      };
    });
    
    // Add any columns from existing state that weren't in the new order
    Object.keys(existingState).forEach(colId => {
      if (!newState[colId]) {
        newState[colId] = existingState[colId];
      }
    });
    
    this.columnStates[viewId] = newState;
    this.notifyListeners(viewId);
  }
  
  getOrderedColumns(viewId: string): string[] {
    const state = this.columnStates[viewId] || {};
    
    const orderedColumns = Object.entries(state)
      .sort(([, a], [, b]) => a.order - b.order)
      .map(([colId]) => colId);
    
    return orderedColumns;
  }
  
  // Get a view's column state with ordering
  getViewColumnState(viewId: string): ColumnStateDetails {
      const state = this.columnStates[viewId] || {};
      return state;
  }
  
  // Get all column states
  getAllColumnStates(): ViewColumnState {
      return { ...this.columnStates };
  }
  
  // Reset all column states
  resetColumnStates(states?: ViewColumnState): void {
    // Clear existing states
    this.columnStates = {};
    
    // Apply new states if provided
    if (states) {
      this.columnStates = { ...states };
      
      // Debug log for each view's column order
      Object.keys(states).forEach(viewId => {
        const orderedColumns = Object.entries(states[viewId])
          .sort(([, a], [, b]) => a.order - b.order)
          .map(([colId]) => colId);
        
        // Notify listeners
        this.notifyListeners(viewId);
      });
    }
  }
  
  
  // Add a listener for column state changes for a specific view
  addListener(viewId: string, listener: ColumnStateListener): void {
      if (!this.listeners.has(viewId)) {
          this.listeners.set(viewId, new Set());
      }
      this.listeners.get(viewId)?.add(listener);
      
      // Immediately notify with current state
      const currentState = this.getViewColumnState(viewId);
      listener(currentState);
  }
  
  // Remove a listener
  removeListener(viewId: string, listener: ColumnStateListener): void {
      const viewListeners = this.listeners.get(viewId);
      if (viewListeners) {
          viewListeners.delete(listener);
      }
  }
  
  // Notify all listeners for a view
  private notifyListeners(viewId: string): void {
      const viewListeners = this.listeners.get(viewId);
      const state = this.getViewColumnState(viewId);
      
      if (viewListeners) {
          viewListeners.forEach(listener => {
              try {
                  listener(state);
              } catch (error) {
                  console.error(`Error in column state listener for ${viewId}:`, error);
              }
          });
      }
  }
}