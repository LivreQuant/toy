// src/components/Dashboard/Viewers/ConvictionBlotter/convictionColumnDefinitions.ts
import { ColDef, CellStyle } from 'ag-grid-community';
import { ConvictionModelConfig } from '@trading-app/types-core';
import StatusCellRenderer from '../utils/StatusCellRenderer';
import { GlobalColours } from '../../../AgGrid/constants/Colours';

// Base columns that are always present
const getBaseConvictionColumnDefs = (): ColDef[] => [
  { 
    headerName: 'Status', 
    field: 'status', 
    width: 100,
    filter: true,
    cellRenderer: StatusCellRenderer,
    pinned: 'left'
  },
  { 
    headerName: 'Conviction ID', 
    field: 'convictionId', 
    width: 150,
    sortable: true,
    filter: true,
    pinned: 'left'
  },
  { 
    headerName: 'Instrument', 
    field: 'instrumentId', 
    width: 120,
    sortable: true,
    filter: true
  }
];

// Dynamic columns based on conviction schema
const getDynamicConvictionColumnDefs = (schema: ConvictionModelConfig | null): ColDef[] => {
  if (!schema) {
    // Default columns when no schema is available
    return [
      { headerName: 'Side', field: 'side', width: 80 },
      { headerName: 'Score', field: 'score', width: 80 },
      { headerName: 'Quantity', field: 'quantity', width: 100 }
    ];
  }

  const dynamicColumns: ColDef[] = [];

  // Portfolio approach determines core columns
  if (schema.portfolioApproach === 'target') {
    if (schema.targetConvictionMethod === 'percent') {
      dynamicColumns.push({
        headerName: 'Target %',
        field: 'targetPercent',
        width: 100,
        valueFormatter: (params) => params.value ? `${params.value.toFixed(2)}%` : '',
        cellStyle: (params): CellStyle | null => {
          if (params.value > 0) return { color: '#4CAF50' };
          if (params.value < 0) return { color: '#F44336' };
          return null;
        }
      });
    } else if (schema.targetConvictionMethod === 'notional') {
      dynamicColumns.push({
        headerName: 'Target Notional',
        field: 'targetNotional',
        width: 120,
        valueFormatter: (params) => params.value ? `$${params.value.toLocaleString()}` : '',
        cellStyle: (params): CellStyle | null => {
          if (params.value > 0) return { color: '#4CAF50' };
          if (params.value < 0) return { color: '#F44336' };
          return null;
        }
      });
    }
  } else {
    // Incremental approach
    if (schema.incrementalConvictionMethod === 'side_score') {
      dynamicColumns.push(
        {
          headerName: 'Side',
          field: 'side',
          width: 80,
          cellStyle: (params): CellStyle | null => {
            if (params.value === 'BUY') return { backgroundColor: GlobalColours.BUYBKG, color: '#000000' };
            if (params.value === 'SELL') return { backgroundColor: GlobalColours.SELLBKG, color: '#000000' };
            return null;
          }
        },
        {
          headerName: 'Score',
          field: 'score',
          width: 80,
          valueFormatter: (params) => `${params.value}/${schema.maxScore || 5}`,
          cellStyle: (params): CellStyle | null => {
            const maxScore = schema.maxScore || 5;
            const normalizedScore = params.value / maxScore;
            if (normalizedScore >= 0.8) return { color: '#4CAF50', fontWeight: 'bold' };
            if (normalizedScore >= 0.6) return { color: '#FF9800' };
            if (normalizedScore <= 0.4) return { color: '#F44336' };
            return null;
          }
        }
      );
    } else if (schema.incrementalConvictionMethod === 'side_qty') {
      dynamicColumns.push(
        {
          headerName: 'Side',
          field: 'side',
          width: 80,
          cellStyle: (params): CellStyle | null => {
            if (params.value === 'BUY') return { backgroundColor: GlobalColours.BUYBKG, color: '#000000' };
            if (params.value === 'SELL') return { backgroundColor: GlobalColours.SELLBKG, color: '#000000' };
            return null;
          }
        },
        {
          headerName: 'Quantity',
          field: 'quantity',
          width: 100,
          valueFormatter: (params) => params.value ? params.value.toLocaleString() : ''
        }
      );
    } else if (schema.incrementalConvictionMethod === 'zscore') {
      dynamicColumns.push({
        headerName: 'Z-Score',
        field: 'zscore',
        width: 100,
        valueFormatter: (params) => params.value ? params.value.toFixed(3) : '',
        cellStyle: (params): CellStyle | null => {
          if (params.value > 2) return { color: '#4CAF50', fontWeight: 'bold' };
          if (params.value > 1) return { color: '#4CAF50' };
          if (params.value < -2) return { color: '#F44336', fontWeight: 'bold' };
          if (params.value < -1) return { color: '#F44336' };
          return null;
        }
      });
    } else if (schema.incrementalConvictionMethod === 'multi-horizon') {
      // Add columns for each horizon
      const horizons = schema.horizons || ['1d', '5d', '20d'];
      horizons.forEach(horizon => {
        const match = horizon.match(/(\d+)([mhdw])/);
        if (match) {
          const [_, value, unit] = match;
          let unitText = unit;
          
          switch(unit) {
            case 'm': unitText = 'min'; break;
            case 'h': unitText = 'hour'; break;
            case 'd': unitText = 'day'; break;
            case 'w': unitText = 'week'; break;
          }
          
          const fieldName = `z${value}${unitText}`;
          dynamicColumns.push({
            headerName: `Z-${value}${unit}`,
            field: fieldName,
            width: 90,
            valueFormatter: (params) => params.value ? params.value.toFixed(2) : '',
            cellStyle: (params): CellStyle | null => {
              if (params.value > 1.5) return { color: '#4CAF50' };
              if (params.value < -1.5) return { color: '#F44336' };
              return null;
            }
          });
        }
      });
    }
  }

  return dynamicColumns;
};

