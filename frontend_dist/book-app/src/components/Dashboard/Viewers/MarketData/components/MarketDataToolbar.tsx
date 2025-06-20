// src/components/Dashboard/Viewers/MarketData/MarketDataToolbar.tsx
import React from 'react';
import { Button, ButtonGroup, InputGroup, H4, Tag, Intent } from '@blueprintjs/core';

// Define StreamStatus locally
enum StreamStatus {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  DISCONNECTED = 'DISCONNECTED',
  FAILED = 'FAILED'
}

interface MarketDataToolbarProps {
  status: StreamStatus;
  dataCount: number;
  lastUpdated: string | null;
  filterText: string;
  onFilterChange: (text: string) => void;
  onClearData: () => void;
  onEditColumns: () => void;
}

const MarketDataToolbar: React.FC<MarketDataToolbarProps> = ({
  status,
  dataCount,
  lastUpdated,
  filterText,
  onFilterChange,
  onClearData,
  onEditColumns
}) => {
  const getStatusIntent = (status: StreamStatus): Intent => {
    switch(status) {
      case StreamStatus.CONNECTED: return Intent.SUCCESS;
      case StreamStatus.CONNECTING: return Intent.PRIMARY;
      case StreamStatus.RECONNECTING: return Intent.WARNING;
      case StreamStatus.FAILED: return Intent.DANGER;
      default: return Intent.NONE;
    }
  };

  const getStatusLabel = (status: StreamStatus): string => {
    return status;
  };

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
              placeholder="Filter instruments..."
              value={filterText}
              onChange={handleFilterChange}
              style={{ 
                width: '100%', 
                borderColor: filterText ? '#FF3A5B' : undefined,
                borderWidth: filterText ? '2px' : undefined,
                borderStyle: filterText ? 'solid' : undefined,
              }}
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
      
      {/* Right section - Data count and Columns buttons */}
      <div style={{ 
        display: 'flex', 
        gap: '10px', 
        marginLeft: 'auto' 
      }}>
        <Tag style={{ fontSize: '14px' }}>
          # of Rows: {dataCount}
        </Tag>
        <Button
          icon="manually-entered-data"
          onClick={onEditColumns}
          text="Columns"
        />
      </div>
    </div>
  );
};

export default MarketDataToolbar;