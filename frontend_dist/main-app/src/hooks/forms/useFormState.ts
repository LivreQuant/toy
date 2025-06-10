// src/hooks/forms/useFormState.ts
import { useState, useCallback, useRef, useEffect } from 'react';

export interface UseFormStateProps<T> {
  initialData: T;
  autoSave?: boolean;
  autoSaveDelay?: number;
  storageKey?: string;
  onDataChange?: (data: T) => void;
}

export const useFormState = <T extends Record<string, any>>({
  initialData,
  autoSave = false,
  autoSaveDelay = 1000,
  storageKey,
  onDataChange
}: UseFormStateProps<T>) => {
  // Try to load from localStorage if storageKey is provided
  const [formData, setFormData] = useState<T>(() => {
    if (storageKey && typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
          return { ...initialData, ...JSON.parse(saved) };
        }
      } catch (error) {
        console.warn('Failed to load form data from localStorage:', error);
      }
    }
    return initialData;
  });

  const [isDirty, setIsDirty] = useState(false);
  const [isAutoSaving, setIsAutoSaving] = useState(false);
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout>();

  // Auto-save to localStorage
  const saveToStorage = useCallback(() => {
    if (storageKey && typeof window !== 'undefined') {
      try {
        localStorage.setItem(storageKey, JSON.stringify(formData));
        setIsAutoSaving(false);
      } catch (error) {
        console.warn('Failed to save form data to localStorage:', error);
        setIsAutoSaving(false);
      }
    }
  }, [formData, storageKey]);

  // Auto-save effect
  useEffect(() => {
    if (autoSave && isDirty) {
      setIsAutoSaving(true);
      
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current);
      }
      
      autoSaveTimeoutRef.current = setTimeout(() => {
        saveToStorage();
      }, autoSaveDelay);
    }

    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current);
      }
    };
  }, [formData, isDirty, autoSave, autoSaveDelay, saveToStorage]);

  const updateField = useCallback(<K extends keyof T>(field: K, value: T[K]) => {
    setFormData(prev => {
      const newData = { ...prev, [field]: value };
      onDataChange?.(newData);
      return newData;
    });
    setIsDirty(true);
  }, [onDataChange]);

  const updateFields = useCallback((updates: Partial<T>) => {
    setFormData(prev => {
      const newData = { ...prev, ...updates };
      onDataChange?.(newData);
      return newData;
    });
    setIsDirty(true);
  }, [onDataChange]);

  const resetForm = useCallback(() => {
    setFormData(initialData);
    setIsDirty(false);
    setIsAutoSaving(false);
    
    // Clear from localStorage
    if (storageKey && typeof window !== 'undefined') {
      localStorage.removeItem(storageKey);
    }
  }, [initialData, storageKey]);

  const saveManually = useCallback(() => {
    saveToStorage();
    setIsDirty(false);
  }, [saveToStorage]);

  return {
    formData,
    isDirty,
    isAutoSaving,
    updateField,
    updateFields,
    resetForm,
    saveManually,
    setFormData
  };
};