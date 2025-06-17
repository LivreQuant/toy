// OrderBlotterToolbar.tsx
import React from 'react';
import { Button, ButtonGroup, InputGroup, Tag, Intent } from '@blueprintjs/core';

interface OrderBlotterToolbarProps {
  onSubmitOrders: () => void;
  onDeleteSelected: () => void;
  onReplaceFile: () => void;
  onEditColumns: () => void;
  filterText: string;
  onFilterChange: (text: string) => void;
  hasOrders: boolean;
  hasErrors: boolean;
  selectedCount: number;
  selectedOrders: any[];
  dataCount: number;
  lastUpdated: string | null;
  isSubmitting: boolean;
}

const OrderBlotterToolbar: React.FC<OrderBlotterToolbarProps> = ({
  onSubmitOrders,
  onDeleteSelected,
  onReplaceFile,
  onEditColumns,
  filterText,
  onFilterChange,
  hasOrders,
  hasErrors,
  selectedCount,
  selectedOrders,
  dataCount,
  lastUpdated,
  isSubmitting
}) => {
  
  const handleFilterChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    console.log("Filter input changed to:", newValue);
    onFilterChange(newValue);
  };

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      padding: '10px', 
      backgroundColor: '#30404D',
      gap: '10px'
    }}>
      {/* Left section - Submit and Delete */}
      <div style={{ display: 'flex', gap: '10px' }}>
        {!(hasErrors || selectedOrders.some(order => order.status === 'ERROR')) && (
          <Button 
            icon={isSubmitting ? "refresh" : "send-to"} // "refresh" is a valid BlueprintJS icon
            onClick={onSubmitOrders}
            intent={Intent.PRIMARY}
            text={isSubmitting ? "Submitting..." : (selectedCount > 0 ? `Submit ${selectedCount} Order${selectedCount !== 1 ? 's' : ''}` : "Submit")}
            disabled={
              !hasOrders || 
              hasErrors || 
              selectedCount === 0 || 
              selectedOrders.some(order => order.status === 'ERROR') ||
              isSubmitting
            }
          />
        )}
        <Button 
          icon="delete" 
          onClick={onDeleteSelected}
          intent={Intent.WARNING}
          text={selectedCount > 0 ? `Delete ${selectedCount} Order${selectedCount !== 1 ? 's' : ''}` : "Delete"}
          disabled={selectedCount === 0}
        />
      </div>

      {/* Middle section - Search with caution sign */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '10px', 
        flex: '1'
      }}>
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          maxWidth: '300px',
          width: '100%',
        }}>
          {/* Input field with X button inside */}
          <div style={{ 
            position: 'relative', 
            width: '100%',
          }}>
            <InputGroup
              leftIcon="search"
              placeholder="Filter by Instrument, ID, or Order Type..."
              value={filterText}
              onChange={handleFilterChange}
              style={{ 
                width: '100%', 
                borderColor: filterText ? '#FF3A5B' : undefined,
                borderWidth: filterText ? '2px' : undefined,
                borderStyle: filterText ? 'solid' : undefined,
                //boxShadow: filterText ? '0 0 5px rgba(0, 229, 255, 0.5)' : 'none',
              }}
              disabled={!hasOrders}
            />
            {filterText && (
              <button 
                onClick={() => {
                  console.log("Clear filter button clicked");
                  onFilterChange('');
                }} 
                style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '16px',
                  color: '#FF3A5B',
                  padding: '4px'
                }}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Caution icon separate from input */}
        {filterText && (
            <div style={{ 
              backgroundColor: '#FF3A5B', 
              color: 'white',
              padding: '0 12px',
              height: '32px',
              width: '32px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <span style={{ 
                fontSize: '20px',
                lineHeight: 1,
                display: 'flex',
                margin: 0,
                padding: 0,
                transform: 'translateY(-2px)'
              }}>
                ⚠️
              </span>
            </div>
          )}
      </div>
      
      {/* Right section - Replace File and Columns buttons */}
      <div style={{ 
        display: 'flex', 
        gap: '10px', 
        marginLeft: 'auto' 
      }}>
        <Tag style={{ fontSize: '14px' }}>
          # of Orders: {dataCount}
        </Tag>
        <Button 
          icon="folder-open" 
          onClick={onReplaceFile}
          text="Replace File"
        />
        <Button
          icon="manually-entered-data"
          onClick={onEditColumns}
          text="Columns"
          disabled={!hasOrders}
        />
      </div>
    </div>
  );
};

export default OrderBlotterToolbar;