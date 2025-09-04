// frontend_dist/book-app/src/components/Dashboard/Container/ViewNameStep.tsx
import React, { useState, useEffect } from 'react';
import { Icon } from '@blueprintjs/core';
import { Views, ViewInfo } from '../core/layoutTypes';

interface ViewNameStepProps {
  selectedViewType: Views;
  onBack: () => void;
  onCancel: () => void;
  onConfirm: (viewName: string) => void;
  getAllViewTypes: () => ViewInfo[];
  getViewDescription: (viewType: Views) => string;
  getViewDefaultName: (viewType: Views) => string;
}

const ViewNameStep: React.FC<ViewNameStepProps> = ({
  selectedViewType,
  onBack,
  onCancel,
  onConfirm,
  getAllViewTypes,
  getViewDescription,
  getViewDefaultName
}) => {
  const [viewName, setViewName] = useState('');

  useEffect(() => {
    if (selectedViewType) {
      setViewName(getViewDefaultName(selectedViewType));
    }
  }, [selectedViewType, getViewDefaultName]);

  const selectedViewInfo = getAllViewTypes().find(v => v.type === selectedViewType);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (viewName.trim()) {
      onConfirm(viewName.trim());
    }
  };

  return (
    <div>
      <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Configure New View</h4>
      <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
        You've selected <strong>{selectedViewInfo?.name}</strong>. Now give it a custom name:
      </p>
      
      <div style={{
        padding: '12px 16px',
        backgroundColor: '#e3f2fd',
        borderRadius: '6px',
        marginBottom: '20px',
        border: '1px solid #90caf9'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <Icon icon={selectedViewInfo?.icon as any} style={{ marginRight: '8px', color: '#1976d2' }} />
          <strong style={{ color: '#1976d2' }}>{selectedViewInfo?.name}</strong>
        </div>
        <div style={{ fontSize: '14px', color: '#555' }}>
          {getViewDescription(selectedViewType)}
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontWeight: '500',
            fontSize: '14px',
            color: '#333'
          }}>
            View Name <span style={{ color: '#e74c3c' }}>*</span>
          </label>
          <input
            type="text"
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            placeholder="Enter a name for this view..."
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px',
              transition: 'border-color 0.2s'
            }}
            autoFocus
            required
          />
          {!viewName.trim() && (
            <div style={{ 
              fontSize: '12px', 
              color: '#e74c3c', 
              marginTop: '4px' 
            }}>
              Please enter a name for your view
            </div>
          )}
        </div>

        <div style={{ 
          display: 'flex', 
          gap: '12px', 
          justifyContent: 'flex-end',
          paddingTop: '20px',
          borderTop: '1px solid #eee'
        }}>
          <button 
            type="button"
            onClick={onBack}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#f8f9fa', 
              color: '#6c757d', 
              border: '1px solid #dee2e6', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            ← Back
          </button>
          <button 
            type="button"
            onClick={onCancel}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#6c757d', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button 
            type="submit"
            disabled={!viewName.trim()}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: viewName.trim() ? '#28a745' : '#6c757d',
              color: 'white', 
              border: 'none', 
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: viewName.trim() ? 'pointer' : 'not-allowed',
              opacity: viewName.trim() ? 1 : 0.6
            }}
          >
            ➕ Create View
          </button>
        </div>
      </form>
    </div>
  );
};

export default ViewNameStep;