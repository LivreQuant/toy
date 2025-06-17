// Modified OrderBlotterGrid.tsx
import React, { useState, useEffect } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import ConfigurableGrid from '../../AgGrid/ConfigurableGrid';
import { darkTheme } from '../../AgGrid/gridThemes';

import StatusCellRenderer from './utils/StatusCellRenderer';

interface OrderBlotterGridProps {
  columnDefs: ColDef[];
  rowData: any[];
  viewId: string;
  filterText: string;
  onGridReady: (api: GridApi) => void;
  onColumnDefsChange: (colDefs: ColDef[]) => void;
  onSelectionChanged: () => void;
}

interface OrderData {
  status?: string;
  // Add other properties as needed
}

const OrderBlotterGrid: React.FC<OrderBlotterGridProps> = (props) => {
  const components = {
    statusCellRenderer: StatusCellRenderer
  };
  
  const [isErrorsPresent, setIsErrorsPresent] = useState(
    props.rowData.some((row: OrderData) => row.status === 'ERROR')
  );

  // Use effect to track ERROR status changes
  useEffect(() => {
    const hasErrorOrders = props.rowData.some((row: OrderData) => row.status === 'ERROR');
    setIsErrorsPresent(hasErrorOrders);
  }, [props.rowData]);

  const selectionConfig = {
    checkboxColumn: true,
    headerCheckboxSelection: true,
    headerCheckboxSelectionFilteredOnly: true,
    multiSelect: true,
    isSelectable: (data: OrderData) => {
      // If errors are present, only allow selecting ERROR rows
      if (isErrorsPresent) {
        return data.status === 'ERROR';
      }
      // Once no ERROR rows remain, allow selecting all rows
      return true;
    }
  };

  console.log("[DEBUG C] OrderBlotterGrid - Received onSelectionChanged:", props.onSelectionChanged);
  console.log("OrderBlotterGrid received filterText:", props.filterText);
  
  const fieldsToFilter = ['instrument', 'id', 'orderType'];
  console.log("Fields to filter:", fieldsToFilter);

  return (
    <ConfigurableGrid
      {...props}
      theme={darkTheme}
      components={components}
      filterFields={fieldsToFilter}
      // Explicitly add selection configuration
      selectionConfig={selectionConfig}
      rowSelection="multiple"
      onSelectionChanged={() => {
        console.log("[DEBUG C] ConfigurableGrid - Selection Changed");
        props.onSelectionChanged();
      }}
    />
  );
};

export default OrderBlotterGrid;