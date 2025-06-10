// src/components/Fund/BaseFundProfileForm.tsx (REFACTORED)
import React, { useState } from 'react';
import { 
  FormWizard, 
  FormContainer, 
  FormField, 
  SectionGrid, 
  ChipSelector 
} from '../Form';
import { useFormState, useFormValidation } from '../../hooks/forms';
import { validationRules, combineValidators } from '../../utils/forms';
import { 
  TextField, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem, 
  IconButton, 
  Paper, 
  Typography, 
  Box, 
  Button 
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { FundProfile, TeamMember, CreateFundProfileRequest, UpdateFundProfileRequest } from '@trading-app/types-core';

const LEGAL_STRUCTURES = [
  'Personal Account',
  'Limited Partnership (LP)',
  'Limited Liability Company (LLC)',
  'Corporation',
  'Offshore Fund',
  'Master-Feeder Structure',
  'Separately Managed Account (SMA)',
  'Other'
];

const AUM_RANGES = [
  'Under $1M',
  '$1M - $10M',
  '$10M - $100M',
  '$100M - $1B',
  'Over $1B'
];

const PURPOSE_OPTIONS = [
  { value: 'raise_capital', label: 'Raise Capital', description: 'Raise capital for your fund' },
  { value: 'join_team', label: 'Join Team', description: 'Join an existing team or firm' },
  { value: 'find_members', label: 'Find Partners', description: 'Find partners or team members' },
  { value: 'sell_strategy', label: 'Sell Strategy', description: 'Sell or license your investment strategy' },
  { value: 'track_record', label: 'Track Record', description: 'Build a verifiable track record' },
  { value: 'other', label: 'Other', description: 'Custom purpose' }
];

interface BaseFundProfileFormProps {
  isEditMode: boolean;
  initialData?: FundProfile;
  onSubmit: (formData: CreateFundProfileRequest | UpdateFundProfileRequest) => Promise<{ success: boolean; fundId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

export const BaseFundProfileForm: React.FC<BaseFundProfileFormProps> = ({
  isEditMode,
  initialData,
  onSubmit,
  submitButtonText,
  title,
  subtitle
}) => {
  const { formData, updateField, updateFields } = useFormState({
    initialData: {
      fundName: initialData?.fundName || '',
      legalStructure: initialData?.legalStructure || '',
      location: initialData?.location || '',
      yearEstablished: initialData?.yearEstablished || new Date().getFullYear().toString(),
      aumRange: initialData?.aumRange || '',
      investmentStrategy: initialData?.investmentStrategy || '',
      profilePurpose: initialData?.profilePurpose || [],
      otherPurposeDetails: initialData?.otherPurposeDetails || '',
      teamMembers: initialData?.teamMembers && initialData.teamMembers.length > 0
        ? [...initialData.teamMembers]
        : [{
            id: '1',
            firstName: '',
            lastName: '',
            role: '',
            yearsExperience: '',
            education: '',
            currentEmployment: '',
            investmentExpertise: '',
            birthDate: '',
            linkedin: '',
          }]
    },
    autoSave: true,
    storageKey: isEditMode ? undefined : 'fund-profile-draft'
  });

  const { errors, validateForm } = useFormValidation({
    initialData: formData,
    validationRules: [
      {
        field: 'fundName',
        validate: combineValidators(
          validationRules.required('Fund name is required'),
          validationRules.minLength(2, 'Fund name must be at least 2 characters')
        ),
        message: 'Fund name validation failed'
      },
      {
        field: 'legalStructure',
        validate: validationRules.required('Legal structure is required'),
        message: 'Legal structure validation failed'
      },
      {
        field: 'location',
        validate: validationRules.required('Fund location is required'),
        message: 'Location validation failed'
      },
      {
        field: 'investmentStrategy',
        validate: validationRules.required('Investment thesis is required'),
        message: 'Investment strategy validation failed'
      },
      {
        field: 'profilePurpose',
        validate: validationRules.arrayMinLength(1, 'Please select at least one purpose'),
        message: 'Purpose validation failed'
      }
    ]
  });

  const addTeamMember = () => {
    const newId = Date.now().toString();
    const newMembers = [
      ...formData.teamMembers,
      {
        id: newId,
        firstName: '',
        lastName: '',
        role: '',
        yearsExperience: '',
        education: '',
        currentEmployment: '',
        investmentExpertise: '',
        birthDate: '',
        linkedin: '',
      }
    ];
    updateField('teamMembers', newMembers);
  };

  const removeTeamMember = (id: string) => {
    if (formData.teamMembers.length <= 1) {
      return; // Keep at least one team member
    }
    
    const newMembers = formData.teamMembers.filter(member => member.id !== id);
    updateField('teamMembers', newMembers);
  };

  const updateTeamMember = (id: string, field: keyof TeamMember, value: string) => {
    const newMembers = formData.teamMembers.map(member => 
      member.id === id ? { ...member, [field]: value } : member
    );
    updateField('teamMembers', newMembers);
  };

  const validateTeamMembers = (): boolean => {
    return formData.teamMembers.every(member => 
      member.firstName.trim() && 
      member.lastName.trim() && 
      member.role.trim() && 
      member.birthDate
    );
  };

  const steps = [
    {
      label: 'Fund Information',
      content: (
        <SectionGrid title="Basic Fund Details">
          <FormField
            label="Fund Name"
            value={formData.fundName}
            onChange={(value) => updateField('fundName', String(value))}
            error={errors.fundName}
            required
          />
          
          <FormField
            label="Fund Location (State, Country)"
            value={formData.location}
            onChange={(value) => updateField('location', String(value))}
            error={errors.location}
            required
          />
          
          <FormControl fullWidth required>
            <InputLabel>Legal Structure</InputLabel>
            <Select
              value={formData.legalStructure || ''}
              onChange={(e) => updateField('legalStructure', e.target.value)}
              label="Legal Structure"
              error={!!errors.legalStructure}
            >
              {LEGAL_STRUCTURES.map(structure => (
                <MenuItem key={structure} value={structure}>
                  {structure}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <FormControl fullWidth>
            <InputLabel>Assets Under Management</InputLabel>
            <Select
              value={formData.aumRange || ''}
              onChange={(e) => updateField('aumRange', e.target.value)}
              label="Assets Under Management"
            >
              {AUM_RANGES.map(range => (
                <MenuItem key={range} value={range}>
                  {range}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <FormField
            label="Year Established"
            type="number"
            value={formData.yearEstablished}
            onChange={(value) => updateField('yearEstablished', String(value))}
          />
          
          <FormField
            label="Investment Thesis"
            value={formData.investmentStrategy || ''}
            onChange={(value) => updateField('investmentStrategy', String(value))}
            placeholder="Describe your fund's investment philosophy, thesis, and core beliefs about markets"
            multiline
            rows={4}
            error={errors.investmentStrategy}
            required
          />
        </SectionGrid>
      ),
      validate: () => !errors.fundName && !errors.legalStructure && !errors.location && !errors.investmentStrategy
    },
    
    {
      label: 'Team Members',
      content: (
        <Box>
          <Typography variant="h6" gutterBottom>
            Management Team
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Add information about your team members
          </Typography>
          
          {formData.teamMembers.map((member, index) => (
            <Paper key={member.id} elevation={2} sx={{ p: 3, mb: 3, position: 'relative' }}>
              <Typography variant="h6" gutterBottom>
                Team Member {index + 1}
              </Typography>
              
              {formData.teamMembers.length > 1 && (
                <IconButton 
                  aria-label="delete" 
                  onClick={() => removeTeamMember(member.id)}
                  sx={{ position: 'absolute', top: 8, right: 8 }}
                >
                  <DeleteIcon />
                </IconButton>
              )}
              
              <SectionGrid>
                <FormField
                  label="First Name"
                  value={member.firstName}
                  onChange={(value) => updateTeamMember(member.id, 'firstName', String(value))}
                  required
                />
                
                <FormField
                  label="Last Name"
                  value={member.lastName}
                  onChange={(value) => updateTeamMember(member.id, 'lastName', String(value))}
                  required
                />
                
                <FormField
                  label="Role/Title"
                  value={member.role}
                  onChange={(value) => updateTeamMember(member.id, 'role', String(value))}
                  placeholder="e.g., Portfolio Manager, Chief Investment Officer"
                  required
                />
                
                <FormField
                  label="Years of Experience"
                  type="number"
                  value={member.yearsExperience || '0'}
                  onChange={(value) => updateTeamMember(member.id, 'yearsExperience', String(value))}
                />
                
                <TextField
                  fullWidth
                  required
                  label="Birth Date"
                  type="date"
                  InputLabelProps={{ shrink: true }}
                  value={member.birthDate || ''}
                  onChange={(e) => updateTeamMember(member.id, 'birthDate', e.target.value)}
                />
                
                <FormField
                  label="Education"
                  value={member.education || ''}
                  onChange={(value) => updateTeamMember(member.id, 'education', String(value))}
                  placeholder="e.g., MBA Harvard, BS Finance NYU"
                  multiline
                  rows={2}
                />
                
                <FormField
                  label="Current Employment"
                  value={member.currentEmployment || ''}
                  onChange={(value) => updateTeamMember(member.id, 'currentEmployment', String(value))}
                  placeholder="Current firm"
                  multiline
                  rows={2}
                />
                
                <FormField
                  label="Investment Expertise"
                  value={member.investmentExpertise || ''}
                  onChange={(value) => updateTeamMember(member.id, 'investmentExpertise', String(value))}
                  placeholder="e.g., Value investing, Small-cap equities, Fixed income"
                  multiline
                  rows={2}
                />
                
                <FormField
                  label="LinkedIn Profile URL"
                  value={member.linkedin || ''}
                  onChange={(value) => updateTeamMember(member.id, 'linkedin', String(value))}
                  placeholder="https://linkedin.com/in/username"
                />
              </SectionGrid>
            </Paper>
          ))}
          
          <Button
            startIcon={<AddIcon />}
            onClick={addTeamMember}
            variant="outlined"
            color="primary"
            sx={{ mt: 2 }}
          >
            Add Team Member
          </Button>
        </Box>
      ),
      validate: validateTeamMembers
    },
    
    {
      label: 'Objectives',
      content: (
        <Box>
          <ChipSelector
            title="What are your objectives?"
            description="Select all that apply"
            options={PURPOSE_OPTIONS}
            value={formData.profilePurpose || []}
            onChange={(value) => updateField('profilePurpose', value)}
            error={errors.profilePurpose}
            required
          />
          
          {formData.profilePurpose?.includes('other') && (
            <FormField
              label="Please specify your purpose"
              value={formData.otherPurposeDetails || ''}
              onChange={(value) => updateField('otherPurposeDetails', String(value))}
              multiline
              rows={2}
              required
            />
          )}
        </Box>
      ),
      validate: () => !errors.profilePurpose && 
        (!formData.profilePurpose?.includes('other') || formData.otherPurposeDetails?.trim())
    }
  ];

  const handleSubmit = async () => {
    if (!validateForm()) {
      return { success: false, error: 'Please correct the validation errors' };
    }

    return await onSubmit(formData);
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

export default BaseFundProfileForm;