// src/components/Book/BaseBookForm.tsx (COMPLETE REFACTOR)
import React from 'react';
import { TextField } from '@mui/material';
import { 
  FormWizard, 
  FormContainer, 
  ToggleButtonGroup, 
  SectionGrid, 
  ChipSelector, 
  SliderField 
} from '../Form';
import { useFormState, useFormValidation } from '../../hooks/forms';
import { validationRules, combineValidators } from '../../utils/forms';
import { BookRequest } from '@trading-app/types-core';
import ConvictionModelForm from './ConvictionModelForm2';

interface BaseBookFormProps {
  isEditMode: boolean;
  initialData?: Partial<BookRequest>;
  onSubmit: (formData: BookRequest) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

const sectors = [
  { value: 'generalist', label: 'Generalist' },
  { value: 'tech', label: 'Technology' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'financials', label: 'Financials' },
  { value: 'consumer', label: 'Consumer' },
  { value: 'industrials', label: 'Industrials' },
  { value: 'energy', label: 'Energy' },
  { value: 'materials', label: 'Materials' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'realestate', label: 'Real Estate' }
];

export const BaseBookForm: React.FC<BaseBookFormProps> = ({
  isEditMode,
  initialData = {},
  onSubmit,
  submitButtonText,
  title,
  subtitle
}) => {
  const { formData, updateField, isDirty } = useFormState({
    initialData: {
      name: initialData.name || 'My Trading Book',
      regions: initialData.regions || ['us'],
      markets: initialData.markets || ['equities'],
      instruments: initialData.instruments || ['stocks'],
      investmentApproaches: initialData.investmentApproaches || [],
      investmentTimeframes: initialData.investmentTimeframes || [],
      sectors: initialData.sectors || [],
      positionTypes: {
        long: initialData.positionTypes?.long || false,
        short: initialData.positionTypes?.short || false
      },
      initialCapital: initialData.initialCapital || 100000000,
      convictionSchema: initialData.convictionSchema || {
        portfolioApproach: 'incremental',
        targetConvictionMethod: 'percent',
        incrementalConvictionMethod: 'side_score',
        maxScore: 3,
        horizons: ['30m', '1h', '1d'],
      }
    },
    autoSave: true,
    storageKey: isEditMode ? undefined : 'book-form-draft'
  });

  const { errors, validateForm } = useFormValidation({
    initialData: formData,
    validationRules: [
      {
        field: 'name',
        validate: combineValidators(
          validationRules.required('Book name is required'),
          validationRules.minLength(2, 'Book name must be at least 2 characters')
        ),
        message: 'Book name validation failed'
      },
      {
        field: 'regions',
        validate: validationRules.arrayMinLength(1, 'At least one region must be selected'),
        message: 'Region selection validation failed'
      },
      {
        field: 'markets',
        validate: validationRules.arrayMinLength(1, 'At least one market must be selected'),
        message: 'Market selection validation failed'
      },
      {
        field: 'instruments',
        validate: validationRules.arrayMinLength(1, 'At least one instrument must be selected'),
        message: 'Instrument selection validation failed'
      },
      {
        field: 'investmentApproaches',
        validate: validationRules.arrayMinLength(1, 'Please select at least one investment approach'),
        message: 'Investment approach validation failed'
      },
      {
        field: 'investmentTimeframes',
        validate: validationRules.arrayMinLength(1, 'Please select at least one investment timeframe'),
        message: 'Investment timeframe validation failed'
      },
      {
        field: 'sectors',
        validate: validationRules.arrayMinLength(1, 'Please select at least one sector'),
        message: 'Sector validation failed'
      },
      {
        field: 'initialCapital',
        validate: combineValidators(
          validationRules.required('Initial capital is required'),
          validationRules.min(1000000, 'Minimum capital is $1M')
        ),
        message: 'Initial capital validation failed'
      }
    ]
  });

  const steps = [
    {
      label: 'Basic Information',
      content: (
        <SectionGrid title="Book Details">
          <TextField
            fullWidth
            label="Book Name"
            value={formData.name}
            onChange={(e) => updateField('name', e.target.value)}
            error={!!errors.name}
            helperText={errors.name}
            required
          />
          
          <ToggleButtonGroup
            title="Region"
            description="Geographic focus of the investment strategy"
            options={[
              { value: 'us', label: 'US Region' },
              { value: 'eu', label: 'EU Region', description: 'Coming soon' },
              { value: 'asia', label: 'Asia Region', description: 'Coming soon' },
              { value: 'emerging', label: 'Emerging', description: 'Coming soon' }
            ]}
            value={formData.regions}
            onChange={(value) => updateField('regions', value)}
            error={errors.regions}
            required
          />
          
          <ToggleButtonGroup
            title="Markets"
            description="The markets accessed by the investment strategy"
            options={[
              { value: 'equities', label: 'Equities' },
              { value: 'bonds', label: 'Bonds', description: 'Coming soon' },
              { value: 'currencies', label: 'Currencies', description: 'Coming soon', disabled: true },
              { value: 'commodities', label: 'Commodities', description: 'Coming soon', disabled: true },
              { value: 'cryptos', label: 'Cryptos', description: 'Coming soon', disabled: true }
            ]}
            value={formData.markets}
            onChange={(value) => updateField('markets', value)}
            error={errors.markets}
            required
          />
          
          <ToggleButtonGroup
            title="Instruments"
            description="Financial instruments used in the portfolio"
            options={[
              { value: 'stocks', label: 'Stocks' },
              { value: 'etfs', label: 'ETFs', description: 'Coming soon' },
              { value: 'funds', label: 'Funds', description: 'Coming soon', disabled: true },
              { value: 'options', label: 'Options', description: 'Coming soon', disabled: true },
              { value: 'futures', label: 'Futures', description: 'Coming soon', disabled: true }
            ]}
            value={formData.instruments}
            onChange={(value) => updateField('instruments', value)}
            error={errors.instruments}
            required
          />
        </SectionGrid>
      ),
      validate: () => !errors.name && !errors.regions && !errors.markets && !errors.instruments
    },
    
    {
      label: 'Investment Strategy',
      content: (
        <SectionGrid title="Strategy Configuration">
          <ToggleButtonGroup
            title="Investment Approach"
            description="The fundamental methodology used to make investment decisions"
            options={[
              { value: 'quantitative', label: 'Quantitative' },
              { value: 'discretionary', label: 'Discretionary' }
            ]}
            value={formData.investmentApproaches}
            onChange={(value) => updateField('investmentApproaches', value)}
            error={errors.investmentApproaches}
            required
          />
          
          <ToggleButtonGroup
            title="Investment Timeframe"
            description="The typical holding period for positions in the portfolio"
            options={[
              { value: 'short', label: 'Short-term', description: 'hours to days' },
              { value: 'medium', label: 'Medium-term', description: 'days to weeks' },
              { value: 'long', label: 'Long-term', description: 'weeks to months' }
            ]}
            value={formData.investmentTimeframes}
            onChange={(value) => updateField('investmentTimeframes', value)}
            error={errors.investmentTimeframes}
            required
          />
        </SectionGrid>
      ),
      validate: () => !errors.investmentApproaches && !errors.investmentTimeframes
    },
    
    {
      label: 'Investment Focus',
      content: (
        <ChipSelector
          title="Investment Focus"
          description="Sectors the portfolio specializes in"
          options={sectors}
          value={formData.sectors}
          onChange={(value) => updateField('sectors', value)}
          error={errors.sectors}
          required
        />
      ),
      validate: () => !errors.sectors
    },
    
    {
      label: 'Position & Capital',
      content: (
        <SectionGrid title="Capital & Risk Configuration">
          <ToggleButtonGroup
            title="Position Types"
            description="The directional exposure strategy employed in the portfolio"
            options={[
              { value: 'long', label: 'Long' },
              { value: 'short', label: 'Short' }
            ]}
            value={[
              ...(formData.positionTypes.long ? ['long'] : []),
              ...(formData.positionTypes.short ? ['short'] : [])
            ]}
            onChange={(value) => updateField('positionTypes', {
              long: value.includes('long'),
              short: value.includes('short')
            })}
            error={errors.positionTypes}
            required
          />
          
          <SliderField
            title="Allocation"
            description="Specify the managed allocation (in millions USD)"
            value={formData.initialCapital / 1000000}
            onChange={(value) => updateField('initialCapital', value * 1000000)}
            min={50}
            max={1000}
            step={50}
            marks={[
              { value: 50, label: '$50M' },
              { value: 100, label: '$100M' },
              { value: 500, label: '$500M' },
              { value: 1000, label: '$1000M' }
            ]}
            formatValue={(value) => `$${value}M`}
            showInput
            unit="M"
            error={errors.initialCapital}
            required
          />
        </SectionGrid>
      ),
      validate: () => !errors.positionTypes && !errors.initialCapital
    },
    
    {
      label: 'Conviction Model',
      content: (
        <ConvictionModelForm
          value={formData.convictionSchema}
          onChange={(value) => updateField('convictionSchema', value)}
        />
      ),
      validate: () => true // ConvictionModelForm handles its own validation
    }
  ];

  const handleSubmit = async (data: any) => {
    if (!validateForm()) {
      return { success: false, error: 'Please correct the validation errors' };
    }

    const bookData: BookRequest = {
      name: formData.name,
      regions: formData.regions,
      markets: formData.markets,
      instruments: formData.instruments,
      investmentApproaches: formData.investmentApproaches,
      investmentTimeframes: formData.investmentTimeframes,
      sectors: formData.sectors.filter(sector => sector !== 'generalist'),
      positionTypes: formData.positionTypes,
      initialCapital: formData.initialCapital,
      convictionSchema: formData.convictionSchema
    };

    return await onSubmit(bookData);
  };

  return (
    <FormContainer
      title={title}
      subtitle={subtitle}
      onBack={() => window.history.back()}
    >
      <FormWizard
        steps={steps}
        onSubmit={handleSubmit}
        submitButtonText={submitButtonText}
        title=""
        subtitle=""
      />
    </FormContainer>
  );
};

export default BaseBookForm;