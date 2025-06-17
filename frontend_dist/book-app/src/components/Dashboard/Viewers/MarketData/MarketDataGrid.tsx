// MarketDataGrid.tsx
import React from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import ConfigurableGrid from '../../AgGrid/ConfigurableGrid';
import { DirectionalPriceRenderer } from '../../AgGrid/Renderers';
import { darkTheme } from '../../AgGrid/gridThemes';

interface MarketDataGridProps {
  columnDefs: ColDef[];
  rowData: any[];
  viewId: string;
  filterText: string;
  onGridReady: (api: GridApi) => void;
  onColumnDefsChange: (colDefs: ColDef[]) => void;
}

const MarketDataGrid: React.FC<MarketDataGridProps> = (props) => {
  return (
    <ConfigurableGrid
      {...props}
      theme={darkTheme}
      components={{
        directionalPriceRenderer: DirectionalPriceRenderer
      }}
    />
  );
};

export default MarketDataGrid;