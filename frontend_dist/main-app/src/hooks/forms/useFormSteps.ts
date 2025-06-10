// src/hooks/forms/useFormSteps.ts
import { useState, useCallback } from 'react';

export interface UseFormStepsProps {
  totalSteps: number;
  initialStep?: number;
  onStepChange?: (step: number) => void;
}

export const useFormSteps = ({
  totalSteps,
  initialStep = 0,
  onStepChange
}: UseFormStepsProps) => {
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [visitedSteps, setVisitedSteps] = useState<Set<number>>(new Set([initialStep]));

  const goToStep = useCallback((step: number) => {
    if (step >= 0 && step < totalSteps) {
      setCurrentStep(step);
      setVisitedSteps(prev => new Set([...prev, step]));
      onStepChange?.(step);
      return true;
    }
    return false;
  }, [totalSteps, onStepChange]);

  const nextStep = useCallback(() => {
    return goToStep(currentStep + 1);
  }, [currentStep, goToStep]);

  const previousStep = useCallback(() => {
    return goToStep(currentStep - 1);
  }, [currentStep, goToStep]);

  const resetSteps = useCallback(() => {
    setCurrentStep(initialStep);
    setVisitedSteps(new Set([initialStep]));
  }, [initialStep]);

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const hasVisitedStep = (step: number) => visitedSteps.has(step);

  return {
    currentStep,
    visitedSteps: Array.from(visitedSteps),
    isFirstStep,
    isLastStep,
    goToStep,
    nextStep,
    previousStep,
    resetSteps,
    hasVisitedStep,
    progress: ((currentStep + 1) / totalSteps) * 100
  };
};