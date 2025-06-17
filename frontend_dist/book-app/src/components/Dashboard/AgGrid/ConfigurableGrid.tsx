// Fixed ConfigurableGrid.tsx
import React, { useRef, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { GridApi, GridReadyEvent, ColDef } from 'ag-grid-community';
import { 
  ModuleRegistry, 
  RowSelectionModule, 
  ClientSideRowModelModule,
  QuickFilterModule,
} from 'ag-grid-community';

import { useColumnManagement } from './useColumnManagement';
import { RowSelectionConfig, createRowSelectionOptions, applyRowSelection } from './rowSelection';
import { PrioritySortConfig, applyPrioritySorting } from './customSort';
import './checkbox-style.css';

// Register modules
ModuleRegistry.registerModules([
  RowSelectionModule,
  ClientSideRowModelModule,
  QuickFilterModule
]);

interface ConfigurableGridProps {
  columnDefs: ColDef[];
  rowData: any[];
  viewId: string;
  filterText?: string;
  onGridReady?: (api: GridApi) => void;
  onColumnDefsChange?: (colDefs: ColDef[]) => void;
  theme?: any;
  components?: any;
  defaultColDef?: any;
  rowSelection?: 'single' | 'multiple';
  additionalGridProps?: any;
  // New optional props for enhanced features
  selectionConfig?: RowSelectionConfig;
  prioritySortConfig?: PrioritySortConfig;
  highlightedCells?: any[];
  enableCustomCheckboxStyle?: boolean;
  // Field names to search when using filterText
  filterFields?: string[];
  onSelectionChanged?: () => void;
}

const ConfigurableGrid: React.FC<ConfigurableGridProps> = ({
  columnDefs,
  rowData,
  viewId,
  filterText = '',
  onGridReady = () => {},
  onColumnDefsChange = () => {},
  theme,
  components = {},
  defaultColDef = {
    sortable: true,
    filter: true,
    resizable: true
  },
  rowSelection = 'single',
  additionalGridProps = {},
  // New props
  selectionConfig,
  prioritySortConfig,
  highlightedCells,
  enableCustomCheckboxStyle = false,
  filterFields = [],
  onSelectionChanged,
}) => {
  const gridApiRef = useRef<GridApi | null>(null);
  
  console.log("ConfigurableGrid render with filterText:", filterText);
  console.log("FilterFields:", filterFields);
  
  // Apply optional configurations to column defs
  let processedColumnDefs = [...columnDefs];
  
  // Apply priority sorting if configured
  if (prioritySortConfig) {
    processedColumnDefs = applyPrioritySorting(processedColumnDefs, prioritySortConfig);
  }
  
  // Apply row selection config if provided
  if (selectionConfig) {
    processedColumnDefs = applyRowSelection(processedColumnDefs, selectionConfig);
  }
  
  const {
    localColumnDefs,
    handleGridReady,
    handleColumnResized,
    handleColumnMoved,
    handleColumnVisible,
    handleDisplayedColumnsChanged
  } = useColumnManagement({
    viewId,
    columnDefs: processedColumnDefs,
    onColumnDefsChange
  });
  
  // Create selection options
  const selectionOptions = selectionConfig 
    ? createRowSelectionOptions(selectionConfig)
    : { rowSelection };

  // Add external filter functions to handle filtering without changing row data
  const isExternalFilterPresent = () => {
    return filterText !== '' && filterText.length > 0;
  };

  const doesExternalFilterPass = (node: any) => {
    if (!filterText || filterText.length === 0) {
      return true;
    }

    const { data } = node;
    if (!data) return false;
    
    const filterTextLower = filterText.toLowerCase();
    
    // Use specified filter fields if provided, otherwise try all fields
    const fieldsToSearch = filterFields.length > 0 
      ? filterFields 
      : Object.keys(data);
    
    return fieldsToSearch.some(field => {
      const value = data[field];
      return value !== undefined && 
            value !== null && 
            String(value).toLowerCase().includes(filterTextLower);
    });
  };

  const gridReadyHandler = (params: GridReadyEvent) => {
    console.log("Grid ready");
    gridApiRef.current = params.api;
    handleGridReady(params.api);
    onGridReady(params.api);
    
    console.log("Filter text at grid ready:", filterText);
    
    // Apply initial sort if priority sorting is configured
    if (prioritySortConfig) {
      try {
        params.api.applyColumnState({
          state: [
            { colId: prioritySortConfig.field, sort: prioritySortConfig.direction || 'asc' }
          ]
        });
      } catch (err) {
        console.warn("Could not apply initial sort:", err);
      }
    }

    /*
    // Add event listener for row selection
    params.api.addEventListener('selectionChanged', () => {
      console.log("[DEBUG C] AG Grid - Selection Changed Event");
      
      // Get selected rows
      const selectedRows = params.api.getSelectedRows();
      console.log("[DEBUG C] AG Grid - Selected Rows:", selectedRows);
      
      // Call the onSelectionChanged prop if provided
      if (onSelectionChanged) {
        onSelectionChanged();
      }
    });
    */
  };

  // Effect to trigger filter updates when filterText changes
  useEffect(() => {
    if (gridApiRef.current) {
      console.log("Filter text changed, triggering filter update:", filterText);
      gridApiRef.current.onFilterChanged();
    }
  }, [filterText]);

  // Add custom CSS class for checkbox styling if enabled
  const gridClass = enableCustomCheckboxStyle 
    ? "ag-theme-quartz custom-checkbox" 
    : "ag-theme-quartz";

  // Add custom styling when filter is active
  const gridContainerStyle = {
    flexGrow: 1,
    //borderColor: filterText ? '#00E5FF' : undefined,
    //borderWidth: filterText ? '2px' : undefined,
    //borderStyle: filterText ? 'solid' : undefined,
  };

  // Extract any filter-related props from additionalGridProps to avoid conflicts
  const { 
    isExternalFilterPresent: existingIsExternalFilterPresent,
    doesExternalFilterPass: existingDoesExternalFilterPass,
    ...restAdditionalProps 
  } = additionalGridProps;

  return (
    <div style={gridContainerStyle} className={gridClass}>
      <AgGridReact
        columnDefs={localColumnDefs}
        rowData={rowData}  // Using original data, not filtered
        onGridReady={gridReadyHandler}
        defaultColDef={defaultColDef}
        suppressColumnVirtualisation={true}
        suppressRowVirtualisation={true}
        suppressDragLeaveHidesColumns={true}
        maintainColumnOrder={true}
        theme={theme}
        components={components}
        onColumnMoved={handleColumnMoved}
        onColumnVisible={handleColumnVisible}
        onDisplayedColumnsChanged={handleDisplayedColumnsChanged}
        onColumnResized={handleColumnResized}
        onSelectionChanged={(params) => {
          console.log("[DEBUG C] AgGridReact - Selection Changed");
          
          // Call the onSelectionChanged prop if provided
          if (onSelectionChanged) {
            onSelectionChanged();
          }
        }}
        // Add external filter functions
        isExternalFilterPresent={isExternalFilterPresent}
        doesExternalFilterPass={doesExternalFilterPass}
        {...selectionOptions}
        {...restAdditionalProps}
      />
    </div>
  );
};

export default ConfigurableGrid;