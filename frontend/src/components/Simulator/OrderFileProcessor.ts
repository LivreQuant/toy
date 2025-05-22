// src/components/Simulator/OrderFileProcessor.ts
import { ConvictionModelConfig, OrderData } from '../../types';


export class OrderFileProcessor {
  constructor(
    private convictionSchema: ConvictionModelConfig | null,
    private addToast: (type: 'success' | 'error' | 'warning' | 'info', message: string, duration?: number, id?: string) => void
  ) {}

  // Generate expected columns based on conviction schema
  getExpectedColumns(): { required: string[], optional: string[] } {
    if (!this.convictionSchema) {
      return {
        required: ['instrumentId', 'orderId'],
        optional: ['participationRate', 'tag']
      };
    }

    const required = ['instrumentId'];
    const optional: string[] = [];

    if (this.convictionSchema.portfolioApproach === 'target') {
      if (this.convictionSchema.targetConvictionMethod === 'percent') {
        required.push('targetPercent');
      } else {
        required.push('targetNotional');
      }
    } else {
      if (this.convictionSchema.incrementalConvictionMethod === 'side_score') {
        required.push('side', 'score');
      } else if (this.convictionSchema.incrementalConvictionMethod === 'side_qty') {
        required.push('side', 'quantity');
      } else if (this.convictionSchema.incrementalConvictionMethod === 'zscore') {
        required.push('zscore');
      } else if (this.convictionSchema.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = this.convictionSchema.horizons || ['1d', '5d', '20d'];
        horizons.forEach(horizon => {
          const match = horizon.match(/(\d+)([mhdw])/);
          if (match) {
            const [_, value, unit] = match;
            let unitText = unit;
            
            switch(unit) {
              case 'm': unitText = 'min'; break;
              case 'h': unitText = 'hour'; break;
              case 'd': unitText = 'day'; break;
              case 'w': unitText = 'week'; break;
            }
            
            required.push(`z${value}${unitText}`);
          }
        });
      }
    }

    required.push('participationRate', 'tag', 'orderId');
    return { required, optional };
  }

  // Generate sample CSV format
  getSampleFormat(): string {
    const { required } = this.getExpectedColumns();
    const sampleValues = required.map(col => {
      switch (col) {
        case 'instrumentId': return 'AAPL.US';
        case 'side': return 'BUY';
        case 'score': return (this.convictionSchema?.maxScore || 5).toString();
        case 'quantity': return '1000';
        case 'zscore': return '1.5';
        case 'targetPercent': return '2.5';
        case 'targetNotional': return '250000';
        case 'participationRate': return 'MEDIUM';
        case 'tag': return 'value';
        case 'orderId': return 'order-001';
        default:
          // Handle multi-horizon zscore columns
          if (col.startsWith('z') && (col.includes('min') || col.includes('hour') || col.includes('day') || col.includes('week'))) {
            return (Math.random() * 4 - 2).toFixed(2);
          }
          return 'value';
      }
    });

    return `${required.join(',')}\n${sampleValues.join(',')}`;
  }

  // Validate CSV structure
  validateCSVStructure(content: string): { isValid: boolean, errors: string[] } {
    const lines = content.trim().split('\n');
    const errors: string[] = [];
    
    if (lines.length === 0) {
      errors.push('CSV file is empty');
      return { isValid: false, errors };
    }

    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    const { required, optional } = this.getExpectedColumns();
    
    // Check for required columns
    const missingRequired = required.filter(col => !header.includes(col.toLowerCase()));
    if (missingRequired.length > 0) {
      errors.push(`Missing required columns: ${missingRequired.join(', ')}`);
    }

    // Check for unexpected columns (warn but don't fail)
    const expectedColumns = [...required, ...optional].map(col => col.toLowerCase());
    const unexpectedColumns = header.filter(col => !expectedColumns.includes(col));
    if (unexpectedColumns.length > 0) {
      errors.push(`Unexpected columns (will be ignored): ${unexpectedColumns.join(', ')}`);
    }

    return { 
      isValid: missingRequired.length === 0, 
      errors 
    };
  }

