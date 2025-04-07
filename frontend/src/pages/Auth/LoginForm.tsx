import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useToast } from '../../hooks/useToast'; // Use toast for feedback

interface LoginFormProps {
  onLoginSuccess: () => void; // Callback on successful login
}

const LoginForm: React.FC<LoginFormProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null); // Local error state
  const { login } = useAuth();
  const { addToast } = useToast();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    setError(null); // Clear previous errors

    const success = await login({ username, password });

    setIsLoading(false);
    if (success) {
      addToast('success', 'Login successful!');
      onLoginSuccess(); // Trigger navigation or state change
    } else {
      // Error toast is likely handled by HttpClient/ErrorHandler,
      // but we can set a local error for the form field if needed.
      setError('Login failed. Please check your credentials.');
      // addToast('error', 'Login failed. Please check your credentials.');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Login</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div className="form-group"> {/* Use classes from index.css */}
        <label htmlFor="username">Username</label>
        <input
          type="text"
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>
      <div className="form-group">
        <label htmlFor="password">Password</label>
        <input
          type="password"
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
};

export default LoginForm;