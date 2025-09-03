# Master File Comparison Tool with USE_PREV Functionality

## Overview

This tool compares master symbology files between two dates and categorizes changes based on importance. It includes special handling for columns that should use previous day's data when current data is empty.

## Key Features

### USE_PREV Functionality
- **Purpose**: Automatically backfill empty fields with previous day's data
- **Benefits**: Maintains data continuity and reduces false positives in change detection
- **Configuration**: Set via `USE_PREV` environment variable
- **Output**: Creates an updated master file with backfilled data

### Change Categorization
- **Primary Changes**: Important data changes that require investigation
- **Secondary Changes**: USE_PREV related changes (backfilled data, less critical)

### Directory Structure