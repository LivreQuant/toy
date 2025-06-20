// frontend_dist/book-app/src/components/Dashboard/Container/CustomModals.tsx
import React from 'react';
import { Icon } from '@blueprintjs/core';
import CustomModal from './CustomModal';
import ViewNameStep from './ViewNameStep';
import { Views, ViewInfo } from '../core/layoutTypes';

interface CustomModalsProps {
  // Test Modal
  testModalOpen: boolean;
  setTestModalOpen: (open: boolean) => void;
  
  // Save Layout Modal
  saveLayoutModalOpen: boolean;
  setSaveLayoutModalOpen: (open: boolean) => void;
  handleSaveLayoutConfirm: () => void;
  configServiceReady: boolean;
  bookId: string;
  
  // Add View Modal
  addViewModalOpen: boolean;
  setAddViewModalOpen: (open: boolean) => void;
  selectedViewType: Views | null;
  setSelectedViewType: (type: Views | null) => void;
  handleAddViewConfirm: (viewType: Views, viewName: string) => void;
  getAllViewTypes: () => ViewInfo[];
  getViewDescription: (viewType: Views) => string;
  getViewDefaultName: (viewType: Views) => string;
  
  // Cancel Convictions Modal
  cancelConvictionsModalOpen: boolean;
  setCancelConvictionsModalOpen: (open: boolean) => void;
  handleCancelConvictionsConfirm: () => void;
}

