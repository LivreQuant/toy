// Update src/pages/LandingPage.tsx
import React, { useEffect, useRef } from 'react';
import { Box } from '@mui/material';
import { useTheme } from '../contexts/ThemeContext';
import './LandingPage.css';

import {
  Header,
  Hero,
  FeaturesSection,
  HowItWorksSection,
  EnterpriseSection,
  StatsSection,
  TestimonialsSection,
  FaqSection, // Import the new component
  CtaSection,
  Footer
} from '../components/Landing';

const LandingPage: React.FC = () => {
  const { mode, toggleTheme } = useTheme();
  
  // Refs for scroll animation elements
  const heroRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const enterpriseRef = useRef<HTMLDivElement>(null);
  const faqRef = useRef<HTMLDivElement>(null); // Add a ref for FAQ section
  
  // Set up animations (unchanged from your code)
  useEffect(() => {
    // Intersection Observer for scroll animations
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animated-in');
        }
      });
    }, observerOptions);
    
    // Observe all animation elements
    const elements = [heroRef.current, featuresRef.current, enterpriseRef.current, faqRef.current];
    elements.forEach(el => el && observer.observe(el));
    
    return () => {
      elements.forEach(el => el && observer.unobserve(el));
    };
  }, []);

  return (
    <Box 
      sx={{ 
        bgcolor: mode === 'dark' ? '#121212' : '#f5f7fa',
        color: mode === 'dark' ? '#ffffff' : '#333333',
        minHeight: '100vh'
      }}
    >
      <Header />
      <Hero ref={heroRef} className="animate-on-scroll" />
      <FeaturesSection ref={featuresRef} className="animate-on-scroll" />
      <HowItWorksSection />
      <EnterpriseSection ref={enterpriseRef} className="animate-on-scroll" />
      {/*<TestimonialsSection />*/}
      <FaqSection ref={faqRef} className="animate-on-scroll" /> {/* Add FAQ section */}
      <CtaSection />
      <Footer />
    </Box>
  );
};

export default LandingPage;