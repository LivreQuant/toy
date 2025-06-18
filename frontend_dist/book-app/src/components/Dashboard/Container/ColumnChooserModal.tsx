// src/components/Dashboard/Container/ColumnChooserModal.tsx
import React, { useState, useEffect } from 'react';
import './ColumnChooserModal.css';

interface ColumnState {
  colId: string;
  hide: boolean;
}

interface ColumnChooserModalProps {
  isOpen: boolean;
  title: string;
  columns: ColumnState[];
  columnHeaders: { [key: string]: string };
  onClose: () => void;
  onApply: (columns: ColumnState[]) => void;
}

const ColumnChooserModal: React.FC<ColumnChooserModalProps> = ({
  isOpen,
  title,
  columns,
  columnHeaders,
  onClose,
  onApply
}) => {
  const [localColumns, setLocalColumns] = useState<ColumnState[]>([]);

  useEffect(() => {
    setLocalColumns([...columns]);
  }, [columns]);

  const handleToggleColumn = (colId: string) => {
    setLocalColumns(prev => 
      prev.map(col => 
        col.colId === colId 
          ? { ...col, hide: !col.hide }
          : col
      )
    );
  };

  const handleSelectAll = () => {
    setLocalColumns(prev => 
      prev.map(col => ({ ...col, hide: false }))
    );
  };

  const handleSelectNone = () => {
    setLocalColumns(prev => 
      prev.map(col => ({ ...col, hide: true }))
    );
  };

  const handleApply = () => {
    onApply(localColumns);
    onClose();
  };

  const handleCancel = () => {
    setLocalColumns([...columns]); // Reset to original
    onClose();
  };

  const visibleCount = localColumns.filter(col => !col.hide).length;
  const totalCount = localColumns.length;

  if (!isOpen) return null;

  return (
    <div className="column-chooser-overlay" onClick={handleCancel}>
      <div className="column-chooser-container" onClick={(e) => e.stopPropagation()}>
        <div className="column-chooser-header">
          <h3>Configure {title} Columns</h3>
          <button className="column-chooser-close" onClick={handleCancel}>×</button>
        </div>
        
        <div className="column-chooser-body">
          <div className="column-chooser-stats">
            <span>Showing {visibleCount} of {totalCount} columns</span>
            <div className="column-chooser-actions">
              <button 
                onClick={handleSelectAll}
                className="select-action-button"
                disabled={visibleCount === totalCount}
              >
                Select All
              </button>
              <button 
                onClick={handleSelectNone}
                className="select-action-button"
                disabled={visibleCount === 0}
              >
                Select None
              </button>
            </div>
          </div>

          <div className="column-list">
            {localColumns.map((column) => (
              <div key={column.colId} className="column-item">
                <label className="column-checkbox">
                  <input
                    type="checkbox"
                    checked={!column.hide}
                    onChange={() => handleToggleColumn(column.colId)}
                  />
                  <span className="checkbox-custom"></span>
                  <span className="column-name">
                    {columnHeaders[column.colId] || column.colId}
                  </span>
                </label>
              </div>
            ))}
          </div>
        </div>
        
        <div className="column-chooser-footer">
          <button 
            onClick={handleCancel}
            className="column-chooser-button cancel-button"
          >
            Cancel
          </button>
          <button 
            onClick={handleApply}
            className="column-chooser-button apply-button"
          >
            Apply Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default ColumnChooserModal;