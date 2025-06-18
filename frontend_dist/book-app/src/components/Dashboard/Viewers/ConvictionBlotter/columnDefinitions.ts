// src/components/Dashboard/Viewers/ConvictionBlotter/columnDefinitions.ts
import { ColDef } from 'ag-grid-community';
import { GlobalColours } from '../../AgGrid/Colours';
import StatusCellRenderer from './utils/StatusCellRenderer';

// Create a generic comparator function for status priority sorting
const createStatusPriorityComparator = <T extends any>(defaultComparator: (a: T, b: T) => number) => {
  return (valueA: T, valueB: T, nodeA: any, nodeB: any, isDescending: boolean) => {
    // Get the status values for both rows
    const statusA = nodeA?.data?.status;
    const statusB = nodeB?.data?.status;
    
    // Always prioritize ERROR status regardless of which column is being sorted
    if (statusA === 'ERROR' && statusB !== 'ERROR') {
      return !isDescending ? -1 : 1; // ERROR comes first
    }
    if (statusA !== 'ERROR' && statusB === 'ERROR') {
      return !isDescending ? 1 : -1; // Other statuses come after ERROR
    }
    
    // If both or neither are ERROR, use the default comparison
    return defaultComparator(valueA, valueB);
  };
};

// Create specific comparators for different data types
const textComparator = createStatusPriorityComparator<string>((a, b) => (a || '').localeCompare(b || ''));
const numberComparator = createStatusPriorityComparator<number>((a, b) => (a || 0) - (b || 0));

export const getConvictionBlotterColumnDefs = (): ColDef[] => [
  { 
    headerName: 'Status', 
    field: 'status', 
    width: 100,
    filter: true,
    comparator: textComparator,
    cellRenderer: StatusCellRenderer
  },
  { 
    headerName: 'Client Conviction ID', 
    field: 'clConvictionId', 
    width: 150,
    sortable: true,
    filter: true,
    comparator: textComparator
  },
  { 
    headerName: 'Instrument', 
    field: 'instrument', 
    width: 100,
    sortable: true,
    filter: true,
    comparator: textComparator
  },
  { 
    headerName: 'Exchange', 
    field: 'exchange', 
    width: 100,
    sortable: true,
    filter: true,
    comparator: textComparator
  },
  { 
    headerName: 'Side', 
    field: 'convictionSide', 
    width: 80,
    sortable: true,
    filter: true,
    comparator: textComparator,
    cellStyle: params => {
      if (params.value === 'BUY') {
        return { backgroundColor: GlobalColours.BUYBKG, color: '#000000' };
      } else if (params.value === 'SELL') {
        return { backgroundColor: GlobalColours.SELLBKG, color: '#000000' };
      }
      return null;
    }
  },
  { 
    headerName: 'Quantity', 
    field: 'quantity', 
    width: 100,
    filter: true,
    comparator: numberComparator,
    valueFormatter: params => {
      return params.value.toLocaleString();
    }
  },
  { 
    headerName: 'Price', 
    field: 'price', 
    width: 100,
    filter: true,
    comparator: numberComparator,
    valueFormatter: params => {
      return params.value.toFixed(2);
    }
  },
  { 
    headerName: 'Currency', 
    field: 'currency', 
    width: 100,
    filter: true,
    comparator: textComparator
  },
  { 
    headerName: 'Conviction Type', 
    field: 'ConvictionType', 
    width: 120,
    filter: true,
    comparator: textComparator
  },
  { 
    headerName: 'Fill Rate', 
    field: 'fillRate', 
    width: 100,
    filter: true,
    comparator: numberComparator,
    valueFormatter: params => {
      return params.value.toFixed(2);
    }
  }
];