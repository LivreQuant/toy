// src/components/Form/FormWizard/useFormWizard.ts
import { useState, useCallback, useMemo } from 'react';

interface FormWizardStep {
  label: string;
  validate?: () => boolean | Promise<boolean>;
  onEnter?: () => void;
  onExit?: () => void;
}

interface UseFormWizardProps {
  steps: FormWizardStep[];
  initialStep?: number;
  onStepChange?: (step: number) => void;
}

export const useFormWizard = ({
  steps,
  initialStep = 0,
  onStepChange
}: UseFormWizardProps) => {
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [completed, setCompleted] = useState<boolean[]>(new Array(steps.length).fill(false));
  const [errors, setErrors] = useState<Record<number, string>>({});

  const goToStep = useCallback(async (stepIndex: number) => {
    if (stepIndex < 0 || stepIndex >= steps.length) return false;

    // Call onExit for current step
    const currentStepConfig = steps[currentStep];
    if (currentStepConfig?.onExit) {
      currentStepConfig.onExit();
    }

    setCurrentStep(stepIndex);
    onStepChange?.(stepIndex);

    // Call onEnter for new step
    const newStepConfig = steps[stepIndex];
    if (newStepConfig?.onEnter) {
      newStepConfig.onEnter();
    }

    return true;
  }, [currentStep, steps, onStepChange]);

  const nextStep = useCallback(async () => {
    const currentStepConfig = steps[currentStep];
    
    // Validate current step if validation exists
    if (currentStepConfig?.validate) {
      try {
        const isValid = await currentStepConfig.validate();
        if (!isValid) {
          setErrors(prev => ({ ...prev, [currentStep]: 'Validation failed' }));
          return false;
        }
      } catch (error: any) {
        setErrors(prev => ({ ...prev, [currentStep]: error.message || 'Validation error' }));
        return false;
      }
    }

    // Clear any errors for this step
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[currentStep];
      return newErrors;
    });

    // Mark current step as completed
    setCompleted(prev => {
      const newCompleted = [...prev];
      newCompleted[currentStep] = true;
      return newCompleted;
    });

    // Move to next step
    if (currentStep < steps.length - 1) {
      return goToStep(currentStep + 1);
    }

    return true;
  }, [currentStep, steps, goToStep]);

  const previousStep = useCallback(() => {
    if (currentStep > 0) {
      return goToStep(currentStep - 1);
    }
    return false;
  }, [currentStep, goToStep]);

  const resetWizard = useCallback(() => {
    setCurrentStep(initialStep);
    setCompleted(new Array(steps.length).fill(false));
    setErrors({});
  }, [initialStep, steps.length]);

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const canGoNext = !errors[currentStep];
  const canGoPrevious = !isFirstStep;

  return useMemo(() => ({
    currentStep,
    completed,
    errors,
    isFirstStep,
    isLastStep,
    canGoNext,
    canGoPrevious,
    nextStep,
    previousStep,
    goToStep,
    resetWizard,
    stepLabels: steps.map(step => step.label)
  }), [
    currentStep,
    completed,
    errors,
    isFirstStep,
    isLastStep,
    canGoNext,
    canGoPrevious,
    nextStep,
    previousStep,
    goToStep,
    resetWizard,
    steps
  ]);
};