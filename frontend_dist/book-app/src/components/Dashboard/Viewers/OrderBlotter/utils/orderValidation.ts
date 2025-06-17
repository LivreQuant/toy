// orderValidation.ts
// Valid values for various fields
const VALID_SIDES = ['BUY', 'SELL'];
const VALID_CURRENCIES = ['USD', 'EUR', 'JPY', 'GBP', 'CHF', 'CAD', 'AUD', 'NZD'];
const VALID_ORDER_TYPES = ['MARKET', 'LIMIT'];

/**
 * Validates a single order row from CSV
 */
export const validateOrderRow = (row: any, rowIndex: number): any => {
  const errors: string[] = [];
  
  // Helper function to validate numeric fields
  const validateNumeric = (field: string, value: any, min: number = 0): boolean => {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) {
      errors.push(`${field} must be a number`);
      return false;
    }
    if (numValue <= min) {
      errors.push(`${field} must be greater than ${min}`);
      return false;
    }
    return true;
  };
  
  // Validate orderSide
  if (!row.orderSide) {
    errors.push(`Order side is required`);
  } else if (!VALID_SIDES.includes(String(row.orderSide).toUpperCase())) {
    errors.push(`Order side must be either BUY or SELL`);
  }
  
  // Validate instrument
  if (!row.instrument) {
    errors.push(`Instrument is required`);
  }
  
  // Validate exchange
  if (!row.exchange) {
    errors.push(`Exchange is required`);
  }
  
  // Validate quantity
  validateNumeric('Quantity', row.quantity, 0);
  
  // Validate currency
  if (!row.currency) {
    errors.push(`Currency is required`);
  } else if (!VALID_CURRENCIES.includes(String(row.currency).toUpperCase())) {
    errors.push(`Currency not supported. Valid currencies are: ${VALID_CURRENCIES.join(', ')}`);
  }
  
  // Validate price
  validateNumeric('Price', row.price, 0);
  
  // Validate orderType
  if (!row.orderType) {
    errors.push(`Order type is required`);
  } else if (!VALID_ORDER_TYPES.includes(String(row.orderType).toUpperCase())) {
    errors.push(`Order type must be either MARKET or LIMIT`);
  }
  
  // Validate fillRate
  if (validateNumeric('Fill rate', row.fillRate, 0)) {
    const fillRate = parseFloat(row.fillRate);
    if (fillRate > 1.0) {
      errors.push(`Fill rate cannot be greater than 1.0`);
    }
  }
  
  // Validate clOrderId
  if (!row.clOrderId) {
    errors.push(`Client order ID is required`);
  }
  
  // Determine status - add WARNING status for certain conditions
  let status = 'READY';
  if (errors.length > 0) {
    status = 'ERROR';
  }
  
  // Create the order object with appropriate status
  return {
    id: `ORD-${Date.now()}-${rowIndex}`,
    orderSide: row.orderSide ? String(row.orderSide).toUpperCase() : '',
    instrument: row.instrument || '',
    exchange: row.exchange || '',
    deskId: 0,
    quantity: parseFloat(row.quantity) || 0,
    currency: row.currency ? String(row.currency).toUpperCase() : '',
    price: parseFloat(row.price) || 0,
    orderType: row.orderType ? String(row.orderType).toUpperCase() : '',
    fillRate: parseFloat(row.fillRate) || 0,
    clOrderId: row.clOrderId || '',
    status: status,
    validationErrors: errors.join(', ')
  };
};

/**
 * Processes the entire CSV data
 */
export const processOrderCsvData = (parsedCsv: any): { 
  orders: any[];
  hasErrors: boolean;
} => {
  try {
    // Check if data is empty
    if (!parsedCsv.data || parsedCsv.data.length === 0) {
      return {
        orders: [],
        hasErrors: true
      };
    }
    
    let hasErrors = false;
    
    // Validate each row
    const orders = parsedCsv.data.map((row: any, index: number) => {
      const validatedOrder = validateOrderRow(row, index);
      if (validatedOrder.status === 'ERROR') {
        hasErrors = true;
      }
      return validatedOrder;
    });
    
    return {
      orders,
      hasErrors
    };
  } catch (error) {
    console.error("Error processing orders:", error);
    return {
      orders: [],
      hasErrors: true
    };
  }
};