// src/components/Form/index.ts
// Form Wizard
export * from './FormWizard';

// Form Fields
export * from './FormFields';

// Form Layouts
export * from './FormLayouts';

// Re-export commonly used types - fix the imports
export type {
  FormWizardProps
} from './FormWizard';

export type {
  FormFieldProps,
  ToggleButtonGroupProps,
  SectionGridProps,
  ChipSelectorProps,
  SliderFieldProps
} from './FormFields';

export type {
  FormContainerProps,
  FormActionsProps
} from './FormLayouts';