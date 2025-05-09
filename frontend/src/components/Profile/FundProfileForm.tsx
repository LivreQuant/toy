// src/components/Profile/FundProfileForm.tsx
import React, { useState } from 'react';
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
  Grid
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useToast } from '../../hooks/useToast';
import './FundProfileForm.css';

// Define types
interface TeamMember {
  id: string;
  firstName: string;
  lastName: string;
  role: string;
  yearsExperience: string;
  education: string;
  //certifications: string;
  currentEmployment: string;
  investmentExpertise: string;
  birthDate: string;
  //biography: string;
  //email: string;
  //phone: string;
  linkedin?: string;
  //twitter?: string;
  //photoUrl?: string;
}

interface FundProfileData {
  // Fund Information
  fundName: string;
  legalStructure: string;
  location: string;
  yearEstablished: string;
  aumRange: string;
  investmentStrategy: string;
  
  // Purpose of the profile
  profilePurpose: string[];
  otherPurposeDetails?: string;
  //targetRaise?: string;
  //minimumInvestment?: string;
  //requiredRoles?: string;
  
  // Team Members
  teamMembers: TeamMember[];
  
  // Institutional Information
  //complianceOfficer: string;
  //complianceEmail: string;
  //fundAdministrator: string;
  //primeBroker: string;
  //auditor: string;
  //legalCounsel: string;
  //regulatoryRegistrations: string;
  
  // Track Record
  //previousPerformance: string;
  //references: string;
}

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

