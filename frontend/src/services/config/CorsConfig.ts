// src/services/config/CorsConfig.ts

// Function to set up CORS for local Kubernetes testing
export function setupLocalKubernetesCors(): void {
    // Only run in local Kubernetes mode
    if (!window.location.hostname.endsWith('.local')) {
      return;
    }
    
    console.log('Running in local Kubernetes mode - setting up CORS interception');
    
    // Patch fetch to add CORS headers
    const originalFetch = window.fetch;
    window.fetch = function(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
      const newInit = init || {};
      newInit.credentials = 'include';
      newInit.headers = {
        ...newInit.headers,
        'X-Requested-With': 'XMLHttpRequest',
      };
      
      return originalFetch.call(this, input, newInit);
    };
    
    // Set session storage flag to indicate we're in EKS/local K8s mode
    sessionStorage.setItem('eks-environment', 'true');
    
    console.log('CORS interception configured for local Kubernetes');
  }