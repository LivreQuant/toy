// src/components/Dashboard/FundProfileCard.tsx
import React from 'react';
import {
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography,
  useTheme
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import BusinessIcon from '@mui/icons-material/Business';
import PublicIcon from '@mui/icons-material/Public';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import StrategyIcon from '@mui/icons-material/Psychology';
import PeopleIcon from '@mui/icons-material/People';

interface FundProfileCardProps {
  fundProfile: any;
  onEditProfile: () => void;
}

const FundProfileCard: React.FC<FundProfileCardProps> = ({ fundProfile, onEditProfile }) => {
  const theme = useTheme();

  if (!fundProfile) {
    return (
      <Card 
        elevation={0} 
        sx={{ 
          mb: 3, 
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2
        }}
      >
        <CardContent sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h5" gutterBottom>Welcome to DigitalTrader</Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            To get started, create your fund profile to showcase your investment expertise.
          </Typography>
          <Button 
            variant="contained" 
            startIcon={<EditIcon />}
            onClick={onEditProfile}
            sx={{ mt: 2 }}
          >
            Create Fund Profile
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      elevation={0} 
      sx={{ 
        mb: 3, 
        overflow: 'hidden',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Header with fund name centered */}
      <Box 
        sx={{ 
          position: 'relative',
          py: 2.5, 
          px: 3,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: `linear-gradient(120deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
          color: 'white',
          textAlign: 'center'
        }}
      >
        <Typography 
          variant="h4" 
          component="h2" 
          sx={{ 
            fontWeight: 'bold',
            textShadow: '0px 1px 2px rgba(0,0,0,0.2)',
            mb: 0.5
          }}
        >
          {fundProfile?.fundName}
        </Typography>
        
        <Typography 
          variant="subtitle1" 
          sx={{ 
            fontWeight: 'medium',
            opacity: 0.9
          }}
        >
          {fundProfile?.legalStructure || ''} {fundProfile?.location ? `• ${fundProfile.location}` : ''}
        </Typography>
        
        <Button
          variant="contained"
          startIcon={<EditIcon />}
          onClick={onEditProfile}
          sx={{
            position: 'absolute',
            right: 16,
            top: '50%',
            transform: 'translateY(-50%)',
            backgroundColor: 'rgba(255,255,255,0.15)',
            backdropFilter: 'blur(10px)',
            '&:hover': {
              backgroundColor: 'rgba(255,255,255,0.25)',
            }
          }}
        >
          Edit Profile
        </Button>
      </Box>

      <CardContent sx={{ p: 0, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Grid container sx={{ flexGrow: 1 }}>
          <Grid {...{component: "div", item: true, xs: 12, sm: 7, md: 8} as any}>
            <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                {fundProfile?.yearEstablished && (
                  <Chip 
                    icon={<CalendarTodayIcon fontSize="small" />}
                    label={`Est. ${fundProfile.yearEstablished}`} 
                    size="small"
                    variant="outlined"
                  />
                )}
                {fundProfile?.aumRange && (
                  <Chip 
                    icon={<AccountBalanceIcon fontSize="small" />}
                    label={fundProfile.aumRange} 
                    size="small"
                    variant="outlined"
                  />
                )}
                {fundProfile?.teamMembers?.length > 0 && (
                  <Chip 
                    icon={<PeopleIcon fontSize="small" />}
                    label={`${fundProfile.teamMembers.length} Team Member${fundProfile.teamMembers.length !== 1 ? 's' : ''}`} 
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>

              <Box sx={{ mb: 3, flexGrow: 1 }}>
                <Box sx={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  mb: 1,
                  pb: 1,
                  borderBottom: `1px solid ${theme.palette.divider}`
                }}>
                  <StrategyIcon fontSize="small" sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Investment Strategy</Typography>
                </Box>
                <Typography 
                  variant="body1" 
                  color="text.secondary" 
                  paragraph 
                  sx={{ px: 1, mt: 1 }}
                >
                  {fundProfile?.investmentStrategy || 'No investment strategy defined yet.'}
                </Typography>
              </Box>

              {fundProfile?.profilePurpose?.length > 0 && (
                <Box sx={{ mt: 'auto' }}>
                  <Box sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    mb: 1,
                    pb: 1,
                    borderBottom: `1px solid ${theme.palette.divider}`
                  }}>
                    <Typography variant="h6">Investment Objectives</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
                    {fundProfile.profilePurpose.map((purpose: string) => (
                      <Chip 
                        key={purpose}
                        label={purpose.replace('_', ' ').split(' ').map((word: string) => 
                          word.charAt(0).toUpperCase() + word.slice(1)
                        ).join(' ')} 
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>
              )}
            </Box>
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sm: 5, md: 4} as any}>
            <Box 
              sx={{ 
                p: 3, 
                backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
                height: '100%',
                borderLeft: `1px solid ${theme.palette.divider}`
              }}
            >
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                mb: 2,
                pb: 1,
                borderBottom: `1px solid ${theme.palette.divider}`
              }}>
                <PeopleIcon fontSize="small" sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Management Team</Typography>
              </Box>
              
              {fundProfile?.teamMembers && fundProfile.teamMembers.length > 0 ? (
                <List disablePadding sx={{ mt: 2 }}>
                  {fundProfile.teamMembers.map((member: any) => (
                    <ListItem 
                      key={member.id} 
                      disablePadding 
                      sx={{ 
                        mb: 2, 
                        pb: 2,
                        borderBottom: fundProfile.teamMembers.indexOf(member) !== fundProfile.teamMembers.length - 1 
                          ? `1px solid ${theme.palette.divider}` 
                          : 'none'
                      }}
                    >
                      <ListItemAvatar>
                        <Avatar 
                          sx={{ 
                            bgcolor: theme.palette.primary.main,
                            width: 48,
                            height: 48
                          }}
                        >
                          {member.firstName?.charAt(0) || ''}{member.lastName?.charAt(0) || ''}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={
                          <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                            {member.firstName} {member.lastName}
                          </Typography>
                        }
                        secondary={
                          <>
                            <Typography variant="body2" component="span" color="text.primary">
                              {member.role}
                            </Typography>
                            {member.yearsExperience && (
                              <>
                                <br />
                                <Typography variant="caption" color="text.secondary">
                                  {member.yearsExperience} years experience
                                </Typography>
                              </>
                            )}
                            {member.education && (
                              <>
                                <br />
                                <Typography variant="caption" color="text.secondary">
                                  {member.education}
                                </Typography>
                              </>
                            )}
                          </>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Box sx={{ 
                  mt: 3, 
                  p: 3, 
                  textAlign: 'center', 
                  border: `1px dashed ${theme.palette.divider}`,
                  borderRadius: 1
                }}>
                  <Typography variant="body2" color="text.secondary">
                    No team members added yet. 
                    <br /><br />
                    Edit your fund profile to add team members.
                  </Typography>
                  <Button 
                    variant="outlined" 
                    size="small" 
                    onClick={onEditProfile}
                    startIcon={<EditIcon />}
                    sx={{ mt: 2 }}
                  >
                    Add Team Members
                  </Button>
                </Box>
              )}
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default FundProfileCard;