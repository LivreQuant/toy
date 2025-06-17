// src/AgGrid/rowSelection.ts
import { ColDef } from 'ag-grid-community';

export interface RowSelectionConfig<T = any> {
  isSelectable?: (data: T) => boolean;
  checkboxColumn?: boolean;
  headerCheckboxSelection?: boolean;
  headerCheckboxSelectionFilteredOnly?: boolean;
  multiSelect?: boolean;
}

export const applyRowSelection = <T = any>(
  columnDefs: ColDef[],
  config: RowSelectionConfig<T>
): ColDef[] => {
  const updatedDefs = [...columnDefs];
  
  console.log("[DEBUG] Apply Row Selection Config:", config);
  console.log("[DEBUG] Initial column defs:", updatedDefs);
  
  // If checkbox column is requested
  if (config.checkboxColumn) {
    console.log("[DEBUG] Adding checkbox column");
    
    // Look for an existing checkbox column
    const checkboxColIndex = updatedDefs.findIndex(col => 
      col.checkboxSelection === true
    );
    
    if (checkboxColIndex >= 0) {
      // Update existing checkbox column
      console.log("[DEBUG] Updating existing checkbox column");
      updatedDefs[checkboxColIndex] = {
        ...updatedDefs[checkboxColIndex],
        headerCheckboxSelection: config.headerCheckboxSelection,
        headerCheckboxSelectionFilteredOnly: config.headerCheckboxSelectionFilteredOnly
      };
    } else {
      // Add a new checkbox column as the first column IMMEDIATELY
      updatedDefs.unshift({
        headerCheckboxSelection: config.headerCheckboxSelection !== false,
        headerCheckboxSelectionFilteredOnly: config.headerCheckboxSelectionFilteredOnly !== false,
        checkboxSelection: true,
        width: 42,
        pinned: 'left' as const,
        lockPinned: true,
        field: undefined, // Add a unique field to help with identification
        headerName: undefined,
        resizable: false
      });
    }
  }
  
  console.log("[DEBUG] Final updated column defs:", updatedDefs);
  
  return updatedDefs;
};

export const createRowSelectionOptions = <T = any>(config: RowSelectionConfig<T>) => {
  console.log("[DEBUG] Creating row selection options:", config);
  
  return {
    rowSelection: config.multiSelect ? 'multiple' : 'single',
    suppressRowClickSelection: config.checkboxColumn === true,
    rowMultiSelectWithClick: config.multiSelect === true,
    isRowSelectable: config.isSelectable
      ? (params: any) => {
          console.log("[DEBUG] Checking row selectability:", params.data);
          return config.isSelectable!(params.data);
        }
      : undefined
  };
};