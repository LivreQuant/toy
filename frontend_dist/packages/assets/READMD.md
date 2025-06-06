
-----

# @trading-app/assets

A centralized package to manage and export static image asset URLs for the trading application suite.

## Overview

This package solves the problem of managing a large number of static images in a decoupled, scalable way. Instead of bloating the main application's source code with image files, this package acts as a centralized "source of truth" for image URLs.

For local development, it's designed to work with a simple, local static file server, perfectly mimicking a production CDN environment.

## Local Development Setup

To use this package effectively during local development, you need two things running simultaneously:

1.  Your main frontend application (e.g., running on `localhost:3000`).
2.  A local static asset server to serve the raw image files (e.g., running on `localhost:8080`).

Here is how to set up the local asset server.

### Step 1: Organize Your Image Files

This package contains the *paths*, but the image files themselves should live in a separate, dedicated folder on your machine, outside of any application's source code.

Create a folder structure like this:

```
/path/to/your/local-asset-storage/
└── images/
    ├── enterprise/
    ├── features/
    ├── hero/
    └── howItWorks/
```

### Step 2: Install The Local Server Tool

We use [`http-server`](https://www.google.com/search?q=%5Bhttps://www.npmjs.com/package/http-server%5D\(https://www.npmjs.com/package/http-server\)), a simple, zero-configuration Node.js package, to serve the images. Install it globally so you can run it from any directory.

```bash
npm install --global http-server
```

### Step 3: Run the Asset Server

Open a **new, separate terminal window**. Navigate to the root of your asset storage folder and run the following command to start the server.

```bash
# Example using a Windows path
http-server "C:/Users/samaral/dev/my-local-assets" -p 8080 --cors

# Example using a Mac/Linux path
http-server "/Users/samaral/dev/my-local-assets" -p 8080 --cors
```

**Command Breakdown:**

  * `http-server "/path/to/your/assets"`: Tells the server which folder to serve.
  * `-p 8080`: Runs the server on port `8080` to avoid conflicts with your main app.
  * `--cors`: **This is critical.** It allows your main app (from a different origin) to request images from this server. The browser will block requests without this.

Your asset server is now running. You can leave this terminal window open for your entire development session.

## Usage In a Frontend Application

Your main application can now import and use the image URLs. The `index.ts` file in this package is configured to point to your local asset server.

```javascript
// In your main application's component file

import { FEATURES_IMAGES, HERO_IMAGES } from '@trading-app/assets';

function MyComponent() {
  const dashboardImage = HERO_IMAGES.DASHBOARD;
  const lockImage = FEATURES_IMAGES.LOCK;

  // The 'dashboardImage' variable now holds the full URL:
  // 'http://localhost:8080/images/hero/dashboard.png'

  return (
    <div>
      <img src={dashboardImage} alt="Main Dashboard" />
      <img src={lockImage} alt="Security Feature" />
    </div>
  );
}
```

## Adding New Assets

1.  **Add the File:** Place your new image file into the appropriate sub-directory inside your local asset storage folder (e.g., `/path/to/your/local-asset-storage/images/hero/new-image.png`).
2.  **Update This Package:** Open the `src/index.ts` file in this (`@trading-app/assets`) package and add the new key and path to the appropriate exported object.
3.  **Re-publish (If Necessary):** If other developers need this new image, remember to version and re-publish this package to your package registry.

## Production Usage

This workflow makes moving to production simple.

1.  Upload the entire `images` directory to your production cloud storage (e.g., an Amazon S3 bucket).
2.  In this package, change the `IMAGE_BASE_PATH` variable in `src/index.ts` from `http://localhost:8080/images` to your production CDN URL (e.g., `https://assets.your-company.com/images`).
3.  Version and publish the updated package for your production build.