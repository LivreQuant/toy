// src/utils/forms/formHelpers.ts (fix the Date check)
export const formHelpers = {
    // Deep clone form data
    cloneDeep: <T>(obj: T): T => {
      if (obj === null || typeof obj !== 'object') return obj;
      if (obj instanceof Date) return new Date(obj.getTime()) as any;
      if (Array.isArray(obj)) return obj.map(item => formHelpers.cloneDeep(item)) as any;
      
      const cloned = {} as T;
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          cloned[key] = formHelpers.cloneDeep(obj[key]);
        }
      }
      return cloned;
    },
  
    // Get nested value from object using dot notation
    getNestedValue: (obj: any, path: string): any => {
      return path.split('.').reduce((current, key) => current?.[key], obj);
    },
  
    // Set nested value in object using dot notation
    setNestedValue: (obj: any, path: string, value: any): any => {
      const keys = path.split('.');
      const lastKey = keys.pop();
      if (!lastKey) return obj;
  
      const target = keys.reduce((current, key) => {
        if (!(key in current)) current[key] = {};
        return current[key];
      }, obj);
  
      target[lastKey] = value;
      return obj;
    },
  
    // Check if form data has changed
    hasChanged: <T>(original: T, current: T): boolean => {
      return JSON.stringify(original) !== JSON.stringify(current);
    },
  
    // Get only changed fields
    getChangedFields: <T extends Record<string, any>>(original: T, current: T): Partial<T> => {
      const changed: Partial<T> = {};
      
      for (const key in current) {
        if (JSON.stringify(original[key]) !== JSON.stringify(current[key])) {
          changed[key] = current[key];
        }
      }
      
      return changed;
    },
  
    // Flatten nested object for form submission
    flattenObject: (obj: any, prefix = ''): Record<string, any> => {
      const flattened: Record<string, any> = {};
      
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          const value = obj[key];
          const newKey = prefix ? `${prefix}.${key}` : key;
          
          if (value !== null && typeof value === 'object' && !Array.isArray(value) && !formHelpers.isDate(value)) {
            Object.assign(flattened, formHelpers.flattenObject(value, newKey));
          } else {
            flattened[newKey] = value;
          }
        }
      }
      
      return flattened;
    },
  
    // Unflatten object from dot notation keys
    unflattenObject: (obj: Record<string, any>): any => {
      const result: any = {};
      
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          formHelpers.setNestedValue(result, key, obj[key]);
        }
      }
      
      return result;
    },
  
    // Helper function to check if value is a Date
    isDate: (value: any): value is Date => {
      return Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value.getTime());
    },
  
    // Sanitize form data (remove empty strings, null values, etc.)
    sanitizeFormData: <T extends Record<string, any>>(data: T, options: {
      removeEmptyStrings?: boolean;
      removeNull?: boolean;
      removeUndefined?: boolean;
      removeEmptyArrays?: boolean;
      removeEmptyObjects?: boolean;
    } = {}): Partial<T> => {
      const {
        removeEmptyStrings = true,
        removeNull = true,
        removeUndefined = true,
        removeEmptyArrays = true,
        removeEmptyObjects = true
      } = options;
  
      const sanitized: any = {};
  
      for (const key in data) {
        if (data.hasOwnProperty(key)) {
          const value = data[key];
  
          // Skip based on options
          if (removeUndefined && value === undefined) continue;
          if (removeNull && value === null) continue;
          if (removeEmptyStrings && value === '') continue;
          if (removeEmptyArrays && Array.isArray(value) && value.length === 0) continue;
          if (removeEmptyObjects && typeof value === 'object' && value !== null && !Array.isArray(value) && Object.keys(value).length === 0) continue;
  
          // Recursively sanitize nested objects
          // Use the helper function to check for dates
          if (typeof value === 'object' && value !== null && !Array.isArray(value) && !formHelpers.isDate(value)) {
            const sanitizedNested = formHelpers.sanitizeFormData(value, options);
            if (Object.keys(sanitizedNested).length > 0 || !removeEmptyObjects) {
              sanitized[key] = sanitizedNested;
            }
          } else {
            sanitized[key] = value;
          }
        }
      }
  
      return sanitized;
    },
  
    // Convert form data to FormData for file uploads
    toFormData: (data: Record<string, any>, formData = new FormData(), parentKey = ''): FormData => {
      for (const key in data) {
        if (data.hasOwnProperty(key)) {
          const value = data[key];
          const formKey = parentKey ? `${parentKey}[${key}]` : key;
  
          if (value instanceof File) {
            formData.append(formKey, value);
          } else if (Array.isArray(value)) {
            value.forEach((item, index) => {
              if (item instanceof File) {
                formData.append(`${formKey}[${index}]`, item);
              } else if (typeof item === 'object' && item !== null) {
                formHelpers.toFormData({ [index]: item }, formData, formKey);
              } else {
                formData.append(`${formKey}[${index}]`, String(item));
              }
            });
          } else if (typeof value === 'object' && value !== null && !formHelpers.isDate(value)) {
            formHelpers.toFormData(value, formData, formKey);
          } else if (value !== null && value !== undefined) {
            formData.append(formKey, String(value));
          }
        }
      }
  
      return formData;
    },
  
    // Debounce function for form validation
    debounce: <T extends (...args: any[]) => any>(
      func: T,
      wait: number
    ): ((...args: Parameters<T>) => void) => {
      let timeout: NodeJS.Timeout;
      
      return (...args: Parameters<T>) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
      };
    },
  
    // Format currency values
    formatCurrency: (value: number, currency = 'USD', locale = 'en-US'): string => {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency
      }).format(value);
    },
  
    // Parse currency string to number
    parseCurrency: (value: string): number => {
      return parseFloat(value.replace(/[^\d.-]/g, '')) || 0;
    },
  
    // Generate unique IDs for form fields
    generateId: (): string => {
      return `form-field-${Math.random().toString(36).substr(2, 9)}`;
    },
  
    // Validate file types and sizes
    validateFile: (
      file: File,
      options: {
        maxSize?: number; // in bytes
        allowedTypes?: string[];
        allowedExtensions?: string[];
      } = {}
    ): string | null => {
      const { maxSize, allowedTypes, allowedExtensions } = options;
  
      if (maxSize && file.size > maxSize) {
        const maxSizeMB = (maxSize / 1024 / 1024).toFixed(1);
        return `File size must be less than ${maxSizeMB}MB`;
      }
  
      if (allowedTypes && !allowedTypes.includes(file.type)) {
        return `File type ${file.type} is not allowed`;
      }
  
      if (allowedExtensions) {
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (!extension || !allowedExtensions.includes(extension)) {
          return `File extension must be one of: ${allowedExtensions.join(', ')}`;
        }
      }
  
      return null;
    }
  };
  
  // Export individual functions for easier importing
  export const {
    cloneDeep,
    getNestedValue,
    setNestedValue,
    hasChanged,
    getChangedFields,
    flattenObject,
    unflattenObject,
    sanitizeFormData,
    toFormData,
    debounce,
    formatCurrency,
    parseCurrency,
    generateId,
    validateFile,
    isDate
  } = formHelpers;