  // Validate individual order data
  validateOrderData(order: OrderData, rowIndex: number): string[] {
    const errors: string[] = [];
    
    if (!this.convictionSchema) return errors;

    // Validate based on conviction schema
    if (this.convictionSchema.portfolioApproach === 'target') {
      if (this.convictionSchema.targetConvictionMethod === 'percent') {
        if (order.targetPercent === undefined) {
          errors.push(`Row ${rowIndex}: targetPercent is required`);
        } else if (Math.abs(order.targetPercent) > 100) {
          errors.push(`Row ${rowIndex}: targetPercent should be between -100 and 100`);
        }
      } else {
        if (order.targetNotional === undefined) {
          errors.push(`Row ${rowIndex}: targetNotional is required`);
        }
      }
    } else {
      // Incremental approach validation
      if (this.convictionSchema.incrementalConvictionMethod === 'side_score') {
        if (!order.side) {
          errors.push(`Row ${rowIndex}: side is required (BUY, SELL, or CLOSE)`);
        } else if (!['BUY', 'SELL', 'CLOSE'].includes(order.side)) {
          errors.push(`Row ${rowIndex}: side must be BUY, SELL, or CLOSE`);
        }
        
        if (order.score === undefined) {
          errors.push(`Row ${rowIndex}: score is required`);
        } else {
          const maxScore = this.convictionSchema.maxScore || 5;
          if (order.score < 1 || order.score > maxScore) {
            errors.push(`Row ${rowIndex}: score must be between 1 and ${maxScore}`);
          }
        }
      } else if (this.convictionSchema.incrementalConvictionMethod === 'side_qty') {
        if (!order.side || !['BUY', 'SELL', 'CLOSE'].includes(order.side)) {
          errors.push(`Row ${rowIndex}: side must be BUY, SELL, or CLOSE`);
        }
        if (!order.quantity || order.quantity <= 0) {
          errors.push(`Row ${rowIndex}: quantity must be a positive number`);
        }
      } else if (this.convictionSchema.incrementalConvictionMethod === 'zscore') {
        if (order.zscore === undefined) {
          errors.push(`Row ${rowIndex}: zscore is required`);
        }
      } else if (this.convictionSchema.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = this.convictionSchema.horizons || [];
        let hasAnyZScore = false;
        
        horizons.forEach(horizon => {
          const match = horizon.match(/(\d+)([mhdw])/);
          if (match) {
            const [_, value, unit] = match;
            let unitText = unit;
            
            switch(unit) {
              case 'm': unitText = 'min'; break;
              case 'h': unitText = 'hour'; break;
              case 'd': unitText = 'day'; break;
              case 'w': unitText = 'week'; break;
            }
            
            const colName = `z${value}${unitText}`;
            if (order[colName] !== undefined) {
              hasAnyZScore = true;
            }
          }
        });
        
        if (!hasAnyZScore) {
          errors.push(`Row ${rowIndex}: at least one z-score column is required`);
        }
      }
    }

    // Validate common fields
    if (order.participationRate && 
        !(['LOW', 'MEDIUM', 'HIGH'].includes(order.participationRate as string)) && 
        (typeof order.participationRate !== 'number' || order.participationRate < 0 || order.participationRate > 1)) {
      errors.push(`Row ${rowIndex}: participationRate must be LOW, MEDIUM, HIGH, or a decimal between 0 and 1`);
    }

    return errors;
  }

