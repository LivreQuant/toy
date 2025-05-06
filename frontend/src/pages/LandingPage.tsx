import React from 'react';
import { Link } from 'react-router-dom';
import './LandingPage.css';

const LandingPage: React.FC = () => {
  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-logo">
          <h1>Trading Platform</h1>
        </div>
        <div className="landing-actions">
          <Link to="/login" className="action-button login-button">Login</Link>
          <Link to="/signup" className="action-button signup-button">Sign Up</Link>
        </div>
      </header>
      
      <main className="landing-content">
        <section className="hero-section">
          <h2>Welcome to Open Trading Platform</h2>
          <p>A powerful platform for testing and executing trading strategies</p>
          <div className="hero-cta">
            <Link to="/signup" className="cta-button">Get Started</Link>
            <a href="#features" className="learn-more">Learn More</a>
          </div>
        </section>
        
        <section id="features" className="features-section">
          <h2>Platform Features</h2>
          <div className="feature-cards">
            <div className="feature-card">
              <div className="feature-icon">📈</div>
              <h3>Advanced Simulator</h3>
              <p>Test your strategies in a realistic market environment</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">📊</div>
              <h3>Real-time Data</h3>
              <p>Access to market data with minimal latency</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🔒</div>
              <h3>Secure Platform</h3>
              <p>Enterprise-grade security for your trading activities</p>
            </div>
          </div>
        </section>
      </main>
      
      <footer className="landing-footer">
        <p>&copy; {new Date().getFullYear()} Trading Platform. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default LandingPage;