// src/hooks/forms/useFormValidation.ts
import { useState, useCallback } from 'react';

type ValidationRule<T> = {
  field: keyof T;
  validate: (value: any, formData: T) => string | null;
  message: string;
};

export interface UseFormValidationProps<T> {
  initialData: T;
  validationRules: ValidationRule<T>[];
}

export function useFormValidation<T extends Record<string, any>>({
  initialData,
  validationRules
}: UseFormValidationProps<T>) {
  const [formData, setFormData] = useState<T>(initialData);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});

  const validateField = useCallback((field: keyof T, value: any): string | null => {
    const rule = validationRules.find(r => r.field === field);
    if (!rule) return null;
    
    return rule.validate(value, formData);
  }, [validationRules, formData]);

  const validateForm = useCallback((): boolean => {
    const newErrors: Partial<Record<keyof T, string>> = {};
    let isValid = true;

    for (const rule of validationRules) {
      const error = rule.validate(formData[rule.field], formData);
      if (error) {
        newErrors[rule.field] = error;
        isValid = false;
      }
    }

    setErrors(newErrors);
    return isValid;
  }, [formData, validationRules]);

  const updateField = useCallback((field: keyof T, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when field is updated
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  }, [errors]);

  const updateFields = useCallback((updates: Partial<T>) => {
    setFormData(prev => ({ ...prev, ...updates }));
    
    // Clear errors for updated fields
    const updatedFields = Object.keys(updates) as Array<keyof T>;
    setErrors(prev => {
      const newErrors = { ...prev };
      updatedFields.forEach(field => {
        delete newErrors[field];
      });
      return newErrors;
    });
  }, []);

  return {
    formData,
    errors,
    validateField,
    validateForm,
    updateField,
    updateFields,
    setErrors
  };
}