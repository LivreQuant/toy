// src/components/Common/Footer.tsx
import React from 'react';
import { useLocation } from 'react-router-dom';
import './Footer.css';

const Footer: React.FC = () => {
  const location = useLocation();
  const year = new Date().getFullYear();
  
  // Don't show footer on login page
  if (location.pathname === '/login') {
    return null;
  }
  
  return (
    <footer className="app-footer">
      <div className="footer-content">
        <div className="copyright">
          &copy; {year} Trading Simulator
        </div>
        <div className="footer-links">
          <a href="#help">Help</a>
          <a href="#about">About</a>
          <a href="#terms">Terms</a>
        </div>
        <div className="version">
          v1.0.0
        </div>
      </div>
    </footer>
  );
};

export default Footer;