const CustomModals: React.FC<CustomModalsProps> = ({
  testModalOpen,
  setTestModalOpen,
  saveLayoutModalOpen,
  setSaveLayoutModalOpen,
  handleSaveLayoutConfirm,
  configServiceReady,
  bookId,
  addViewModalOpen,
  setAddViewModalOpen,
  selectedViewType,
  setSelectedViewType,
  handleAddViewConfirm,
  getAllViewTypes,
  getViewDescription,
  getViewDefaultName,
  cancelConvictionsModalOpen,
  setCancelConvictionsModalOpen,
  handleCancelConvictionsConfirm
}) => {
  return (
    <>
      {/* Test Custom Modal */}
      <CustomModal
        isOpen={testModalOpen}
        title="🧪 Test Custom Modal"
        onClose={() => setTestModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4>Custom Modal Test</h4>
          <p>This is a test modal to verify modal functionality works properly.</p>
          <p>If you can see this modal clearly on top of everything else, then custom modals work!</p>
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => setTestModalOpen(false)}
              style={{ padding: '8px 16px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px' }}
            >
              Success - Close
            </button>
            <button 
              onClick={() => alert('Button clicked!')}
              style={{ padding: '8px 16px', backgroundColor: '#2196F3', color: 'white', border: 'none', borderRadius: '4px' }}
            >
              Test Alert
            </button>
          </div>
        </div>
      </CustomModal>

      {/* Save Layout Custom Modal */}
      <CustomModal
        isOpen={saveLayoutModalOpen}
        title="💾 Save Layout"
        onClose={() => setSaveLayoutModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Save Layout</h4>
          <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
            Do you want to save the current dashboard layout and column configurations? 
            This will preserve your current view arrangement, column visibility, and sizing for book <strong>{bookId}</strong>.
          </p>
          <div style={{ 
            padding: '12px 16px', 
            backgroundColor: '#f8f9fa', 
            borderRadius: '6px', 
            marginBottom: '20px',
            border: '1px solid #e9ecef'
          }}>
            <div style={{ fontSize: '13px', color: '#666' }}>
              <strong>What will be saved:</strong>
            </div>
            <ul style={{ fontSize: '12px', color: '#888', marginTop: '8px', paddingLeft: '20px' }}>
              <li>Current tab layout and arrangement</li>
              <li>Column visibility and order</li>
              <li>Column widths and sizing</li>
              <li>View configurations</li>
            </ul>
          </div>
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'flex-end',
            paddingTop: '10px',
            borderTop: '1px solid #eee'
          }}>
            <button 
              onClick={() => setSaveLayoutModalOpen(false)}
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
              onClick={handleSaveLayoutConfirm}
              disabled={!configServiceReady}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: configServiceReady ? '#28a745' : '#6c757d',
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: configServiceReady ? 'pointer' : 'not-allowed',
                opacity: configServiceReady ? 1 : 0.6
              }}
            >
              💾 Save Layout
            </button>
          </div>
        </div>
      </CustomModal>

      {/* Add View Custom Modal */}
      <CustomModal
        isOpen={addViewModalOpen}
        title="➕ Add New View"
        onClose={() => {
          setAddViewModalOpen(false);
          setSelectedViewType(null);
        }}
      >
        <div style={{ padding: '20px' }}>
          {!selectedViewType ? (
            <div>
              <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Choose View Type</h4>
              <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
                Select the type of view you want to add to your dashboard:
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {getAllViewTypes().map((viewInfo) => (
                  <div
                    key={viewInfo.type}
                    onClick={() => {
                      console.log('📋 Selected view type:', viewInfo.type);
                      setSelectedViewType(viewInfo.type);
                    }}
                    style={{
                      padding: '16px',
                      border: '2px solid #e9ecef',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      backgroundColor: '#f8f9fa'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.borderColor = '#007bff';
                      e.currentTarget.style.backgroundColor = '#e3f2fd';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.borderColor = '#e9ecef';
                      e.currentTarget.style.backgroundColor = '#f8f9fa';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                      <Icon icon={viewInfo.icon as any} style={{ marginRight: '12px', fontSize: '18px', color: '#007bff' }} />
                      <strong style={{ fontSize: '16px', color: '#333' }}>{viewInfo.name}</strong>
                    </div>
                    <div style={{ fontSize: '14px', color: '#666', paddingLeft: '30px' }}>
                      {getViewDescription(viewInfo.type)}
                    </div>
                  </div>
                ))}
              </div>
              
              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end',
                paddingTop: '20px',
                borderTop: '1px solid #eee'
              }}>
                <button 
                  onClick={() => setAddViewModalOpen(false)}
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
              </div>
            </div>
          ) : (
            <ViewNameStep 
              selectedViewType={selectedViewType}
              onBack={() => setSelectedViewType(null)}
              onCancel={() => {
                setAddViewModalOpen(false);
                setSelectedViewType(null);
              }}
              onConfirm={(viewName: string) => {
                console.log('📋 Creating view:', selectedViewType, viewName);
                handleAddViewConfirm(selectedViewType, viewName);
              }}
              getAllViewTypes={getAllViewTypes}
              getViewDescription={getViewDescription}
              getViewDefaultName={getViewDefaultName}
            />
          )}
        </div>
      </CustomModal>

      {/* Cancel Orders Custom Modal */}
      <CustomModal
        isOpen={cancelConvictionsModalOpen}
        title="🗑️ Cancel All Convictions"
        onClose={() => setCancelConvictionsModalOpen(false)}
      >
        <div style={{ padding: '20px' }}>
          <h4 style={{ margin: '0 0 15px 0', color: '#333' }}>Cancel All Desk Convictions</h4>
          <p style={{ margin: '0 0 20px 0', color: '#666', lineHeight: '1.5' }}>
            Are you sure you want to cancel all active convictions for this trading desk? This action cannot be undone.
          </p>
          <div style={{ 
            padding: '12px 16px', 
            backgroundColor: '#fff3cd', 
            borderRadius: '6px', 
            marginBottom: '20px',
            border: '1px solid #ffeaa7'
          }}>
            <div style={{ fontSize: '13px', color: '#856404' }}>
              <strong>⚠️ Warning:</strong> This will cancel all pending and partially filled convictions
            </div>
          </div>
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'flex-end',
            paddingTop: '10px',
            borderTop: '1px solid #eee'
          }}>
            <button 
              onClick={() => setCancelConvictionsModalOpen(false)}
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
              Keep Convictions
            </button>
            <button 
              onClick={handleCancelConvictionsConfirm}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#dc3545', 
                color: 'white', 
                border: 'none', 
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              🗑️ Cancel All Convictions
            </button>
          </div>
        </div>
      </CustomModal>
    </>
  );
};

export default CustomModals;