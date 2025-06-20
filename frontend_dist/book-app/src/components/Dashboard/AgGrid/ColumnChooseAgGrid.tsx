// ColumnChooserAgGrid.tsx - updated version
import { AnchorButton, Checkbox, Classes, Dialog, Intent } from '@blueprintjs/core';
import { Column, ColumnState } from 'ag-grid-community';
import React, { useState, useEffect } from "react";
import { AgGridColumnChooserController } from "../Container/Controllers";

export interface ColumnChooserAgGridProps {
  controller: AgGridColumnChooserController;
}

const ColumnChooserAgGrid: React.FC<ColumnChooserAgGridProps> = ({ controller }) => {
  // Initialize columns as an empty array to prevent undefined errors
  const [isOpen, setIsOpen] = useState(false);
  const [columns, setColumns] = useState<ColumnState[]>([]);
  const [tableName, setTableName] = useState("");
  const [callback, setCallback] = useState<(columns: ColumnState[] | undefined) => void>(() => {});
  const [idToHeader, setIdToHeader] = useState<Map<string, string>>(new Map());

  // Register this component with the controller
  useEffect(() => {
    controller.setDialog({
      open: (tableName: string, colStates: ColumnState[], cols: Column[] | null, callback: (columns: ColumnState[] | undefined) => void) => {
        console.log("Column chooser opened with:", {
          tableName,
          colStates: colStates || [],
          cols: cols || [],
          colStatesLength: colStates?.length || 0,
          colsLength: cols?.length || 0
        });
        
        const headerMap = new Map<string, string>();
        
        // Ensure cols is never null
        const safeColumns = cols || [];
        
        for (let col of safeColumns) {
          if (col) {
            const header = col.getDefinition()?.headerName;
            if (header) {
              headerMap.set(col.getColId(), header);
            }
          }
        }
      
        // Ensure colStates is never undefined and preserve conviction
        setIsOpen(true);
        setColumns(colStates || []);
        setCallback(() => callback);
        setTableName(tableName);
        setIdToHeader(headerMap);
      }
    });
  }, [controller]);

  const getTitle = (): string => {
    return `Edit ${tableName} visible columns`;
  };

  const handleChecked = (id: string | undefined, checked: boolean) => {
    const updatedColumns = [...columns];
    for (let col of updatedColumns) {
      if (col.colId === id) {
        col.hide = !checked;
      }
    }

    setColumns(updatedColumns);
  };

  const handleOK = () => {
    setIsOpen(false);
    callback(columns);
  };

  const handleCancel = () => {
    setIsOpen(false);
    callback(undefined);
  };

  // Add a conditional check to prevent rendering checkboxes with undefined data
  const renderCheckboxes = () => {
    if (!columns || columns.length === 0) {
      return <div>No columns available</div>;
    }
    
    return columns.map(col => (
      <Checkbox 
        key={col.colId} 
        checked={!col.hide} 
        label={col.colId ? idToHeader.get(col.colId) : col.colId}  
        onChange={(e: React.FormEvent<HTMLInputElement>) => {
          handleChecked(col.colId, e.currentTarget.checked);
        }} 
      />
    ));
  };

  return (  
    // ColumnChooserAgGrid.tsx (continued)
    <Dialog
      icon="bring-data"
      onClose={handleCancel}
      title={getTitle()}
      isOpen={isOpen}
      className="bp3-dark"
    >
      <div className={Classes.DIALOG_BODY}>
        {renderCheckboxes()}
      </div>
      <div className={Classes.DIALOG_FOOTER}>
        <div className={Classes.DIALOG_FOOTER_ACTIONS}>
          <AnchorButton 
            onClick={handleOK}
            intent={Intent.PRIMARY}
          >
            OK
          </AnchorButton>
          <AnchorButton 
            onClick={handleCancel}
            intent={Intent.DANGER}
          >
            Cancel
          </AnchorButton>
        </div>
      </div>
    </Dialog>
  );
};

export default ColumnChooserAgGrid;