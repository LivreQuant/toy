// src/components/Landing/FaqSection.tsx
import React, { forwardRef } from 'react';
import { Box, Container, Typography, Accordion, AccordionSummary, AccordionDetails, useTheme } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { alpha } from '@mui/material/styles';

interface FaqSectionProps {
  className?: string;
}

// FAQ data
const faqItems = [
  {
    question: "What is DigitalTrader?",
    answer: "DigitalTrader is a trading simulation platform that provides a realistic, risk-free environment for investors to demonstrate and prove their investment aptitude. Our platform helps you build a verifiable track record that can help you stand out in the competitive investment industry."
  },
  {
    question: "How does the trading simulation work?",
    answer: "Our trading simulator offers an institutional-grade market simulation with accurate price dynamics, order book depth, and latency modeling. You can create and manage separate trading books for different strategies, execute trades via our professional dashboard, and generate comprehensive performance analytics to track your success."
  },
  {
    question: "Is my trading strategy protected?",
    answer: "Yes, we take intellectual property protection seriously. Your trading strategies and proprietary methodologies remain entirely yours. Our platform includes built-in compliance checks and risk limits to ensure trading strategies meet regulatory requirements while protecting your IP."
  },
  {
    question: "Can I use DigitalTrader for my job search?",
    answer: "Absolutely! Many portfolio managers and traders use our platform to build a verifiable track record that they can showcase to potential employers. Our performance metrics and detailed analytics provide concrete evidence of your trading capabilities."
  },
  {
    question: "Is there an API for algorithmic trading?",
    answer: "Yes, we offer robust REST and WebSocket APIs that allow you to connect your custom trading algorithms directly to our simulation platform. This enables you to test and demonstrate your algorithmic trading strategies in a realistic market environment."
  },
  {
    question: "How can asset managers use DigitalTrader to find talent?",
    answer: "Investment firms can use our enterprise solutions to identify potential hires based on verified trading performance rather than just interviews and resumes. Our platform provides access to a pool of investment talent with demonstrable track records verified through our simulation environment."
  }
];

const FaqSection = forwardRef<HTMLDivElement, FaqSectionProps>(({ className }, ref) => {
  const theme = useTheme();
  
  return (
    <Box
      id="faq"
      ref={ref}
      className={className}
      sx={{ 
        py: 10,
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(160deg, rgba(0, 0, 0, 0.3) 0%, rgba(0, 0, 0, 0.1) 100%)'
          : 'linear-gradient(160deg, #ffffff 0%, #f5f7fa 100%)',
      }}
    >
      <Container maxWidth="lg">
        <Box sx={{ textAlign: 'center', mb: 6 }}>
          <Typography 
            variant="h3" 
            component="h2" 
            gutterBottom
            sx={{ 
              fontWeight: 800,
              maxWidth: '800px',
              mx: 'auto'
            }}
          >
            Frequently Asked Questions
          </Typography>
          
          <Typography 
            variant="h6" 
            color="textSecondary" 
            sx={{ 
              maxWidth: '700px',
              mx: 'auto',
              mb: 2
            }}
          >
            Everything you need to know about our platform
          </Typography>
        </Box>
        
        <Box sx={{ maxWidth: '900px', mx: 'auto' }}>
          {faqItems.map((item, index) => (
            <Accordion 
              key={index}
              sx={{
                mb: 2,
                boxShadow: 'none',
                border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`,
                borderRadius: '8px !important',
                '&:before': { display: 'none' }, // Remove the default divider
                '&.Mui-expanded': {
                  boxShadow: `0 4px 20px ${alpha(theme.palette.primary.main, 0.15)}`,
                  borderColor: alpha(theme.palette.primary.main, 0.2),
                  mb: 2
                }
              }}
            >
              <AccordionSummary
                expandIcon={<ExpandMoreIcon color="primary" />}
                sx={{
                  backgroundColor: alpha(theme.palette.background.paper, 0.6),
                  borderRadius: '8px',
                  '&.Mui-expanded': {
                    borderBottomLeftRadius: 0,
                    borderBottomRightRadius: 0,
                  }
                }}
              >
                <Typography fontWeight="600" variant="h6">{item.question}</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ py: 3 }}>
                <Typography variant="body1">{item.answer}</Typography>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      </Container>
    </Box>
  );
});

export default FaqSection;