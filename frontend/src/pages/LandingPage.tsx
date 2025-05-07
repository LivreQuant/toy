// src/pages/LandingPage.tsx
import React, { useEffect, useRef } from 'react';
import { Box, useTheme } from '@mui/material';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import './LandingPage.css';

import {
  Header,
  Hero,
  TrustedBySection,
  FeaturesSection,
  HowItWorksSection,
  StatsSection,
  TestimonialsSection,
  CtaSection,
  Footer
} from '../components/Landing';

const LandingPage: React.FC = () => {
  const theme = useTheme();
  const { mode, toggleTheme } = useCustomTheme();
  
  // Refs for scroll animation elements
  const heroRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const testimonialsRef = useRef<HTMLDivElement>(null);
  
  // Set up animations
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
    const elements = [heroRef.current, featuresRef.current, testimonialsRef.current];
    elements.forEach(el => el && observer.observe(el));
    
    return () => {
      elements.forEach(el => el && observer.unobserve(el));
    };
  }, []);

  return (
    <Box 
      sx={{ 
        bgcolor: 'background.default',
        color: 'text.primary',
        minHeight: '100vh'
      }}
    >
      <Header />
      <Hero ref={heroRef} className="animate-on-scroll" />
      {/*<TrustedBySection />*/}
      <FeaturesSection ref={featuresRef} className="animate-on-scroll" />
      <HowItWorksSection />
      {/*<StatsSection />*/}
      {/*<TestimonialsSection ref={testimonialsRef} className="animate-on-scroll" />*/}
      <CtaSection />
      <Footer />
    </Box>
  );
};

export default LandingPage;