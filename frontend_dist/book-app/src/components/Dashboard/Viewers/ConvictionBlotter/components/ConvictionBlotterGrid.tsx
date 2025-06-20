// src/components/Dashboard/Viewers/ConvictionBlotter/ConvictionBlotterGrid.tsx
import React, { useState, useEffect } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import ConfigurableGrid from '../../../AgGrid/core/ConfigurableGrid';
import { darkTheme } from '../../../AgGrid/themes/gridThemes';
import StatusCellRenderer from '../utils/StatusCellRenderer';

interface ConvictionBlotterGridProps {
  columnDefs: ColDef[];
  rowData: any[];
  viewId: string;
  filterText: string;
  onGridReady: (api: GridApi) => void;
  onColumnDefsChange: (colDefs: ColDef[]) => void;
  onSelectionChanged: () => void;
}

interface ConvictionData {
  status?: string;
  [key: string]: any;
}

const ConvictionBlotterGrid: React.FC<ConvictionBlotterGridProps> = (props) => {
  const components = {
    statusCellRenderer: StatusCellRenderer
  };
  
  const [isErrorsPresent, setIsErrorsPresent] = useState(
    props.rowData.some((row: ConvictionData) => row.status === 'ERROR')
  );

  // Track ERROR status changes
  useEffect(() => {
    const hasErrorConvictions = props.rowData.some((row: ConvictionData) => row.status === 'ERROR');
    setIsErrorsPresent(hasErrorConvictions);
  }, [props.rowData]);

  const selectionConfig = {
    checkboxColumn: true,
    headerCheckboxSelection: true,
    headerCheckboxSelectionFilteredOnly: true,
    multiSelect: true,
    isSelectable: (data: ConvictionData) => {
      // If errors are present, only allow selecting ERROR rows
      if (isErrorsPresent) {
        return data.status === 'ERROR';
      }
      // Once no ERROR rows remain, allow selecting all rows
      return true;
    }
  };

  // Filter fields for conviction data
  const fieldsToFilter = ['instrumentId', 'convictionId', 'side', 'tag', 'status'];

  return (
    <ConfigurableGrid
      {...props}
      theme={darkTheme}
      components={components}
      filterFields={fieldsToFilter}
      selectionConfig={selectionConfig}
      rowSelection="multiple"
      onSelectionChanged={() => {
        console.log("[DEBUG C] ConfigurableGrid - Conviction Selection Changed");
        props.onSelectionChanged();
      }}
    />
  );
};

export default ConvictionBlotterGrid;