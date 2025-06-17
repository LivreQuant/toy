// Modified OrderBlotterDashboard.tsx - Key parts updated
import React, { useState, useRef, useEffect } from 'react';
import { GridApi, ColDef } from 'ag-grid-community';
import { AgGridColumnChooserController } from '../../Container/Controllers';
import OrderBlotterToolbar from './OrderBlotterToolbar';
import OrderBlotterGrid from './OrderBlotterGrid';
import { ColumnStateService, ColumnStateDetails } from '../../AgGrid/columnStateService';
import { getOrderBlotterColumnDefs } from './columnDefinitions';
import OrderFileDropzone from './utils/OrderFileDropzone';
import { useOrderData, OrderDataStatus } from './useOrderBlotterData';

//import { OrderService } from '../../../../services_old/api/orderService';
import { OrderService } from '../../../../services/api/services/orderService';

import { Side } from '../../../../protobufs/services/orderentryservice_pb';
import { useAuth } from '../../../Login/AuthProvider';

interface OrderBlotterDashboardProps {
  colController: AgGridColumnChooserController;
  viewId: string;
}

const OrderBlotterDashboard: React.FC<OrderBlotterDashboardProps> = ({ colController, viewId }) => {
  const [filterText, setFilterText] = useState<string>('');
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const [columnDefsState, setColumnDefs] = useState<ColDef[]>(getOrderBlotterColumnDefs());
  const [selectedOrders, setSelectedOrders] = useState<any[]>([]);
  const preventUpdateRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const { isAuthenticated, logout } = useAuth();

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

  const handleFileAccepted = async (file: File) => {
    await processFile(file);
  };
  
  const handleSubmitOrders = async () => {
    // Check if all selected orders are valid (not ERROR status)
    const selectedErrorOrders = selectedOrders.filter(order => order.status === 'ERROR');
    
    if (selectedErrorOrders.length > 0) {
      alert('Cannot submit orders with ERROR status');
      return;
    }
    
    // Use selected orders only if any are selected
    const ordersToSubmit = selectedOrders.length > 0 ? selectedOrders : orderData;
    
    // Filter out any orders with ERROR status
    const validOrders = ordersToSubmit.filter(order => order.status !== 'ERROR');
    
    if (validOrders.length === 0) {
      alert('No valid orders to submit');
      return;
    }
      
    if (!isAuthenticated) {
      alert('You must be logged in to submit orders');
      return;
    }
    
    try {
      setIsSubmitting(true);
      // Get the OrderService instance
      const orderService = OrderService.getInstance();
      
      // Transform the order data to match the service expectations
      const formattedOrders = validOrders.map(order => ({
        clOrderId: order.clOrderId,
        orderId: "0", // TEMPORARY ORDER ID
        instrument: order.instrument,
        exchange: order.exchange,
        side: order.orderSide === 'BUY' ? Side.BUY : Side.SELL,
        quantity: parseFloat(order.quantity),
        price: parseFloat(order.price),
        orderType: order.orderType,
        currency: order.currency,
        fillRate: order.fillRate ? parseFloat(order.fillRate) : 1.0
      }));
      
      // Call the service to insert the orders
      const result = await orderService.insertOrders(formattedOrders);
      
      if (result && result.length > 0) {
        // Update the status of submitted orders
        const updatedOrders = [...orderData];
        const submittedOrderIds = new Set(validOrders.map(order => order.id));
        
        updatedOrders.forEach(order => {
          if (submittedOrderIds.has(order.id)) {
            // Update status to indicate the order has been submitted
            order.status = 'SUBMITTED';
          }
        });
        
        // Update the order data
        updateOrderData(updatedOrders);
        
        alert(`${validOrders.length} orders submitted successfully!`);
      } else {
        alert('Order submission failed');
      }

    } catch (error) {
      console.error('Error submitting orders:', error);
      
      // Check for authentication errors (unauthorized)
      if (error instanceof Error && 
          (error.message.includes('unauthorized') || 
           error.message.includes('unauthenticated') || 
           error.message.includes('token'))) {
        alert('Your session has expired. Please log in again.');
        logout();
        return;
      }
      
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
  
  const editVisibleColumns = () => {
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
  };

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
        <OrderFileDropzone onFileAccepted={handleFileAccepted} />
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