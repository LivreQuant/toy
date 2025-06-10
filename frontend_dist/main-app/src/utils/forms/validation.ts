// src/utils/forms/validation.ts
export type ValidationRule<T = any> = (value: T, formData?: any) => string | null;

export const validationRules = {
  required: (message = 'This field is required'): ValidationRule => (value: any) =>
    value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
      ? message
      : null,

  minLength: (min: number, message?: string): ValidationRule<string> => (value: string) =>
    value && value.length < min
      ? message || `Must be at least ${min} characters`
      : null,

  maxLength: (max: number, message?: string): ValidationRule<string> => (value: string) =>
    value && value.length > max
      ? message || `Must be no more than ${max} characters`
      : null,

  email: (message = 'Please enter a valid email address'): ValidationRule<string> => (value: string) =>
    value && !/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(value)
      ? message
      : null,

  url: (message = 'Please enter a valid URL'): ValidationRule<string> => (value: string) =>
    value && !/^https?:\/\/.+/.test(value)
      ? message
      : null,

  number: (message = 'Please enter a valid number'): ValidationRule => (value: any) =>
    value !== '' && value !== null && value !== undefined && isNaN(Number(value))
      ? message
      : null,

  min: (min: number, message?: string): ValidationRule<number> => (value: number) =>
    value < min
      ? message || `Must be at least ${min}`
      : null,

  max: (max: number, message?: string): ValidationRule<number> => (value: number) =>
    value > max
      ? message || `Must be no more than ${max}`
      : null,

  pattern: (regex: RegExp, message: string): ValidationRule<string> => (value: string) =>
    value && !regex.test(value)
      ? message
      : null,

  arrayMinLength: (min: number, message?: string): ValidationRule<any[]> => (value: any[]) =>
    !Array.isArray(value) || value.length < min
      ? message || `Please select at least ${min} option${min > 1 ? 's' : ''}`
      : null,

  arrayMaxLength: (max: number, message?: string): ValidationRule<any[]> => (value: any[]) =>
    Array.isArray(value) && value.length > max
      ? message || `Please select no more than ${max} option${max > 1 ? 's' : ''}`
      : null,

  custom: <T>(validator: (value: T, formData?: any) => string | null): ValidationRule<T> => validator
};

export const combineValidators = (...validators: Array<ValidationRule>): ValidationRule =>
  (value: any, formData?: any) => {
    for (const validator of validators) {
      const error = validator(value, formData);
      if (error) return error;
    }
    return null;
  };