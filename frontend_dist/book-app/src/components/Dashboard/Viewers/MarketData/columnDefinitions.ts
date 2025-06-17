// src/components/MarketData/columnDefinitions.ts
import { ColDef } from 'ag-grid-community';

export const getMarketDataColumnDefs = (): ColDef[] => [
  { 
    headerName: 'Instrument', 
    field: 'instrument', 
    width: 120,
    sortable: true,
    filter: true
  },
  { 
    headerName: 'Exchange', 
    field: 'exchange', 
    width: 120,
    sortable: true,
    filter: true
  },
  { 
    headerName: 'Time', 
    field: 'timestamp', 
    width: 100,
    valueFormatter: (params) => {
      return new Date(params.value).toLocaleTimeString();
    }
  },
  { 
    headerName: 'Close', 
    field: 'close', 
    width: 100,
    valueGetter: (params) => {
      return { 
        price: params.data.close.toFixed(2), 
        direction: params.data?.priceDirection 
      };
    },
    cellRenderer: 'directionalPriceRenderer'
  },
  { 
    headerName: 'Open', 
    field: 'open', 
    width: 100,
    valueFormatter: (params) => {
      return params.value.toFixed(2);
    }
  },
  { 
    headerName: 'High', 
    field: 'high', 
    width: 100,
    valueFormatter: (params) => {
      return params.value.toFixed(2);
    }
  },
  { 
    headerName: 'Low', 
    field: 'low', 
    width: 100,
    valueFormatter: (params) => {
      return params.value.toFixed(2);
    }
  },
  { 
    headerName: 'Volume', 
    field: 'volume', 
    width: 100
  },
  {
    headerName: 'Change',
    field: 'change',
    width: 100,
    valueFormatter: (params) => {
      return params.value ? params.value.toFixed(2) : '';
    },
    cellStyle: (params) => {
      return { 
        color: params.value > 0 ? '#4CAF50' : params.value < 0 ? '#F44336' : ''
      };
    }
  }
];