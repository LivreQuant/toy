#!/bin/bash

echo "Building all packages..."

# Build packages in dependency order
cd packages/config && npm run build && cd ../..
cd packages/types-core && npm run build && cd ../..
cd packages/logging && npm run build && cd ../..

cd packages/utils && npm run build && cd ../..
cd packages/styles && npm run build && cd ../..
cd packages/toast && npm run build && cd ../..

cd packages/storage && npm run build && cd ../..
cd packages/auth && npm run build && cd ../..
cd packages/state && npm run build && cd ../..

cd packages/websocket && npm run build && cd ../..
cd packages/api && npm run build && cd ../..
cd packages/assets && npm run build && cd ../..

cd packages/ui && npm run build && cd ../..

echo "Building land, main, and book app..."
cd land-app && npm install && npm run build & cd ..
cd main-app && npm install && npm run build & cd ..
cd book-app && npm install && npm run build & cd ..

echo "All builds completed!"