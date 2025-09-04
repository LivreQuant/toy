// src/components/Dashboard/AgGrid/customSort.ts
import { ColDef } from 'ag-grid-community';

export interface PrioritySortConfig {
  field: string;
  priorityValues: any[];
  direction?: 'asc' | 'desc';
}

// Generic comparator factory that prioritizes specific values
export const createPriorityComparator = <T = any>(config: PrioritySortConfig) => {
  return (valueA: any, valueB: any, nodeA: any, nodeB: any, isDescending: boolean) => {
    // Get the values from our target field for comparison
    const fieldValueA = nodeA?.data?.[config.field];
    const fieldValueB = nodeB?.data?.[config.field];
    
    // Check if either value is in our priority list
    const priorityA = config.priorityValues.indexOf(fieldValueA);
    const priorityB = config.priorityValues.indexOf(fieldValueB);
    
    // If both values are in the priority list, sort by their position in the list
    if (priorityA >= 0 && priorityB >= 0) {
      return priorityA - priorityB;
    }
    
    // If only one value is a priority, it goes first
    if (priorityA >= 0) return !isDescending ? -1 : 1;
    if (priorityB >= 0) return !isDescending ? 1 : -1;
    
    // Otherwise do the default comparison
    if (typeof valueA === 'string' && typeof valueB === 'string') {
      return (valueA || '').localeCompare(valueB || '');
    }
    
    // Convert to numbers for numeric comparison
    const numA = Number(valueA) || 0;
    const numB = Number(valueB) || 0;
    return numA - numB;
  };
};

// Apply priority sorting to a set of column definitions
export const applyPrioritySorting = (columnDefs: ColDef[], config: PrioritySortConfig): ColDef[] => {
  return columnDefs.map(colDef => {
    // Only modify the comparator for the specified field
    if (colDef.field === config.field) {
      return {
        ...colDef,
        comparator: createPriorityComparator(config),
        sort: config.direction
      };
    }
    return colDef;
  });
};