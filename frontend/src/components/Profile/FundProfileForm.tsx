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
  Grid,
  MenuItem,
  IconButton,
  Divider,
  FormControl,
  InputLabel,
  Select,
  SelectChangeEvent
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useToast } from '../../hooks/useToast';
import './FundProfileForm.css';

// Define types
interface TeamMember {
  id: string;
  name: string;
  role: string;
  yearsExperience: string;
  education: string;
  previousEmployment: string;
  birthDate: string;
  linkedin?: string;
}

interface FundProfileData {
  // Fund Information
  fundName: string;
  legalStructure: string;
  location: string;
  yearEstablished: string;
  aumRange: string;
  investmentStrategy: string;
  
  // Team Members
  teamMembers: TeamMember[];
  
  // Institutional Information
  complianceOfficer: string;
  complianceEmail: string;
  fundAdministrator: string;
  primeBroker: string;
  auditor: string;
  legalCounsel: string;
  regulatoryRegistrations: string;
  
  // Track Record
  previousPerformance: string;
  references: string;
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
  const [formData, setFormData] = useState<FundProfileData>({
    // Fund Information
    fundName: '',
    legalStructure: '',
    location: '',
    yearEstablished: new Date().getFullYear().toString(),
    aumRange: '',
    investmentStrategy: '',
    
    // Team Members (initialize with one empty member)
    teamMembers: [{
      id: '1',
      name: '',
      role: '',
      yearsExperience: '',
      education: '',
      previousEmployment: '',
      birthDate: '',
      linkedin: ''
    }],
    
    // Institutional Information
    complianceOfficer: '',
    complianceEmail: '',
    fundAdministrator: '',
    primeBroker: '',
    auditor: '',
    legalCounsel: '',
    regulatoryRegistrations: '',
    
    // Track Record
    previousPerformance: '',
    references: ''
  });

  const steps = ['Fund Information', 'Team Members', 'Institutional Details', 'Track Record'];

  const handleNext = () => {
    if (activeStep === 0 && !validateFundInfo()) {
      return;
    }
    
    if (activeStep === 1 && !validateTeamMembers()) {
      return;
    }
    
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  // Separate handlers for input and select elements
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const handleSelectChange = (e: SelectChangeEvent) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const handleTeamMemberChange = (id: string, field: keyof TeamMember, value: string) => {
    setFormData({
      ...formData,
      teamMembers: formData.teamMembers.map(member => 
        member.id === id ? { ...member, [field]: value } : member
      )
    });
  };

  const addTeamMember = () => {
    const newId = Date.now().toString();
    setFormData({
      ...formData,
      teamMembers: [
        ...formData.teamMembers,
        {
          id: newId,
          name: '',
          role: '',
          yearsExperience: '',
          education: '',
          previousEmployment: '',
          birthDate: '',
          linkedin: ''
        }
      ]
    });
  };

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

  const validateFundInfo = () => {
    if (!formData.fundName.trim()) {
      addToast('error', 'Fund name is required');
      return false;
    }
    
    if (!formData.legalStructure) {
      addToast('error', 'Legal structure is required');
      return false;
    }
    
    if (!formData.location.trim()) {
      addToast('error', 'Fund location is required');
      return false;
    }
    
    return true;
  };

  const validateTeamMembers = () => {
    for (const member of formData.teamMembers) {
      if (!member.name.trim() || !member.role.trim()) {
        addToast('error', 'Name and role are required for all team members');
        return false;
      }
    }
    
    return true;
  };

  const handleSubmit = () => {
    // Here you would send the data to your backend API
    console.log('Submitting fund profile:', formData);
    
    // For demo purposes, store in localStorage
    try {
      localStorage.setItem('fundProfile', JSON.stringify(formData));
    } catch (error) {
      console.error('Error saving to localStorage:', error);
    }
    
    // Show success message
    addToast('success', 'Fund profile created successfully!');
    
    // Navigate back to the home page
    window.location.href = '/home';
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderFundInfo();
      case 1:
        return renderTeamMembers();
      case 2:
        return renderInstitutionalInfo();
      case 3:
        return renderTrackRecord();
      default:
        return null;
    }
  };

  const renderFundInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
        <TextField
          required
          fullWidth
          label="Fund Name"
          name="fundName"
          value={formData.fundName}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 12} as any}>
        <TextField
          required
          fullWidth
          label="Fund Location (City, Country)"
          name="location"
          value={formData.location}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
        <FormControl fullWidth required>
          <InputLabel>Legal Structure</InputLabel>
          <Select
            name="legalStructure"
            value={formData.legalStructure}
            onChange={handleSelectChange}
            label="Legal Structure"
          >
            {LEGAL_STRUCTURES.map(structure => (
              <MenuItem key={structure} value={structure}>
                {structure}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 3} as any}>
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
      <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 3} as any}>
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

  const renderTeamMembers = () => (
    <Box>
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
          
          <Grid container spacing={3}>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="First Name"
                value={member.name}
                onChange={(e) => handleTeamMemberChange(member.id, 'name', e.target.value)}
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="Last Name"
                value={member.name}
                onChange={(e) => handleTeamMemberChange(member.id, 'name', e.target.value)}
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 6} as any}>
              <TextField
                required
                fullWidth
                label="Role/Title"
                value={member.role}
                onChange={(e) => handleTeamMemberChange(member.id, 'role', e.target.value)}
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 3} as any}>
              <TextField
                fullWidth
                label="Years of Experience"
                type="number"
                value={member.yearsExperience}
                onChange={(e) => handleTeamMemberChange(member.id, 'yearsExperience', e.target.value)}
                inputProps={{ min: "0", max: "70" }}
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, size: 3} as any}>
              <TextField
                fullWidth
                label="Birth Date"
                type="date"
                value={member.birthDate}
                onChange={(e) => handleTeamMemberChange(member.id, 'birthDate', e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, size: 6} as any}>
              <TextField
                fullWidth
                label="Highest Education"
                value={member.education}
                onChange={(e) => handleTeamMemberChange(member.id, 'education', e.target.value)}
                placeholder="Degrees, institutions, certifications"
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, size: 6} as any}>
              <TextField
                fullWidth
                label="Current Employment"
                value={member.previousEmployment}
                onChange={(e) => handleTeamMemberChange(member.id, 'previousEmployment', e.target.value)}
                placeholder="Previous firms, positions, responsibilities"
              />
            </Grid>
            <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
              <TextField
                fullWidth
                label="LinkedIn Profile (Optional)"
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
    </Box>
  );

  const renderInstitutionalInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Compliance Officer"
          name="complianceOfficer"
          value={formData.complianceOfficer}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Compliance Email"
          name="complianceEmail"
          type="email"
          value={formData.complianceEmail}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Fund Administrator"
          name="fundAdministrator"
          value={formData.fundAdministrator}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Prime Broker"
          name="primeBroker"
          value={formData.primeBroker}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Auditor"
          name="auditor"
          value={formData.auditor}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
        <TextField
          fullWidth
          label="Legal Counsel"
          name="legalCounsel"
          value={formData.legalCounsel}
          onChange={handleInputChange}
        />
      </Grid>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
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

  const renderTrackRecord = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
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
      <Grid {...{component: "div", item: true, xs: 12} as any}>
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
            >
              Submit Profile
            </Button>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default FundProfileForm;