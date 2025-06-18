// src/components/Simulator/ConvictionFileProcessor.ts
import { ConvictionModelConfig, ConvictionData } from '@trading-app/types-core';

export class ConvictionFileProcessor {
  constructor(
    private convictionSchema: ConvictionModelConfig | null,
    private addToast: (type: 'success' | 'error' | 'warning' | 'info', message: string, duration?: number, id?: string) => void
  ) {}

  // Generate expected columns based on conviction schema
  getExpectedColumns(): { required: string[], optional: string[] } {
    if (!this.convictionSchema) {
      return {
        required: ['instrumentId', 'convictionId'],
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

    required.push('participationRate', 'tag', 'convictionId');
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
        case 'convictionId': return 'conviction-001';
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

  // Get all valid column names (required + optional + multi-horizon)
  getAllValidColumns(): string[] {
    const { required, optional } = this.getExpectedColumns();
    const validColumns = [...required, ...optional];
    
    // Add multi-horizon columns if applicable
    if (this.convictionSchema?.portfolioApproach === 'incremental' && 
        this.convictionSchema?.incrementalConvictionMethod === 'multi-horizon') {
      const horizons = this.convictionSchema.horizons || [];
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
          
          validColumns.push(`z${value}${unitText}`);
        }
      });
    }
    
    return validColumns;
  }

  // Validate CSV structure with strict column checking
  validateCSVStructure(content: string): { isValid: boolean, errors: string[] } {
    const lines = content.trim().split('\n');
    const errors: string[] = [];
    
    if (lines.length === 0) {
      errors.push('CSV file is empty');
      return { isValid: false, errors };
    }

    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    const { required } = this.getExpectedColumns();
    const validColumns = this.getAllValidColumns().map(col => col.toLowerCase());
    
    console.log('[ConvictionFileProcessor] CSV validation:', {
      headerColumns: header,
      requiredColumns: required.map(col => col.toLowerCase()),
      validColumns: validColumns
    });
    
    // Check for required columns
    const missingRequired = required.filter(col => !header.includes(col.toLowerCase()));
    if (missingRequired.length > 0) {
      errors.push(`Missing required columns: ${missingRequired.join(', ')}`);
    }

    // Check for invalid columns (strict validation)
    const invalidColumns = header.filter(col => col && !validColumns.includes(col));
    if (invalidColumns.length > 0) {
      errors.push(`Invalid columns found: ${invalidColumns.join(', ')}. These columns are not supported by the current conviction schema.`);
      return { isValid: false, errors }; // REJECT the file immediately
    }

    return { 
      isValid: missingRequired.length === 0, 
      errors 
    };
  }

