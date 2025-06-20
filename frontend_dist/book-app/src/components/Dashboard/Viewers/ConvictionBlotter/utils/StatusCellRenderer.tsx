// src/components/Dashboard/Viewers/ConvictionBlotter/utils/StatusCellRenderer.tsx
import React from 'react';
import { ICellRendererParams } from 'ag-grid-community';

interface ConvictionData {
  status: string;
  [key: string]: any;
}

const StatusCellRenderer: React.FC<ICellRendererParams<ConvictionData, string>> = (props) => {
  if (!props.value) {
    return <span></span>;
  }

  // Similar styling approach to what's in grid.tsx for Russia
  if (props.value === 'ERROR') {
    const errorStyle = { 
      color: '#FF0000', // Bright red
      fontWeight: 700 as const, 
      fontSize: '1.1em',
      width: '100%', 
      height: '100%', 
      display: 'flex', 
      alignItems: 'center', 
      padding: '0px',
      textShadow: '0px 0px 1px rgba(255, 0, 0, 0.5)',
      letterSpacing: '0.5px',
      textTransform: 'uppercase' as const
    };
    return <div style={errorStyle}>{props.value}</div>;
  } else if (props.value === 'WARNING') {
    return <div className="status-warning">{props.value}</div>;
  } else if (props.value === 'READY') {
    return <div className="status-ready">{props.value}</div>;
  }
  
  // Default case
  return <div>{props.value}</div>;
};

export default StatusCellRenderer;