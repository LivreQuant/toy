// src/components/Dashboard/AgGrid/cellStyling.ts
import { ICellRendererParams } from 'ag-grid-community';

// Generic type for highlight configuration
export interface CellHighlightConfig<T> {
  field: string;
  targetValue: any;
  style: Record<string, any>; // Use Record instead of React.CSSProperties
  transform?: (value: any) => string | any;
}

// Creates a cell renderer factory
export const createHighlightCellRenderer = <T = any>(config: CellHighlightConfig<T>) => {
  // Return a function that AG Grid will use to create cell renderer components
  return (params: ICellRendererParams) => {
    // Check if this is the target value we want to highlight
    const shouldHighlight = params.data && 
      params.data[config.field] === config.targetValue;
    
    // Apply style if it matches our target condition
    const cellStyle = shouldHighlight ? config.style : {};
    
    // Use transform function if provided, or just display the value
    const displayValue = config.transform ? 
      config.transform(params.value) : 
      params.value;
    
    // Create DOM element instead of using JSX
    const div = document.createElement('div');
    Object.assign(div.style, cellStyle);
    div.innerText = String(displayValue ?? '');
    
    return div;
  };
};

// Helper to create multiple cell renderers at once
export const createCellRenderers = <T = any>(configs: CellHighlightConfig<T>[]) => {
  const renderers: {[key: string]: any} = {};
  
  configs.forEach(config => {
    renderers[`${config.field}HighlightRenderer`] = createHighlightCellRenderer(config);
  });
  
  return renderers;
};