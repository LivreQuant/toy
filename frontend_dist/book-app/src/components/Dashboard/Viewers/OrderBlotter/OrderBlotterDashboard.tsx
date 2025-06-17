// src/components/Dashboard/Viewers/OrderBlotter/OrderBlotterDashboard.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../Container/Controllers';
import OrderBlotterToolbar from './OrderBlotterToolbar';
import OrderBlotterGrid from './OrderBlotterGrid';
import { ColumnStateService, ColumnStateDetails } from '../../AgGrid/columnStateService';
import { getOrderBlotterColumnDefs } from './columnDefinitions';
import { useOrderData, OrderDataStatus } from './useOrderBlotterData';
import { useParams } from 'react-router-dom';

import FileUploadZone from '../../../Simulator/FileUploadZone';
import ConvictionFileProcessor from '../../../Simulator/ConvictionFileProcessor';
import { useConvictionManager } from '../../../../contexts/ConvictionContext';

import { useToast } from '../../../../hooks/useToast';

import { Side } from '../../Mock/OrderDataService';

interface OrderBlotterDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
  onColumnHandlerReady?: (handler: () => void) => void; // NEW
}

const OrderBlotterDashboard: React.FC<OrderBlotterDashboardProps> = ({ 
  colController, 
  viewId,
  onColumnHandlerReady // NEW
}) => {
  const [filterText, setFilterText] = useState<string>('');
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [columnDefsState, setColumnDefs] = useState<ColDef[]>(getOrderBlotterColumnDefs());
  const [selectedOrders, setSelectedOrders] = useState<any[]>([]);
  const preventUpdateRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const convictionManager = useConvictionManager();
  const { addToast } = useToast();

  const { bookId } = useParams<{ bookId: string }>();

  // Use a ref to store column definitions to prevent regeneration on data changes
  const columnDefsRef = useRef(columnDefsState);
  
  const {
    orderData,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    processFile,
    clearData,
    updateOrderData
  } = useOrderData(viewId);

  // Only update the ref if column definitions have explicitly changed
  useEffect(() => {
    columnDefsRef.current = columnDefsState;
  }, [columnDefsState]);

  // Modified useEffect to include width handling
  useEffect(() => {
    // Get the saved column order
    const columnStateService = ColumnStateService.getInstance();
    const savedState = columnStateService.getViewColumnState(viewId);
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (savedColumnOrder.length > 0) {
      // Get the default column definitions
      const defaultDefs = getOrderBlotterColumnDefs();
      
      // Create a new ordered array based on the saved order
      const orderedDefs: ColDef[] = [];
      
      // First add columns in the saved order
      savedColumnOrder.forEach(colId => {
        const def = defaultDefs.find(d => d.field === colId);
        if (def) {
          // Apply saved visibility and width
          orderedDefs.push({
            ...def,
            hide: !savedState[colId]?.visibility,
            // Use saved width if available, otherwise use the default width from column definition
            width: savedState[colId]?.width || def.width
          });
        }
      });
      
      // Then add any remaining columns not in the saved order
      defaultDefs.forEach(def => {
        if (def.field && !savedColumnOrder.includes(def.field)) {
          orderedDefs.push(def);
        }
      });
      
      // Update the column definitions state
      setColumnDefs(orderedDefs);
    }
  }, [viewId]); // This effect should run once when component mounts

  const handleFileAccepted = (file: File | null) => {
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const processor = new ConvictionFileProcessor(null, addToast);
      
      // Use the existing processor but call it "orders" instead of "convictions"
      const parsedOrders = processor.processSubmitCsv(content);
      
      if (parsedOrders.length > 0) {
        // Convert conviction format to order format if needed
        const orderData = parsedOrders.map(item => ({
          ...item,
          orderSide: item.side,
          status: item.status || 'READY'
        }));
        
        updateOrderData(orderData);
        // This will set isDropzoneVisible to false through the hook
      }
    };
    
    reader.readAsText(file);
  };

  const handleSubmitOrders = async () => {
    const selectedErrorOrders = selectedOrders.filter(order => order.status === 'ERROR');
    
    if (selectedErrorOrders.length > 0) {
      alert('Cannot submit orders with ERROR status');
      return;
    }
    
    const ordersToSubmit = selectedOrders.length > 0 ? selectedOrders : orderData;
    const validOrders = ordersToSubmit.filter(order => order.status !== 'ERROR');
    
    if (validOrders.length === 0) {
      alert('No valid orders to submit');
      return;
    }
    
    try {
      setIsSubmitting(true);
      
      // Convert orders to conviction format
      const convictions = validOrders.map(order => ({
        instrumentId: order.instrument,
        convictionId: order.clOrderId,
        side: order.orderSide,
        quantity: order.quantity,
        // Add other fields as needed
      }));
      
      // Use existing conviction submission
      const response = await convictionManager.submitConvictions({
        bookId: bookId!, // Get from useParams
        convictions: convictions,
        notes: `Order submission: ${validOrders.length} orders`
      });
      
      if (response.success) {
        // Update order status
        const updatedOrders = [...orderData];
        const submittedOrderIds = new Set(validOrders.map(order => order.id));
        
        updatedOrders.forEach(order => {
          if (submittedOrderIds.has(order.id)) {
            order.status = 'SUBMITTED';
          }
        });
        
        updateOrderData(updatedOrders);
        alert(`${validOrders.length} orders submitted successfully!`);
      } else {
        alert('Order submission failed');
      }
      
    } catch (error) {
      console.error('Error submitting orders:', error);
      alert(`Error submitting orders: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };
    
  const handleDeleteSelectedOrders = () => {
    // Allow deleting selected orders (even if they have ERROR status)
    if (selectedOrders.length === 0) {
      alert('No orders selected');
      return;
    }
    
    // Create a map of selected order IDs for faster lookup
    const selectedOrderIds = new Set(selectedOrders.map(order => order.id));
    
    // Filter out the selected orders
    const remainingOrders = orderData.filter(order => !selectedOrderIds.has(order.id));
    
    // Update our data through the hook
    updateOrderData(remainingOrders);
    setSelectedOrders([]);
    
    if (remainingOrders.length === 0) {
      clearData();
    }
  };
  
  const handleSelectionChanged = () => {
    if (gridApi) {
      const selected = gridApi.getSelectedRows();
      
      // Add detailed logging
      console.log("Selection Changed - Raw Selected Rows:", selected);
      console.log("Selection Changed - Number of Selected Rows:", selected.length);
      
      // Log the details of each selected row
      selected.forEach((row, index) => {
        console.log(`Selected Row ${index + 1}:`, {
          id: row.id,
          status: row.status,
          // Add any other key properties you want to log
        });
      });
      
      setSelectedOrders(selected);
    } else {
      console.warn("Grid API is not available during selection");
    }
  };
  
  const handleReplaceFile = () => {
    clearData();
  };
  
  const handleFilterChange = (text: string) => {
    console.log("Filter text changed to:", text);
    setFilterText(text);
    
    // No need to filter data here - AG Grid will handle it internally
  };
  
  // UPDATED: Make editVisibleColumns stable with useCallback
  const editVisibleColumns = useCallback(() => {
    try {
      // Skip grid API calls entirely and just use our column definitions
      const columnDefs = columnDefsRef.current;
      
      // Filter out the 'id' column before creating column states
      const visibleColumnDefs = columnDefs.filter(def => def.field !== 'id');
      
      // Create column states directly from filtered column definitions
      const columnStates = visibleColumnDefs.map(def => ({
        colId: def.field || '',
        hide: def.hide === true
      }));
      
      // Create columns-like objects for header mapping (also filtered)
      const columnLikes = visibleColumnDefs.map(def => ({
        getColId: () => def.field || '',
        getDefinition: () => ({ headerName: def.headerName || def.field || '' })
      }));
      
      colController.open(
        "Order Blotter",
        columnStates,
        columnLikes as any,
        (newColumnsState) => {
          if (!newColumnsState) {
            return;
          }
          
          try {
            // Check if anything has actually changed
            const hasChanges = newColumnsState.some(state => {
              const columnDef = columnDefsRef.current.find(def => def.field === state.colId);
              return columnDef && (columnDef.hide !== state.hide);
            });
            
            if (!hasChanges) {
              return;
            }
            
            // Create new column definitions with updated visibility
            const updatedColumnDefs = columnDefs.map(colDef => {
              if (!colDef.field) return colDef;
              
              const newState = newColumnsState.find(state => state.colId === colDef.field);
              if (newState !== undefined) {
                return {
                  ...colDef,
                  hide: newState.hide === true
                };
              }
              return colDef;
            });
            
            // Update the state with new column definitions
            preventUpdateRef.current = true;
            setColumnDefs(updatedColumnDefs);
            columnDefsRef.current = updatedColumnDefs;
            
            // Get current column state to preserve widths
            const columnStateService = ColumnStateService.getInstance();
            const currentState = columnStateService.getViewColumnState(viewId);
            const columnState: ColumnStateDetails = {};
            
            // Convert from column state to our detailed state format
            newColumnsState.forEach((state, index) => {
              if (state.colId) {
                // Preserve width from current state if available
                const currentWidth = currentState[state.colId]?.width;
                
                columnState[state.colId] = {
                  visibility: !state.hide,
                  order: index,
                  ...(currentWidth !== undefined ? { width: currentWidth } : {})
                };
              }
            });
            
            columnStateService.setViewColumnState(viewId, columnState);
            
            // Force refresh the grid
            if (gridApi) {
              gridApi.setGridOption('columnDefs', updatedColumnDefs);
            }
            
            setTimeout(() => {
              preventUpdateRef.current = false;
            }, 0);
          } catch (error) {
            console.error("Error applying column state:", error);
          }
        }
      );
    } catch (error) {
      console.error("Error opening column chooser:", error);
    }
  }, [colController, viewId, gridApi]);

  // NEW: Register the column handler with the container
  useEffect(() => {
    if (onColumnHandlerReady) {
      console.log('📋 OrderBlotter: Registering column handler');
      onColumnHandlerReady(editVisibleColumns);
    }
  }, [onColumnHandlerReady, editVisibleColumns]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Only show toolbar when dropzone is not visible */}
      {!isDropzoneVisible && (
        <OrderBlotterToolbar
          onSubmitOrders={handleSubmitOrders}
          onDeleteSelected={handleDeleteSelectedOrders}
          onReplaceFile={handleReplaceFile}
          onEditColumns={editVisibleColumns}
          filterText={filterText}
          onFilterChange={handleFilterChange}
          hasOrders={orderData.length > 0}
          hasErrors={orderData.some(order => order.status === 'ERROR')}
          selectedCount={selectedOrders.length}
          selectedOrders={selectedOrders}
          dataCount={dataCount}
          lastUpdated={lastUpdated}
          isSubmitting={isSubmitting}
        />
      )}

      {error && (
        <div style={{ 
          padding: '8px', 
          margin: '0 10px', 
          backgroundColor: '#f8d7da', 
          color: '#721c24', 
          borderRadius: '4px' 
        }}>
          {error}
        </div>
      )}
      
      {isDropzoneVisible ? (
        <FileUploadZone
          title="Order File"
          acceptedTypes=".csv"
          onFileSelect={handleFileAccepted}
          file={null}
          required={true}
          description="CSV file containing your orders"
        />
      ) : (
        <OrderBlotterGrid
          columnDefs={columnDefsRef.current}
          rowData={orderData}  // Pass the original data, not filtered
          viewId={viewId}
          filterText={filterText}
          onGridReady={setGridApi}
          onColumnDefsChange={(newColDefs) => {
            if (preventUpdateRef.current) return;
            
            // Compare with current state to avoid unnecessary updates
            if (JSON.stringify(newColDefs) !== JSON.stringify(columnDefsRef.current)) {
              setColumnDefs(newColDefs);
            }
          }}
          onSelectionChanged={handleSelectionChanged}
        />
      )}
    </div>
  );
};

export default OrderBlotterDashboard;