  // Validate individual conviction data
  validateConvictionData(conviction: ConvictionData, rowIndex: number): string[] {
    const errors: string[] = [];
    
    if (!this.convictionSchema) return errors;

    // Validate based on conviction schema
    if (this.convictionSchema.portfolioApproach === 'target') {
      if (this.convictionSchema.targetConvictionMethod === 'percent') {
        if (conviction.targetPercent === undefined) {
          errors.push(`Row ${rowIndex}: targetPercent is required`);
        } else if (Math.abs(conviction.targetPercent) > 100) {
          errors.push(`Row ${rowIndex}: targetPercent should be between -100 and 100`);
        }
      } else {
        if (conviction.targetNotional === undefined) {
          errors.push(`Row ${rowIndex}: targetNotional is required`);
        }
      }
    } else {
      // Incremental approach validation
      if (this.convictionSchema.incrementalConvictionMethod === 'side_score') {
        if (!conviction.side) {
          errors.push(`Row ${rowIndex}: side is required (BUY, SELL, or CLOSE)`);
        } else if (!['BUY', 'SELL', 'CLOSE'].includes(conviction.side)) {
          errors.push(`Row ${rowIndex}: side must be BUY, SELL, or CLOSE`);
        }
        
        if (conviction.score === undefined) {
          errors.push(`Row ${rowIndex}: score is required`);
        } else {
          const maxScore = this.convictionSchema.maxScore || 5;
          if (conviction.score < 1 || conviction.score > maxScore) {
            errors.push(`Row ${rowIndex}: score must be between 1 and ${maxScore}`);
          }
        }
      } else if (this.convictionSchema.incrementalConvictionMethod === 'side_qty') {
        if (!conviction.side || !['BUY', 'SELL', 'CLOSE'].includes(conviction.side)) {
          errors.push(`Row ${rowIndex}: side must be BUY, SELL, or CLOSE`);
        }
        if (!conviction.quantity || conviction.quantity <= 0) {
          errors.push(`Row ${rowIndex}: quantity must be a positive number`);
        }
      } else if (this.convictionSchema.incrementalConvictionMethod === 'zscore') {
        if (conviction.zscore === undefined) {
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
            if (conviction[colName] !== undefined) {
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
    if (conviction.participationRate && 
        !(['LOW', 'MEDIUM', 'HIGH'].includes(conviction.participationRate as string)) && 
        (typeof conviction.participationRate !== 'number' || conviction.participationRate < 0 || conviction.participationRate > 1)) {
      errors.push(`Row ${rowIndex}: participationRate must be LOW, MEDIUM, HIGH, or a decimal between 0 and 1`);
    }

    return errors;
  }

  // Process submit CSV with strict validation
  processSubmitCsv(content: string): ConvictionData[] {
    console.log('[ConvictionFileProcessor] Processing CSV content');
    
    // First validate structure with strict column checking
    const structureValidation = this.validateCSVStructure(content);
    
    console.log('[ConvictionFileProcessor] Structure validation:', structureValidation);
    
    // Show structure errors/warnings
    structureValidation.errors.forEach(error => {
      if (error.includes('Missing required') || error.includes('Invalid columns')) {
        this.addToast('error', error);
      } else {
        this.addToast('warning', error);
      }
    });

    if (!structureValidation.isValid) {
      console.log('[ConvictionFileProcessor] CSV structure validation failed, returning empty array');
      return [];
    }

    const lines = content.trim().split('\n');
    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    
    console.log('[ConvictionFileProcessor] Processing rows with valid structure');
    
    // Create column index mapping
    const columnMap: Record<string, number> = {};
    header.forEach((colName, index) => {
      columnMap[colName] = index;
    });

    const parsedConvictions: ConvictionData[] = [];
    const allValidationErrors: string[] = [];

    // Process data rows
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      if (values.length < header.length) {
        this.addToast('warning', `Row ${i+1}: insufficient columns, skipping`);
        continue;
      }

      // Build conviction object based on available columns
      const conviction: Partial<ConvictionData> = {};
      
      // Only map known valid columns
      header.forEach((colName, colIndex) => {
        const value = values[colIndex];
        if (!value) return;

        switch (colName) {
          case 'instrumentid':
            conviction.instrumentId = value;
            break;
          case 'convictionid':
            conviction.convictionId = value;
            break;
          case 'side':
            const side = value.toUpperCase();
            if (['BUY', 'SELL', 'CLOSE'].includes(side)) {
              conviction.side = side as 'BUY' | 'SELL' | 'CLOSE';
            }
            break;
          case 'quantity':
            const qty = parseFloat(value);
            if (!isNaN(qty)) conviction.quantity = qty;
            break;
          case 'score':
            const score = parseInt(value);
            if (!isNaN(score)) conviction.score = score;
            break;
          case 'zscore':
            const zscore = parseFloat(value);
            if (!isNaN(zscore)) conviction.zscore = zscore;
            break;
          case 'targetpercent':
            const targetPct = parseFloat(value);
            if (!isNaN(targetPct)) conviction.targetPercent = targetPct;
            break;
          case 'targetnotional':
            const targetNot = parseFloat(value);
            if (!isNaN(targetNot)) conviction.targetNotional = targetNot;
            break;
          case 'participationrate':
            // FIXED: Handle both string and number participation rates properly
            const upperValue = value.toUpperCase();
            if (['LOW', 'MEDIUM', 'HIGH'].includes(upperValue)) {
              conviction.participationRate = upperValue as 'LOW' | 'MEDIUM' | 'HIGH';
            } else {
              const numericRate = parseFloat(value);
              if (!isNaN(numericRate) && numericRate >= 0 && numericRate <= 1) {
                // Convert numeric rate to string equivalent for type safety
                if (numericRate <= 0.33) {
                  conviction.participationRate = 'LOW';
                } else if (numericRate <= 0.66) {
                  conviction.participationRate = 'MEDIUM';
                } else {
                  conviction.participationRate = 'HIGH';
                }
              }
            }
            break;
          case 'tag':
            conviction.tag = value;
            break;
          default:
            // Handle multi-horizon columns ONLY
            if (colName.startsWith('z') && (colName.includes('min') || colName.includes('hour') || colName.includes('day') || colName.includes('week'))) {
              const zValue = parseFloat(value);
              if (!isNaN(zValue)) {
                conviction[colName] = zValue;
              }
            }
            // NOTE: Unknown columns are now rejected at validation stage, so we shouldn't reach here
            break;
        }
      });

      // Validate the conviction data
      const convictionErrors = this.validateConvictionData(conviction as ConvictionData, i + 1);
      if (convictionErrors.length > 0) {
        allValidationErrors.push(...convictionErrors);
        continue; // Skip invalid convictions
      }

      parsedConvictions.push(conviction as ConvictionData);
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

    console.log('[ConvictionFileProcessor] Final parsed convictions:', {
      count: parsedConvictions.length,
      validationErrors: allValidationErrors.length
    });

    return parsedConvictions;
  }

  // Process cancel CSV (unchanged)
  processCancelCsv(content: string): ConvictionData[] {
    const lines = content.trim().split('\n');
    if (lines.length === 0) return [];

    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    
    if (!header.includes('convictionid')) {
      this.addToast('error', 'CSV is missing required column: convictionId');
      return [];
    }

    const convictionIdIndex = header.indexOf('convictionid');
    const parsedConvictions: ConvictionData[] = [];
    
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      if (values.length <= convictionIdIndex) {
        this.addToast('warning', `Row ${i+1}: missing convictionId, skipping`);
        continue;
      }

      const convictionId = values[convictionIdIndex];
      if (!convictionId) {
        this.addToast('warning', `Row ${i+1}: empty convictionId, skipping`);
        continue;
      }

      parsedConvictions.push({ convictionId } as ConvictionData);
    }

    return parsedConvictions;
  }
}

export default ConvictionFileProcessor;