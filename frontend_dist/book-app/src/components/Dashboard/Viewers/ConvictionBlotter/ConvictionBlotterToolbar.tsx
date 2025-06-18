// src/components/Dashboard/Viewers/ConvictionBlotter/ConvictionBlotterToolbar.tsx
import React from 'react';
import { Button, InputGroup, Tag, Intent } from '@blueprintjs/core';
import { ConvictionModelConfig } from '@trading-app/types-core';

interface ConvictionBlotterToolbarProps {
  title?: string;
  onSubmitConvictions: () => void;
  onDeleteSelected: () => void;
  onReplaceFile: () => void;
  onEditColumns: () => void;
  filterText: string;
  onFilterChange: (text: string) => void;
  hasConvictions: boolean;
  hasErrors: boolean;
  selectedCount: number;
  selectedConvictions: any[];
  dataCount: number;
  lastUpdated: string | null;
  isSubmitting: boolean;
  convictionSchema?: ConvictionModelConfig | null;
}

const ConvictionBlotterToolbar: React.FC<ConvictionBlotterToolbarProps> = ({
  title = "Conviction Blotter",
  onSubmitConvictions,
  onDeleteSelected,
  onReplaceFile,
  onEditColumns,
  filterText,
  onFilterChange,
  hasConvictions,
  hasErrors,
  selectedCount,
  selectedConvictions,
  dataCount,
  lastUpdated,
  isSubmitting,
  convictionSchema
}) => {
  
  const handleFilterChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange(e.target.value);
  };

  const getSchemaDisplayText = (): string => {
    if (!convictionSchema) return 'Default Schema';
    
    const approach = convictionSchema.portfolioApproach;
    const method = approach === 'target' 
      ? convictionSchema.targetConvictionMethod 
      : convictionSchema.incrementalConvictionMethod;
    
    return `${approach}/${method}`;
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
        {!(hasErrors || selectedConvictions.some(conviction => conviction.status === 'ERROR')) && (
          <Button 
            icon={isSubmitting ? "refresh" : "send-to"}
            onClick={onSubmitConvictions}
            intent={Intent.PRIMARY}
            text={isSubmitting ? "Submitting..." : (selectedCount > 0 ? `Submit ${selectedCount} Conviction${selectedCount !== 1 ? 's' : ''}` : "Submit")}
            disabled={
              !hasConvictions || 
              hasErrors || 
              selectedCount === 0 || 
              selectedConvictions.some(conviction => conviction.status === 'ERROR') ||
              isSubmitting
            }
          />
        )}
        <Button 
          icon="delete" 
          onClick={onDeleteSelected}
          intent={Intent.WARNING}
          text={selectedCount > 0 ? `Delete ${selectedCount} Conviction${selectedCount !== 1 ? 's' : ''}` : "Delete"}
          disabled={selectedCount === 0}
        />
      </div>

      {/* Middle section - Schema info and Search */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '15px', 
        flex: '1'
      }}>
        {/* Schema indicator */}
        <Tag 
          intent={convictionSchema ? Intent.SUCCESS : Intent.WARNING}
          style={{ fontSize: '12px', whiteSpace: 'nowrap' }}
        >
          {getSchemaDisplayText()}
        </Tag>

        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          maxWidth: '300px',
          width: '100%',
        }}>
          <div style={{ 
            position: 'relative', 
            width: '100%',
          }}>
            <InputGroup
              leftIcon="search"
              placeholder="Filter by Instrument, ID, or Conviction Type..."
              value={filterText}
              onChange={handleFilterChange}
              style={{ 
                width: '100%', 
                borderColor: filterText ? '#FF3A5B' : undefined,
                borderWidth: filterText ? '2px' : undefined,
                borderStyle: filterText ? 'solid' : undefined,
              }}
              disabled={!hasConvictions}
            />
            {filterText && (
              <button 
                onClick={() => onFilterChange('')} 
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

       {/* Filter warning indicator */}
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
     
     {/* Right section - Stats and Controls */}
     <div style={{ 
       display: 'flex', 
       gap: '10px', 
       marginLeft: 'auto',
       alignItems: 'center'
     }}>
       <Tag style={{ fontSize: '14px' }}>
         # of Convictions: {dataCount}
       </Tag>
       {lastUpdated && (
         <Tag style={{ fontSize: '12px', opacity: 0.8 }}>
           Updated: {lastUpdated}
         </Tag>
       )}
       <Button 
         icon="folder-open" 
         onClick={onReplaceFile}
         text="Replace File"
       />
       <Button
         icon="manually-entered-data"
         onClick={onEditColumns}
         text="Columns"
         disabled={!hasConvictions}
       />
     </div>
   </div>
 );
};

export default ConvictionBlotterToolbar;