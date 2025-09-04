// src/components/Fund/BaseFundProfileForm.tsx
import React, { useState } from 'react';
import { 
  Box, 
  Typography, 
  TextField, 
  Stepper, 
  Step, 
  StepLabel,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormGroup,
  FormControlLabel,
  Checkbox,
  IconButton,
  SelectChangeEvent,
  Tooltip,
  Grid,
  CircularProgress,
  Paper
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useToast } from '../../hooks/useToast';
import { useNavigate } from 'react-router-dom';
import { FundProfile, TeamMember, CreateFundProfileRequest, UpdateFundProfileRequest } from '@trading-app/types-core';
import { FormContainer, FormStepper } from '../Form';
import './BaseFundProfileForm.css';

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

interface BaseFundProfileFormProps {
  isEditMode: boolean;
  initialData?: FundProfile;
  onSubmit: (formData: CreateFundProfileRequest | UpdateFundProfileRequest) => Promise<{ success: boolean; fundId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

const BaseFundProfileForm: React.FC<BaseFundProfileFormProps> = ({
  isEditMode,
  initialData,
  onSubmit,
  submitButtonText,
  title,
  subtitle
}) => {
  const { addToast } = useToast();
  const navigate = useNavigate();
  
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Initialize form data with initial values or defaults
  const [formData, setFormData] = useState<Omit<FundProfile, 'id' | 'userId' | 'createdAt' | 'updatedAt'>>({
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
  });

  const steps = ['Fund Information', 'Team Members', 'Objectives'];

  const handleNext = () => {
    let isValid = false;
    
    switch (activeStep) {
      case 0:
        isValid = validateFundInfo();
        break;
      case 1:
        isValid = validateTeamMembers();
        break;
      case 2:
        isValid = validatePurpose();
        break;
      default:
        isValid = true;
    }
    
    if (isValid) {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleGoBack = () => {
    navigate('/home');
  };

  // Handler for input fields
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
    
    // Clear error when field is updated
    if (errors[name]) {
      setErrors({
        ...errors,
        [name]: ''
      });
    }
  };

  // Handler for select fields
  const handleSelectChange = (e: SelectChangeEvent) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
    
    // Clear error when field is updated
    if (errors[name]) {
      setErrors({
        ...errors,
        [name]: ''
      });
    }
  };

  // Handler for purpose checkboxes
  const handlePurposeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = event.target;
    
    setFormData(prev => {
      let newPurposes = [...(prev.profilePurpose || [])];
      
      if (checked) {
        if (!newPurposes.includes(name)) {
          newPurposes.push(name);
        }
      } else {
        newPurposes = newPurposes.filter(purpose => purpose !== name);
      }
      
      return {
        ...prev,
        profilePurpose: newPurposes
      };
    });
    
    // Clear error when field is updated
    if (errors.profilePurpose) {
      setErrors({
        ...errors,
        profilePurpose: ''
      });
    }
  };

  // Handler for team member fields
  const handleTeamMemberChange = (id: string, field: keyof TeamMember, value: string) => {
    setFormData({
      ...formData,
      teamMembers: formData.teamMembers.map(member => 
        member.id === id ? { ...member, [field]: value } : member
      )
    });
    
    // Find the index of the member being updated
    const memberIndex = formData.teamMembers.findIndex(member => member.id === id);
    
    // Clear specific error for this field if it exists
    if (memberIndex !== -1) {
      const errorKey = `teamMember${memberIndex}${field.charAt(0).toUpperCase() + field.slice(1)}`;
      if (errors[errorKey]) {
        setErrors({
          ...errors,
          [errorKey]: '',
          teamMembers: ''
        });
      }
    }
  };

  // Add new team member
  const addTeamMember = () => {
    const newId = Date.now().toString();
    setFormData({
      ...formData,
      teamMembers: [
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
      ]
    });
  };

  // Remove team member
  const removeTeamMember = (id: string) => {
    if (formData.teamMembers.length <= 1) {
      addToast('warning', 'At least one team member is required');
      return;
    }
    
    setFormData({
      ...formData,
      teamMembers: formData.teamMembers.filter(member => member.id !== id)
    });
  };

  // Validation functions
  const validatePurpose = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.profilePurpose || formData.profilePurpose.length === 0) {
      newErrors.profilePurpose = 'Please select at least one purpose';
    }
    
    if (formData.profilePurpose?.includes('other') && !formData.otherPurposeDetails) {
      newErrors.otherPurposeDetails = 'Please specify your purpose';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateFundInfo = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.fundName.trim()) {
      newErrors.fundName = 'Fund name is required';
    }
    
    if (!formData.legalStructure) {
      newErrors.legalStructure = 'Legal structure is required';
    }
    
    if (!formData.location?.trim()) {
      newErrors.location = 'Fund location is required';
    }
    