  // Process submit CSV
  processSubmitCsv(content: string): OrderData[] {
    // First validate structure
    const structureValidation = this.validateCSVStructure(content);
    
    // Show structure errors/warnings
    structureValidation.errors.forEach(error => {
      if (error.includes('Missing required')) {
        this.addToast('error', error);
      } else {
        this.addToast('warning', error);
      }
    });

    if (!structureValidation.isValid) {
      return [];
    }

    const lines = content.trim().split('\n');
    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    
    // Create column index mapping
    const columnMap: Record<string, number> = {};
    header.forEach((colName, index) => {
      columnMap[colName] = index;
    });

    const parsedOrders: OrderData[] = [];
    const allValidationErrors: string[] = [];

    // Process data rows
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      if (values.length < header.length) {
        this.addToast('warning', `Row ${i+1}: insufficient columns, skipping`);
        continue;
      }

      // Build order object based on available columns
      const order: Partial<OrderData> = {}; // Use Partial<OrderData> to allow empty initialization
      
      // Map all available columns
      header.forEach((colName, colIndex) => {
        const value = values[colIndex];
        if (!value) return;

        switch (colName) {
          case 'instrumentid':
            order.instrumentId = value;
            break;
          case 'orderid':
            order.orderId = value;
            break;
          case 'side':
            const side = value.toUpperCase();
            if (['BUY', 'SELL', 'CLOSE'].includes(side)) {
              order.side = side as 'BUY' | 'SELL' | 'CLOSE';
            }
            break;
          case 'quantity':
            const qty = parseFloat(value);
            if (!isNaN(qty)) order.quantity = qty;
            break;
          case 'score':
            const score = parseInt(value);
            if (!isNaN(score)) order.score = score;
            break;
          case 'zscore':
            const zscore = parseFloat(value);
            if (!isNaN(zscore)) order.zscore = zscore;
            break;
          case 'targetpercent':
            const targetPct = parseFloat(value);
            if (!isNaN(targetPct)) order.targetPercent = targetPct;
            break;
          case 'targetnotional':
            const targetNot = parseFloat(value);
            if (!isNaN(targetNot)) order.targetNotional = targetNot;
            break;
          case 'participationrate':
            if (['LOW', 'MEDIUM', 'HIGH'].includes(value.toUpperCase())) {
              order.participationRate = value.toUpperCase() as 'LOW' | 'MEDIUM' | 'HIGH';
            } else {
              const rate = parseFloat(value);
              if (!isNaN(rate)) order.participationRate = rate;
            }
            break;
          case 'tag':
            order.tag = value;
            break;
          default:
            // Handle multi-horizon columns
            if (colName.startsWith('z') && (colName.includes('min') || colName.includes('hour') || colName.includes('day') || colName.includes('week'))) {
              const zValue = parseFloat(value);
              if (!isNaN(zValue)) {
                order[colName] = zValue;
              }
            }
            break;
        }
      });

      // Validate the order data
      const orderErrors = this.validateOrderData(order as OrderData, i + 1);
      if (orderErrors.length > 0) {
        allValidationErrors.push(...orderErrors);
        continue; // Skip invalid orders
      }

      parsedOrders.push(order as OrderData);
    }

    // Show validation errors
    if (allValidationErrors.length > 0) {
      // Show first few errors
      allValidationErrors.slice(0, 5).forEach(error => {
        this.addToast('error', error);
      });
      
      if (allValidationErrors.length > 5) {
        this.addToast('warning', `${allValidationErrors.length - 5} additional validation errors not shown`);
      }
    }

    return parsedOrders;
  }

  // Process cancel CSV
  processCancelCsv(content: string): OrderData[] {
    const lines = content.trim().split('\n');
    if (lines.length === 0) return [];

    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    
    if (!header.includes('orderid')) {
      this.addToast('error', 'CSV is missing required column: orderId');
      return [];
    }

    const orderIdIndex = header.indexOf('orderid');
    const parsedOrders: OrderData[] = [];
    
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      if (values.length <= orderIdIndex) {
        this.addToast('warning', `Row ${i+1}: missing orderId, skipping`);
        continue;
      }

      const orderId = values[orderIdIndex];
      if (!orderId) {
        this.addToast('warning', `Row ${i+1}: empty orderId, skipping`);
        continue;
      }

      parsedOrders.push({ orderId } as OrderData);
    }

    return parsedOrders;
  }
}

export default OrderFileProcessor;