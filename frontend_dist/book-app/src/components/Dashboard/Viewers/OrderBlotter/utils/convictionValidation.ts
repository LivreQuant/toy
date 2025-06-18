// src/components/Dashboard/Viewers/OrderBlotter/utils/convictionValidation.ts

// Valid values for conviction fields
const VALID_SIDES = ['BUY', 'SELL', 'CLOSE'];
const VALID_PARTICIPATION_RATES = ['LOW', 'MEDIUM', 'HIGH'];

export const validateConvictionRow = (row: any, rowIndex: number): any => {
  const errors: string[] = [];
  
  // Validate required fields
  if (!row.convictionId) {
    errors.push(`Conviction ID is required`);
  }
  
  if (!row.instrumentId) {
    errors.push(`Instrument ID is required`);
  }
  
  // Validate side if present
  if (row.side && !VALID_SIDES.includes(String(row.side).toUpperCase())) {
    errors.push(`Side must be one of: ${VALID_SIDES.join(', ')}`);
  }
  
  // Validate score if present
  if (row.score !== undefined) {
    const score = parseInt(row.score);
    if (isNaN(score) || score < 1) {
      errors.push(`Score must be a positive integer`);
    }
  }
  
  // Validate quantity if present
  if (row.quantity !== undefined) {
    const quantity = parseFloat(row.quantity);
    if (isNaN(quantity) || quantity <= 0) {
      errors.push(`Quantity must be a positive number`);
    }
  }
  
  // Validate zscore if present
  if (row.zscore !== undefined) {
    const zscore = parseFloat(row.zscore);
    if (isNaN(zscore)) {
      errors.push(`Z-score must be a valid number`);
    }
  }
  
  // Validate target percent if present
  if (row.targetPercent !== undefined) {
    const targetPercent = parseFloat(row.targetPercent);
    if (isNaN(targetPercent) || Math.abs(targetPercent) > 100) {
      errors.push(`Target percent must be between -100 and 100`);
    }
  }
  
  // Validate target notional if present
  if (row.targetNotional !== undefined) {
    const targetNotional = parseFloat(row.targetNotional);
    if (isNaN(targetNotional)) {
      errors.push(`Target notional must be a valid number`);
    }
  }
  
  // Validate participation rate if present
  if (row.participationRate) {
    const rate = String(row.participationRate).toUpperCase();
    if (!VALID_PARTICIPATION_RATES.includes(rate)) {
      const numericRate = parseFloat(row.participationRate);
      if (isNaN(numericRate) || numericRate < 0 || numericRate > 1) {
        errors.push(`Participation rate must be LOW, MEDIUM, HIGH, or a decimal between 0 and 1`);
      }
    }
  }
  
  // Determine status
  let status = 'READY';
  if (errors.length > 0) {
    status = 'ERROR';
  }
  
  // Create the conviction object
  return {
    id: `CONV-${Date.now()}-${rowIndex}`,
    convictionId: row.convictionId || '',
    instrumentId: row.instrumentId || '',
    side: row.side ? String(row.side).toUpperCase() : undefined,
    quantity: row.quantity ? parseFloat(row.quantity) : undefined,
    score: row.score ? parseInt(row.score) : undefined,
    zscore: row.zscore ? parseFloat(row.zscore) : undefined,
    targetPercent: row.targetPercent ? parseFloat(row.targetPercent) : undefined,
    targetNotional: row.targetNotional ? parseFloat(row.targetNotional) : undefined,
    participationRate: row.participationRate ? (
      VALID_PARTICIPATION_RATES.includes(String(row.participationRate).toUpperCase()) 
        ? String(row.participationRate).toUpperCase()
        : parseFloat(row.participationRate)
    ) : undefined,
    tag: row.tag || undefined,
    status: status,
    validationErrors: errors.join(', '),
    
    // Include any multi-horizon z-scores
    ...Object.keys(row).reduce((acc, key) => {
      if (key.startsWith('z') && (key.includes('min') || key.includes('hour') || key.includes('day') || key.includes('week'))) {
        const value = parseFloat(row[key]);
        if (!isNaN(value)) {
          acc[key] = value;
        }
      }
      return acc;
    }, {} as Record<string, any>)
  };
};

export const processConvictionCsvData = (parsedCsv: any): { 
  convictions: any[];
  hasErrors: boolean;
} => {
  try {
    if (!parsedCsv.data || parsedCsv.data.length === 0) {
      return {
        convictions: [],
        hasErrors: true
      };
    }
    
    let hasErrors = false;
    
    const convictions = parsedCsv.data.map((row: any, index: number) => {
      const validatedConviction = validateConvictionRow(row, index);
      if (validatedConviction.status === 'ERROR') {
        hasErrors = true;
      }
      return validatedConviction;
    });
    
    return {
      convictions,
      hasErrors
    };
  } catch (error) {
    console.error("Error processing convictions:", error);
    return {
      convictions: [],
      hasErrors: true
    };
  }
};

// Keep the old exports for backward compatibility
export const validateOrderRow = validateConvictionRow;
export const processOrderCsvData = processConvictionCsvData;