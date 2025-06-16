// landing-app/scripts/check-env.js
const fs = require('fs');
const path = require('path');

const requiredEnvVars = [
  'REACT_APP_MAIN_APP_URL',
  'REACT_APP_API_BASE_URL',
  'REACT_APP_ENV'
];

const optionalEnvVars = [
  'REACT_APP_WS_URL',
  'REACT_APP_LANDING_URL',
  'REACT_APP_ENABLE_CONSOLE_LOGS',
  'REACT_APP_ENABLE_DEBUG_MODE'
];

function checkEnvironmentVariables() {
  console.log('🔧 Checking environment variables...\n');
  
  const missing = [];
  const present = [];
  
  // Check required variables
  requiredEnvVars.forEach(varName => {
    if (process.env[varName]) {
      present.push({ name: varName, value: process.env[varName], required: true });
    } else {
      missing.push({ name: varName, required: true });
    }
  });
  
  // Check optional variables
  optionalEnvVars.forEach(varName => {
    if (process.env[varName]) {
      present.push({ name: varName, value: process.env[varName], required: false });
    } else {
      missing.push({ name: varName, required: false });
    }
  });
  
  // Display results
  console.log('✅ Present environment variables:');
  present.forEach(({ name, value, required }) => {
    const badge = required ? '[REQUIRED]' : '[OPTIONAL]';
    console.log(`   ${badge} ${name}=${value}`);
  });
  
  if (missing.length > 0) {
    console.log('\n❌ Missing environment variables:');
    missing.forEach(({ name, required }) => {
      const badge = required ? '[REQUIRED]' : '[OPTIONAL]';
      console.log(`   ${badge} ${name}`);
    });
  }
  
  // Check for .env files
  console.log('\n📁 Environment files:');
  const envFiles = ['.env', '.env.local', '.env.development', '.env.production'];
  envFiles.forEach(file => {
    const filePath = path.join(process.cwd(), file);
    const exists = fs.existsSync(filePath);
    console.log(`   ${exists ? '✅' : '❌'} ${file}`);
  });
  
  // Determine if we can proceed
  const requiredMissing = missing.filter(({ required }) => required);
  if (requiredMissing.length > 0) {
    console.log('\n❌ Cannot proceed: Required environment variables are missing.');
    console.log('Please check your .env files and ensure all required variables are set.');
    process.exit(1);
  } else {
    console.log('\n✅ Environment validation passed!');
  }
}

checkEnvironmentVariables();