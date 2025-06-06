// landing-app/src/config/app-urls.ts
const getMainAppUrl = () => {
    // In production, main app will be at different URL
    // In development, main app runs on different port
    if (process.env.NODE_ENV === 'production') {
      return 'https://app.digitaltrader.com';
    }
    return 'http://localhost:3000'; // Your main-app dev port
  };
  
  export const mainAppRoutes = {
    login: `${getMainAppUrl()}/login`,
    signup: `${getMainAppUrl()}/signup`,
    home: `${getMainAppUrl()}/home`,
  };