const FundProfileForm: React.FC = () => {
  const { addToast } = useToast();
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [formData, setFormData] = useState<FundProfileData>({
    // Fund Information
    fundName: '',
    legalStructure: '',
    location: '',
    yearEstablished: new Date().getFullYear().toString(),
    aumRange: '',
    investmentStrategy: '',
    
    // Profile purpose
    profilePurpose: [],
    otherPurposeDetails: '',
    //targetRaise: '',
    //minimumInvestment: '',
    //requiredRoles: '',
    
    // Team Members (initialize with one empty member)
    teamMembers: [{
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
    }],
    
    // Institutional Information
    //complianceOfficer: '',
    //complianceEmail: '',
    //fundAdministrator: '',
    //primeBroker: '',
    //auditor: '',
    //legalCounsel: '',
    //regulatoryRegistrations: '',
    
    // Track Record
    //previousPerformance: '',
    //references: ''
  });

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
      let newPurposes = [...prev.profilePurpose];
      
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
          //certifications: '',
          currentEmployment: '',
          investmentExpertise: '',
          birthDate: '',
          //biography: '',
          //email: '',
          //phone: '',
          linkedin: '',
          //twitter: '',
          //photoUrl: ''
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
    
    if (formData.profilePurpose.length === 0) {
      newErrors.profilePurpose = 'Please select at least one purpose';
    }
    
    if (formData.profilePurpose.includes('other') && !formData.otherPurposeDetails) {
      newErrors.otherPurposeDetails = 'Please specify your purpose';
    }
    
    /*
    if (formData.profilePurpose.includes('raise_capital')) {
      if (!formData.targetRaise) {
        newErrors.targetRaise = 'Target raise amount is required';
      }
      if (!formData.minimumInvestment) {
        newErrors.minimumInvestment = 'Minimum investment amount is required';
      }
    }
    */
    
    if (formData.profilePurpose.includes('find_members')) { // && !formData.requiredRoles) {
      newErrors.requiredRoles = 'Please specify what roles you are looking to fill';
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
    
    if (!formData.location.trim()) {
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

  const handleSubmit = () => {
    // Here you would send the data to your backend API
    console.log('Submitting fund profile:', formData);
    
    // For demo purposes, store in localStorage
    try {
      setIsProcessing(true);
      localStorage.setItem('fundProfile', JSON.stringify(formData));
      
      // Show success message
      addToast('success', 'Fund profile created successfully!');
      
      // Navigate back to the home page
      window.location.href = '/home';
    } catch (error) {
      console.error('Error saving to localStorage:', error);
      addToast('error', 'Failed to save profile data');
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
              checked={formData.profilePurpose.includes('raise_capital')}
              onChange={handlePurposeChange}
              name="raise_capital"
            />
          }
          label="Raise capital for your fund"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose.includes('join_team')}
              onChange={handlePurposeChange}
              name="join_team"
            />
          }
          label="Join an existing team or firm"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose.includes('find_members')}
              onChange={handlePurposeChange}
              name="find_members"
            />
          }
          label="Find partners or team members"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose.includes('sell_strategy')}
              onChange={handlePurposeChange}
              name="sell_strategy"
            />
          }
          label="Sell or license your investment strategy"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose.includes('track_record')}
              onChange={handlePurposeChange}
              name="track_record"
            />
          }
          label="Build a verifiable track record"
        />
        
        <FormControlLabel
          control={
            <Checkbox 
              checked={formData.profilePurpose.includes('other')}
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
      
      {formData.profilePurpose.includes('other') && (
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
      
      {/*
      {formData.profilePurpose.includes('raise_capital') && (
        <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle1" gutterBottom>
            Fundraising Details
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Target Amount"
                name="targetRaise"
                value={formData.targetRaise || ''}
                onChange={handleInputChange}
                placeholder="e.g., $5M, $10-20M"
                error={!!errors.targetRaise}
                helperText={errors.targetRaise}
                sx={{ mb: 2 }}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Minimum Investment"
                name="minimumInvestment"
                value={formData.minimumInvestment || ''}
                onChange={handleInputChange}
                placeholder="e.g., $250K, $1M"
                error={!!errors.minimumInvestment}
                helperText={errors.minimumInvestment}
              />
            </Grid>
          </Grid>
        </Box>
      )}
      
      {formData.profilePurpose.includes('find_members') && (
        <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle1" gutterBottom>
            Team Building
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={2}
            label="What roles are you looking to fill?"
            name="requiredRoles"
            value={formData.requiredRoles || ''}
            onChange={handleInputChange}
            placeholder="e.g., Portfolio Manager, Research Analyst, Risk Manager"
            error={!!errors.requiredRoles}
            helperText={errors.requiredRoles}
          />
        </Box>
      )}
      */}
    </div>
  );

  // Render fund info section
  const renderFundInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>  
      <Tooltip
        title="Information text here"
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
      
      <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
        <FormControl fullWidth required>
          <InputLabel>Legal Structure</InputLabel>
          <Select
            name="legalStructure"
            value={formData.legalStructure}
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
      
      <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
        <FormControl fullWidth>
          <InputLabel>Assets Under Management</InputLabel>
          <Select
            name="aumRange"
            value={formData.aumRange}
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
      
      <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
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
      
      <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>
        <TextField
          fullWidth
          multiline
          rows={4}
          label="Investment Thesis"
          name="investmentStrategy"
          value={formData.investmentStrategy}
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
            <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
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
            
            <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
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
            
            <Grid {...{component: "div", item: true, xs: 12,size: 6} as any}>
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
            
            <Grid {...{component: "div", item: true, xs: 12,size: 3} as any}>
              <TextField
                fullWidth
                label="Years of Experience"
                type="number"
                value={member.yearsExperience}
                onChange={(e) => handleTeamMemberChange(member.id, 'yearsExperience', e.target.value)}
                inputProps={{ min: "0", max: "70" }}
              />
            </Grid>
            
            {/* Personal Details */}
            <Grid {...{component: "div", item: true, xs: 12,size: 3} as any}>
              <TextField
                fullWidth
                label="Birth Date"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={member.birthDate}
                onChange={(e) => handleTeamMemberChange(member.id, 'birthDate', e.target.value)}
              />
            </Grid>

            {/* Professional Qualifications */}
            <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>
              <TextField
                fullWidth
                label="Education"
                value={member.education}
                onChange={(e) => handleTeamMemberChange(member.id, 'education', e.target.value)}
                placeholder="e.g., MBA Harvard, BS Finance NYU"
                multiline
                rows={2}
              />
            </Grid>
            
            {/*
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Professional Certifications"
                value={member.certifications}
                onChange={(e) => handleTeamMemberChange(member.id, 'certifications', e.target.value)}
                placeholder="e.g., CFA, CAIA, CFP, Series 7/63"
              />
            </Grid>
            */}

            {/* Experience and Expertise */}
            <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>
              <TextField
                fullWidth
                label="Current Employment"
                value={member.currentEmployment}
                onChange={(e) => handleTeamMemberChange(member.id, 'currentEmployment', e.target.value)}
                placeholder="Previous firms, positions, and responsibilities"
                multiline
                rows={2}
              />
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>
              <TextField
                fullWidth
                label="Investment Expertise"
                value={member.investmentExpertise}
                onChange={(e) => handleTeamMemberChange(member.id, 'investmentExpertise', e.target.value)}
                placeholder="e.g., Value investing, Small-cap equities, Fixed income, Emerging markets"
                multiline
                rows={2}
              />
            </Grid>
                        
            <Grid {...{component: "div", item: true, xs: 12,size: 12} as any}>
              <TextField
                fullWidth
                label="LinkedIn Profile URL"
                value={member.linkedin || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'linkedin', e.target.value)}
                placeholder="https://linkedin.com/in/username"
              />
            </Grid>
            
            {/*
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Photo URL (Optional)"
                value={member.photoUrl || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'photoUrl', e.target.value)}
                placeholder="Link to professional headshot"
              />
            </Grid>
            */}

            {/* Biography */}
            {/*
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Professional Biography"
                value={member.biography || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'biography', e.target.value)}
                placeholder="A brief professional biography highlighting career achievements and investment philosophy"
                multiline
                rows={3}
              />
            </Grid>
            */}

            {/* Contact Information */}
            {/*
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={member.email || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'email', e.target.value)}
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Phone"
                value={member.phone || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'phone', e.target.value)}
              />
            </Grid>
            */}

            {/* Social Media */}
            {/*
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Twitter/X Handle (Optional)"
                value={member.twitter || ''}
                onChange={(e) => handleTeamMemberChange(member.id, 'twitter', e.target.value)}
                placeholder="@username"
              />
            </Grid>
            */}
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

  // Render institutional info section
  /*
  const renderInstitutionalInfo = () => (
    <Grid container spacing={3}>
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Compliance Officer"
          name="complianceOfficer"
          value={formData.complianceOfficer}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Compliance Email"
          name="complianceEmail"
          type="email"
          value={formData.complianceEmail}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Fund Administrator"
          name="fundAdministrator"
          value={formData.fundAdministrator}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Prime Broker"
          name="primeBroker"
          value={formData.primeBroker}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Auditor"
          name="auditor"
          value={formData.auditor}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12} sm={6}>
        <TextField
          fullWidth
          label="Legal Counsel"
          name="legalCounsel"
          value={formData.legalCounsel}
          onChange={handleInputChange}
        />
      </Grid>
      
      <Grid item xs={12}>
        <TextField
          fullWidth
          label="Regulatory Registrations"
          name="regulatoryRegistrations"
          value={formData.regulatoryRegistrations}
          onChange={handleInputChange}
          placeholder="e.g., SEC, FINRA, FCA, other regulatory bodies"
        />
      </Grid>
    </Grid>
  );
  */

  // Render track record section
  /*
  const renderTrackRecord = () => (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <TextField
          fullWidth
          multiline
          rows={6}
          label="Previous Performance History"
          name="previousPerformance"
          value={formData.previousPerformance}
          onChange={handleInputChange}
          placeholder="Briefly describe your historical performance, previous funds managed, or notable achievements"
        />
      </Grid>
      
      <Grid item xs={12}>
        <TextField
          fullWidth
          multiline
          rows={4}
          label="References"
          name="references"
          value={formData.references}
          onChange={handleInputChange}
          placeholder="References from investors, industry professionals, or service providers (optional)"
        />
      </Grid>
    </Grid>
  );
  */

  // Render the appropriate step content
  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderFundInfo();
      case 1:
        return renderTeamMembers();
      case 2:
        return renderPurposeSection();
      //case 3:
      //  return renderInstitutionalInfo();
      //case 4:
      //  return renderTrackRecord();
      default:
        return null;
    }
  };

  return (
    <Box className="fund-profile-form">
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" align="center" gutterBottom>
          Fund Profile
        </Typography>
        <Typography variant="subtitle1" color="textSecondary" align="center" paragraph>
          Create your fund's profile for investors and allocators
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
              {isProcessing ? 'Submitting...' : 'Submit Profile'}
            </Button>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default FundProfileForm;