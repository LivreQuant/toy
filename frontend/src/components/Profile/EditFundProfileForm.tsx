// src/components/Profile/EditFundProfileForm.tsx
import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Button, 
  Typography, 
  TextField, 
  Paper, 
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
  CircularProgress
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useToast } from '../../hooks/useToast';
import { useNavigate } from 'react-router-dom';
import { useFundManager } from '../../hooks/useFundManager';
import { FundProfile, TeamMember } from '../../types';
import './FundProfileForm.css'; // Reuse the same CSS

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
  '$1M - $5M',
  '$5M - $10M',
  '$10M - $25M',
  '$25M - $50M',
  '$50M - $100M',
  '$100M - $250M',
  '$250M - $500M',
  '$500M - $1B',
  'Over $1B'
];

const EditFundProfileForm: React.FC = () => {
  const { addToast } = useToast();
  const navigate = useNavigate();
  const { getFundProfile, updateFundProfile } = useFundManager();
  
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [fundId, setFundId] = useState<string | undefined>(undefined);
  
  const [formData, setFormData] = useState<Omit<FundProfile, 'id' | 'userId' | 'createdAt' | 'updatedAt'>>({
    fundName: '',
    legalStructure: '',
    location: '',
    yearEstablished: new Date().getFullYear().toString(),
    aumRange: '',
    investmentStrategy: '',
    profilePurpose: [],
    otherPurposeDetails: '',
    teamMembers: []
  });

  // Fetch current fund profile
  useEffect(() => {
    const loadFundProfile = async () => {
      setIsLoading(true);
      
      try {
        const response = await getFundProfile();
        
        if (response.success && response.fund) {
          const fund = response.fund;
          setFundId(fund.id);
          
          // Initialize form with fund data
          setFormData({
            fundName: fund.fundName || '',
            legalStructure: fund.legalStructure || '',
            location: fund.location || '',
            yearEstablished: fund.yearEstablished || new Date().getFullYear().toString(),
            aumRange: fund.aumRange || '',
            investmentStrategy: fund.investmentStrategy || '',
            profilePurpose: fund.profilePurpose || [],
            otherPurposeDetails: fund.otherPurposeDetails || '',
            teamMembers: fund.teamMembers.length > 0 
              ? fund.teamMembers 
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
        } else {
          // No fund profile found, redirect to create
          addToast('warning', 'No fund profile found. Please create one first.');
          navigate('/profile/create');
        }
      } catch (error: any) {
        addToast('error', `Error loading fund profile: ${error.message}`);
        console.error('Error loading fund profile:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadFundProfile();
  }, [getFundProfile, addToast, navigate]);

  const steps = ['Fund Information', 'Team Members', 'Objectives'];

  const handleNext = () => {
    let isValid = false;
    
    // Validate current step
    switch (activeStep) {
      case 0: // Fund Info
        isValid = validateFundInfo();
        break;
      case 1: // Team Members
        isValid = validateTeamMembers();
        break;
      case 2: // Purpose
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
        // Add purpose if not already in array
        if (!newPurposes.includes(name)) {
          newPurposes.push(name);
        }
      } else {
        // Remove purpose if in array
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

  // Validation functions - same as in FundProfileForm.tsx
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
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateTeamMembers = () => {
    const newErrors: Record<string, string> = {};
    
    // Check first team member at minimum
    const firstMember = formData.teamMembers[0];
    if (!firstMember.firstName.trim()) {
      newErrors.teamFirstName = 'First name is required for all team members';
    }
    if (!firstMember.lastName.trim()) {
      newErrors.teamLastName = 'Last name is required for all team members';
    }
    if (!firstMember.role.trim()) {
      newErrors.teamRole = 'Role is required for all team members';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!fundId) {
      addToast('error', 'No fund ID found. Cannot update profile.');
      return;
    }
    
    setIsProcessing(true);
    
    try {
      // Call API to update fund profile
      const result = await updateFundProfile(formData);
      
      if (result.success) {
        addToast('success', 'Fund profile updated successfully!');
        navigate('/home');
      } else {
        addToast('error', result.error || 'Failed to update fund profile');
      }
    } catch (error: any) {
      console.error('Error updating fund profile:', error);
      addToast('error', `Failed to update profile: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

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

  // Render fund info section
  const renderFundInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
        <TextField
          required
          fullWidth
          label="Fund Location (City, Country)"
          name="location"
          value={formData.location}
          onChange={handleInputChange}
          error={!!errors.location}
          helperText={errors.location}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <TextField
          fullWidth
          multiline
          rows={4}
          label="Investment Thesis"
          name="investmentStrategy"
          value={formData.investmentStrategy || ''}
          onChange={handleInputChange}
          placeholder="Describe your fund's investment philosophy, thesis, and core beliefs about markets"
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
            {/* Basic Information */}
            <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
              <TextField
                required
                fullWidth
                label="First Name"
                value={member.firstName}
                onChange={(e) => handleTeamMemberChange(member.id, 'firstName', e.target.value)}
                error={!!errors.teamFirstName && index === 0}
                helperText={index === 0 ? errors.teamFirstName : ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
              <TextField
                required
                fullWidth
                label="Last Name"
                value={member.lastName}
                onChange={(e) => handleTeamMemberChange(member.id, 'lastName', e.target.value)}
                error={!!errors.teamLastName && index === 0}
                helperText={index === 0 ? errors.teamLastName : ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
              <TextField
                required
                fullWidth
                label="Role/Title"
                value={member.role}
                onChange={(e) => handleTeamMemberChange(member.id, 'role', e.target.value)}
                placeholder="e.g., Portfolio Manager, Chief Investment Officer"
                error={!!errors.teamRole && index === 0}
                helperText={index === 0 ? errors.teamRole : ''}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 3} as any}>
              <TextField
                fullWidth
                label="Years of Experience"
                type="number"
                value={member.yearsExperience || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'yearsExperience', e.target.value)}
                inputProps={{ min: "0", max: "70" }}
              />
            </Grid>
            
            {/* Personal Details */}
            <Grid {...{component: "div", item: true, xs: 12, sm: 3} as any}>
              <TextField
                fullWidth
                label="Birth Date"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={member.birthDate || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'birthDate', e.target.value)}
              />
            </Grid>

            {/* Professional Qualifications */}
            <Grid {...{component: "div", item: true, xs: 12} as any}>
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

            {/* Experience and Expertise */}
            <Grid {...{component: "div", item: true, xs: 12} as any}>
              <TextField
                fullWidth
                label="Current Employment"
                value={member.currentEmployment || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'currentEmployment', e.target.value)}
                placeholder="Previous firms, positions, and responsibilities"
                multiline
                rows={2}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12} as any}>
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
                        
            <Grid {...{component: "div", item: true, xs: 12} as any}>
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
      
      <Button
        startIcon={<AddIcon />}
        onClick={addTeamMember}
        variant="outlined"
        color="primary"
        sx={{ mt: 2 }}
      >
        Add Team Member
      </Button>
    </div>
  );

  // Render the appropriate step content
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

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading fund profile...
        </Typography>
      </Box>
    );
  }

  return (
    <Box className="fund-profile-form">
      {/* Add Back Button at the top */}
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate('/home')}
        variant="contained"
        color="secondary"
        size="medium"
        sx={{
          py: 1,
          px: 2,
          fontWeight: 600,
          marginBottom: 2,
          width: '150px',
          borderRadius: 2,
          textTransform: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '48px'
        }}
      >
        Back to Home
      </Button>

      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" align="center" gutterBottom>
          Edit Fund Profile
        </Typography>

        <Typography variant="subtitle1" color="textSecondary" align="center" paragraph>
          Update your fund's profile for investors and allocators
        </Typography>
        
        <Stepper activeStep={activeStep} sx={{ mb: 4, pt: 2, pb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        <Divider sx={{ mb: 4 }} />
        
        {renderStepContent(activeStep)}
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 2 }}>
          <Button
            disabled={activeStep === 0}
            onClick={handleBack}
            variant="outlined"
          >
            Back
          </Button>
          
          {activeStep < steps.length - 1 ? (
            <Button 
              variant="contained" 
              color="primary" 
              onClick={handleNext}
            >
              Next
            </Button>
          ) : (
            <Button 
              variant="contained" 
              color="primary" 
              onClick={handleSubmit}
              disabled={isProcessing}
            >
              {isProcessing ? 'Updating Profile...' : 'Update Profile'}
            </Button>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default EditFundProfileForm;