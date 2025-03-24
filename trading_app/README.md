# Trading Platform - Local Development

## Overview

This repository contains a full-featured trading platform with microservices architecture:

- React frontend
- Authentication service
- Session management service
- Exchange simulator
- Order processing
- PostgreSQL and Redis for data storage

## Local Development Setup

### Prerequisites

- Windows with PowerShell
- Docker Desktop
- Minikube
- kubectl
- Git

### Getting Started

1. Clone this repository:
git clone https://github.com/yourusername/trading-platform.git
cd trading-platform
Copy
2. Set up the local Kubernetes environment:
```powershell
.\scripts\setup-local-env.ps1

Build service images:
powershellCopy.\scripts\build-images.ps1

Deploy all services:
powershellCopy.\scripts\deploy-services.ps1

Verify everything is running:
powershellCopykubectl get pods

Access the application at:

API: http://trading.local/api
WebSocket: ws://trading.local/ws



Default Test User

Username: testuser
Password: password123

Development Workflow
Updating a Service

Make changes to a service code (e.g., authorization-service)
Reset that service:
powershellCopy.\scripts\reset-service.ps1 -Service auth


Debugging

Load debugging tools:
powershellCopy. .\scripts\debug-commands.ps1

Check pods:
powershellCopyCheck-Pods

View logs:
powershellCopyGet-PodLogs -PodName <pod-name>

Forward a port:
powershellCopyPort-Forward -Service auth-service -LocalPort 8000 -ServicePort 8000


Frontend Development
For frontend development, create a .env.local file in the frontend directory:
CopyREACT_APP_API_URL=http://trading.local/api
REACT_APP_WS_URL=ws://trading.local/ws
REACT_APP_ENV=development
Then start the React development server:
Copycd frontend
npm install
npm start
Documentation

Kubernetes setup: k8s-README.md
Development scripts: scripts/README.md
API documentation: docs/API.md

Preparing for AWS Deployment
See docs/AWS-DEPLOYMENT.md for instructions on deploying to AWS EKS.
Copy
## Comprehensive Solution

This complete setup provides you with all the necessary files and scripts to:

1. Set up a local Kubernetes environment with Minikube
2. Build and deploy all services
3. Develop and test individual services
4. Reset services or the entire environment as needed
5. Debug issues through various tools and commands

The directory structure is organized logically, separating deployment configurations, storage definitions, secrets, and jobs. The PowerShell scripts automate common tasks, making the development workflow smooth and efficient.

By following this setup, you can effectively develop and test your trading platform locally before deploying to AWS EKS, saving time and costs in the process.