// Optional columns that may be present
const getOptionalConvictionColumnDefs = (): ColDef[] => [
  {
    headerName: 'Participation Rate',
    field: 'participationRate',
    width: 120,
    valueFormatter: (params) => {
      if (typeof params.value === 'number') {
        return `${(params.value * 100).toFixed(1)}%`;
      }
      return params.value || '';
    }
  },
  {
    headerName: 'Tag',
    field: 'tag',
    width: 100,
    cellStyle: { fontStyle: 'italic', color: '#666' } as CellStyle
  }
];

// Main function to generate conviction column definitions
export const getConvictionColumnDefs = (schema: ConvictionModelConfig | null): ColDef[] => {
  const baseColumns = getBaseConvictionColumnDefs();
  const dynamicColumns = getDynamicConvictionColumnDefs(schema);
  const optionalColumns = getOptionalConvictionColumnDefs();

  return [
    ...baseColumns,
    ...dynamicColumns,
    ...optionalColumns
  ];
};

// Helper function to validate conviction data matches schema
export const validateConvictionData = (data: any[], schema: ConvictionModelConfig | null): {
  isValid: boolean;
  missingFields: string[];
  unexpectedFields: string[];
} => {
  if (!data.length) return { isValid: true, missingFields: [], unexpectedFields: [] };

  const requiredFields = ['convictionId', 'instrumentId'];
  const expectedFields = new Set(requiredFields);
  
  if (schema) {
    if (schema.portfolioApproach === 'target') {
      expectedFields.add(schema.targetConvictionMethod === 'percent' ? 'targetPercent' : 'targetNotional');
    } else {
      if (schema.incrementalConvictionMethod === 'side_score') {
        expectedFields.add('side');
        expectedFields.add('score');
      } else if (schema.incrementalConvictionMethod === 'side_qty') {
        expectedFields.add('side');
        expectedFields.add('quantity');
      } else if (schema.incrementalConvictionMethod === 'zscore') {
        expectedFields.add('zscore');
      } else if (schema.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = schema.horizons || [];
        horizons.forEach(horizon => {
          const match = horizon.match(/(\d+)([mhdw])/);
          if (match) {
            const [_, value, unit] = match;
            let unitText = unit;
            switch(unit) {
              case 'm': unitText = 'min'; break;
              case 'h': unitText = 'hour'; break;
              case 'd': unitText = 'day'; break;
              case 'w': unitText = 'week'; break;
            }
            expectedFields.add(`z${value}${unitText}`);
          }
        });
      }
    }
  }

  // Optional fields
  expectedFields.add('participationRate');
  expectedFields.add('tag');
  expectedFields.add('status');

  const sampleRecord = data[0];
  const actualFields = new Set(Object.keys(sampleRecord));
  
  const missingFields = requiredFields.filter(field => !actualFields.has(field));
  const unexpectedFields = Array.from(actualFields).filter(field => !expectedFields.has(field));

  return {
    isValid: missingFields.length === 0,
    missingFields,
    unexpectedFields
  };
};