    if (!formData.investmentStrategy?.trim()) {
      newErrors.investmentStrategy = 'Investment thesis is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateTeamMembers = () => {
    const newErrors: Record<string, string> = {};
    
    let hasInvalidMembers = false;
    
    formData.teamMembers.forEach((member, index) => {
      if (!member.firstName.trim()) {
        newErrors[`teamMember${index}FirstName`] = `Team member ${index + 1} requires a first name`;
        hasInvalidMembers = true;
      }
      
      if (!member.lastName.trim()) {
        newErrors[`teamMember${index}LastName`] = `Team member ${index + 1} requires a last name`;
        hasInvalidMembers = true;
      }
      
      if (!member.role.trim()) {
        newErrors[`teamMember${index}Role`] = `Team member ${index + 1} requires a role`;
        hasInvalidMembers = true;
      }
      
      if (!member.birthDate) {
        newErrors[`teamMember${index}BirthDate`] = `Team member ${index + 1} requires a birth date`;
        hasInvalidMembers = true;
      }
    });
    
    if (hasInvalidMembers) {
      newErrors.teamMembers = 'Please complete all required fields for all team members';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateCurrentStep()) {
      return;
    }
    
    setIsProcessing(true);
    
    try {
      const result = await onSubmit(formData);
      
      if (result.success) {
        addToast('success', isEditMode ? 'Fund profile updated successfully!' : 'Fund profile created successfully!');
        navigate('/home');
      } else {
        addToast('error', result.error || (isEditMode ? 'Failed to update fund profile' : 'Failed to create fund profile'));
      }
    } catch (error: any) {
      console.error(`Error ${isEditMode ? 'updating' : 'saving'} fund profile:`, error);
      addToast('error', `Failed to ${isEditMode ? 'update' : 'save'} profile: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const validateCurrentStep = () => {
    switch (activeStep) {
      case 0:
        return validateFundInfo();
      case 1:
        return validateTeamMembers();
      case 2:
        return validatePurpose();
      default:
        return true;
    }
  };

  // Render fund info section
  const renderFundInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
        <Tooltip
          title="The official name of your fund or investment entity"
          arrow
          placement="top"
          componentsProps={{
            tooltip: {
              sx: {
                bgcolor: 'rgba(0, 0, 0, 0.8)',
                '& .MuiTooltip-arrow': {
                  color: 'rgba(0, 0, 0, 0.8)',
                },
              },
            },
          }}
        >
          <TextField
            required
            fullWidth
            label="Fund Name"
            name="fundName"
            value={formData.fundName}
            onChange={handleInputChange}
            error={!!errors.fundName}
            helperText={errors.fundName}
          />
        </Tooltip>
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6, size: 6} as any}>
        <TextField
          required
          fullWidth
          label="Fund Location (State, Country)"
          name="location"
          value={formData.location}
          onChange={handleInputChange}
          error={!!errors.location}
          helperText={errors.location}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6, size: 6} as any}>
        <FormControl fullWidth required>
          <InputLabel>Legal Structure</InputLabel>
          <Select
            name="legalStructure"
            value={formData.legalStructure || ''}
            onChange={handleSelectChange}
            label="Legal Structure"
            error={!!errors.legalStructure}
          >
            {LEGAL_STRUCTURES.map(structure => (
              <MenuItem key={structure} value={structure}>
                {structure}
              </MenuItem>
            ))}
          </Select>
          {errors.legalStructure && (
            <Typography color="error" variant="caption">{errors.legalStructure}</Typography>
          )}
        </FormControl>
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6, size: 6} as any}>
        <FormControl fullWidth>
          <InputLabel>Assets Under Management</InputLabel>
          <Select
            name="aumRange"
            value={formData.aumRange || ''}
            onChange={handleSelectChange}
            label="Assets Under Management"
          >
            {AUM_RANGES.map(range => (
              <MenuItem key={range} value={range}>
                {range}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6, size: 6} as any}>
        <TextField
          fullWidth
          label="Year Established"
          name="yearEstablished"
          value={formData.yearEstablished}
          onChange={handleInputChange}
          type="number"
          inputProps={{ min: "1900", max: new Date().getFullYear().toString() }}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
        <TextField
          required
          fullWidth
          multiline
          rows={4}
          label="Investment Thesis"
          name="investmentStrategy"
          value={formData.investmentStrategy || ''}
          onChange={handleInputChange}
          placeholder="Describe your fund's investment philosophy, thesis, and core beliefs about markets"
          error={!!errors.investmentStrategy}
          helperText={errors.investmentStrategy}
        />
      </Grid>
    </Grid>
  );

  // Render team members section
  const renderTeamMembers = () => (
    <div>
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
          
          <Grid container spacing={2}>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="First Name"
                value={member.firstName}
                onChange={(e) => handleTeamMemberChange(member.id, 'firstName', e.target.value)}
                error={!!errors[`teamMember${index}FirstName`]}
                helperText={errors[`teamMember${index}FirstName`] || ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="Last Name"
                value={member.lastName}
                onChange={(e) => handleTeamMemberChange(member.id, 'lastName', e.target.value)}
                error={!!errors[`teamMember${index}LastName`]}
                helperText={errors[`teamMember${index}LastName`] || ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="Role/Title"
                value={member.role}
                onChange={(e) => handleTeamMemberChange(member.id, 'role', e.target.value)}
                placeholder="e.g., Portfolio Manager, Chief Investment Officer"
                error={!!errors[`teamMember${index}Role`]}
                helperText={errors[`teamMember${index}Role`] || ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 3, size: 3} as any}>
              <TextField
                fullWidth
                label="Years of Experience"
                type="number"
                value={member.yearsExperience || '0'}
                onChange={(e) => {
                  const inputValue = e.target.value;
                  const parsedValue = parseInt(inputValue, 10);
                  const validValue = (inputValue === '' || isNaN(parsedValue)) ? '0' : inputValue;
                  handleTeamMemberChange(member.id, 'yearsExperience', validValue);
                }}
                InputLabelProps={{ shrink: true }}
                inputProps={{ 
                  min: "0", 
                  max: "70",
                  style: { paddingRight: '20px' }
                }}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 3, size: 3} as any}>
              <TextField
                required
                fullWidth
                label="Birth Date"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={member.birthDate || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'birthDate', e.target.value)}
                error={!!errors[`teamMember${index}BirthDate`]}
                helperText={errors[`teamMember${index}BirthDate`] || ''}
              />
            </Grid>

            <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
              <TextField
                fullWidth
                label="Education"
                value={member.education || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'education', e.target.value)}
                placeholder="e.g., MBA Harvard, BS Finance NYU"
                multiline
                rows={2}
              />
            </Grid>

            <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
              <TextField
                fullWidth
                label="Current Employment"
                value={member.currentEmployment || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'currentEmployment', e.target.value)}
                placeholder="Current firm"
                multiline
                rows={2}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
              <TextField
                fullWidth
                label="Investment Expertise"
                value={member.investmentExpertise || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'investmentExpertise', e.target.value)}
                placeholder="e.g., Value investing, Small-cap equities, Fixed income, Emerging markets"
                multiline
                rows={2}
              />
            </Grid>
                        
            <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
              <TextField
                fullWidth
                label="LinkedIn Profile URL"
                value={member.linkedin || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'linkedin', e.target.value)}
                placeholder="https://linkedin.com/in/username"
              />
            </Grid>
          </Grid>
        </Paper>
      ))}

      {errors.teamMembers && (
        <Typography color="error" variant="body2" sx={{ mt: 2 }}>
          {errors.teamMembers}
        </Typography>
      )}
            
      <Box
        component="button"
        type="button"
        onClick={addTeamMember}
        sx={{
          mt: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          padding: '8px 16px',
          backgroundColor: 'transparent',
          border: '1px solid',
          borderColor: 'primary.main',
          borderRadius: 1,
          color: 'primary.main',
          cursor: 'pointer',
          transition: 'all 0.2s',
          '&:hover': {
            backgroundColor: 'primary.main',
            color: 'primary.contrastText'
          }
        }}
      >
        <AddIcon />
        Add Team Member
      </Box>
    </div>
  );

  // Render purpose section
  const renderPurposeSection = () => (
    <div>
      <Typography variant="h6" gutterBottom>
        What are your objectives? (Select all that apply)
      </Typography>
      
      <FormGroup>
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('raise_capital')}
              onChange={handlePurposeChange}
              name="raise_capital"
            />
          }
          label="Raise capital for your fund"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('join_team')}
              onChange={handlePurposeChange}
              name="join_team"
            />
          }
          label="Join an existing team or firm"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('find_members')}
              onChange={handlePurposeChange}
              name="find_members"
            />
          }
          label="Find partners or team members"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('sell_strategy')}
              onChange={handlePurposeChange}
              name="sell_strategy"
            />
          }
          label="Sell or license your investment strategy"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('track_record')}
              onChange={handlePurposeChange}
              name="track_record"
            />
          }
          label="Build a verifiable track record"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose?.includes('other')}
              onChange={handlePurposeChange}
              name="other"
            />
          }
          label="Other"
        />
      </FormGroup>
      
      {errors.profilePurpose && (
        <Typography color="error" variant="body2">{errors.profilePurpose}</Typography>
      )}
      
      {formData.profilePurpose?.includes('other') && (
        <div className="form-group">
          <TextField
            fullWidth
            multiline
            rows={2}
            label="Please specify"
            name="otherPurposeDetails"
            value={formData.otherPurposeDetails || ''}
            onChange={handleInputChange}
            error={!!errors.otherPurposeDetails}
            helperText={errors.otherPurposeDetails}
            sx={{ mt: 2 }}
          />
        </div>
      )}
    </div>
  );

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderFundInfo();
      case 1:
        return renderTeamMembers();
      case 2:
        return renderPurposeSection();
      default:
        return null;
    }
  };

  return (
    <FormContainer 
      title={title} 
      subtitle={subtitle} 
      onBack={handleGoBack}
    >
      <FormStepper
        activeStep={activeStep}
        steps={steps}
        onNext={handleNext}
        onBack={handleBack}
        onSubmit={handleSubmit}
        isSubmitting={isProcessing}
        submitButtonText={submitButtonText}
      >
        {renderStepContent(activeStep)}
      </FormStepper>
    </FormContainer>
  );
};

export default BaseFundProfileForm;