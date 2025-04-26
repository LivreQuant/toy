#!/bin/bash

echo "Starting protobuf update process..."

# Destination paths
TS_DEST="../frontend/src/protobufs"

# Create a cache timestamp file if it doesn't exist
CACHE_TIMESTAMP_FILE="gen/.last_gen_time"
mkdir -p "gen"

# Check if generation is needed based on file changes
REGENERATE_NEEDED=false

# Get last generation timestamp
LAST_GEN_TIME=0
if [ -f "$CACHE_TIMESTAMP_FILE" ]; then
    LAST_GEN_TIME=$(cat "$CACHE_TIMESTAMP_FILE")
    echo "Last generation timestamp: $LAST_GEN_TIME"
else
    echo "No cache timestamp found, will generate files"
    REGENERATE_NEEDED=true
fi

# Check if proto files have changed
if [ "$REGENERATE_NEEDED" = false ]; then
    # Add more paths to check
    PATHS_TO_CHECK=("main")
    
    echo "Checking for changes in the following directories:"
    for PATH_TO_CHECK in "${PATHS_TO_CHECK[@]}"; do
        echo " - $PATH_TO_CHECK"
        if [ -d "$PATH_TO_CHECK" ]; then
            # Find all proto files and check if any have been modified since last generation
            PROTO_FILES=$(find "$PATH_TO_CHECK" -name "*.proto" -type f)
            PROTO_COUNT=$(echo "$PROTO_FILES" | wc -l)
            echo "   Found $PROTO_COUNT proto files"
            
            for FILE in $PROTO_FILES; do
                # Get file modification time in seconds since epoch
                FILE_TIME=$(stat -c %Y "$FILE")
                FILE_DATE=$(date -d "@$FILE_TIME" "+%Y-%m-%d %H:%M:%S")
                echo "   - $FILE (Last modified: $FILE_DATE)"
                
                if [ "$FILE_TIME" -gt "$LAST_GEN_TIME" ]; then
                    echo "   - File changed: $FILE (File time: $FILE_TIME > Last gen time: $LAST_GEN_TIME)"
                    REGENERATE_NEEDED=true
                    break
                fi
            done
        else
            echo "   Directory does not exist"
        fi
        
        if [ "$REGENERATE_NEEDED" = true ]; then
            break
        fi
    done
fi

# Run buf commands only if needed
if [ "$REGENERATE_NEEDED" = true ]; then
    echo "Changes detected, running buf build..."
    buf build

    echo "Running buf generate..."
    buf generate
    
    # Store current time (seconds since epoch)
    date +%s > "$CACHE_TIMESTAMP_FILE"
    echo "Generation timestamp updated"
else
    echo "No changes detected, skipping buf generation"
fi

# Create destination directories if they don't exist
mkdir -p "$TS_DEST/services"

# Clean existing files
echo "Cleaning existing proto files..."
rm -f "$TS_DEST/services/"*.ts

# COPY FUNCTION
copy_proto_files() {
    SOURCE_PATH="$1"
    DESTINATION_PATH="$2"
    FILE_TYPE="$3"
    SUCCESS_MESSAGE="$4"
    NO_FILES_MESSAGE="$5"
    PATH_REPLACEMENTS="$6"
    
    # Check if source files exist
    SOURCE_FILES=$(find "$SOURCE_PATH" -name "$FILE_TYPE" -type f 2>/dev/null)
    if [ -z "$SOURCE_FILES" ]; then
        echo "$NO_FILES_MESSAGE"
        return
    fi

    # Copy files first
    cp "$SOURCE_PATH"/$FILE_TYPE "$DESTINATION_PATH" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "$SUCCESS_MESSAGE"
        
        # Apply path replacements
        if [ -n "$PATH_REPLACEMENTS" ]; then
            FILES=$(find "$DESTINATION_PATH" -name "$FILE_TYPE" -type f)
            
            for FILE in $FILES; do
                MODIFIED=false
                
                # Split the PATH_REPLACEMENTS string into pairs
                IFS=';' read -ra PAIRS <<< "$PATH_REPLACEMENTS"
                for PAIR in "${PAIRS[@]}"; do
                    IFS=':' read -ra REPLACEMENT <<< "$PAIR"
                    OLD_PATH="${REPLACEMENT[0]}"
                    NEW_PATH="${REPLACEMENT[1]}"
                    
                    # Check if pattern exists in content
                    if grep -q "$OLD_PATH" "$FILE"; then
                        sed -i "s|$OLD_PATH|$NEW_PATH|g" "$FILE"
                        MODIFIED=true
                    fi
                done
                
                if [ "$MODIFIED" = true ]; then
                    echo "  - Fixed import paths in $(basename "$FILE")"
                fi
            done
        fi
    else
        echo "$NO_FILES_MESSAGE"
    fi
}

# Copy Typescript files
#TS_PATH_REPLACEMENTS="../../main/services/:../../protobufs/"

#copy_proto_files "gen/ts/main/services" \
#                 "$TS_DEST" \
#                 "*.ts" \
#                 "TypeScript service files copied successfully" \
#                 "No TypeScript service files found" \
#                 "$TS_PATH_REPLACEMENTS"
                
# Copy Python files
PY_PATH_REPLACEMENTS="from main.services import:from source.api.grpc import"
                
# Order Manager
copy_proto_files "gen/python/main/services" \
                 "../backend/order-service/source/api/grpc" \
                 "order*.py" \
                 "Python market data service files copied to Order Service" \
                 "No Python market data service files found for Order Service" \
                 "$PY_PATH_REPLACEMENTS"

# Session Manager
copy_proto_files "gen/python/main/services" \
                 "../backend/session-service/source/api/grpc" \
                 "session*.py" \
                 "Python market data service files copied to Session Service" \
                 "No Python market data service files found for Session Service" \
                 "$PY_PATH_REPLACEMENTS"
                
# Exchange Manager
copy_proto_files "gen/python/main/services" \
                 "../backend/exchange-service/source/api/grpc" \
                 "order*.py" \
                 "Python market data service files copied to Exchange Manager Service" \
                 "No Python market data service files found for Exchange Manager Service" \
                 "$PY_PATH_REPLACEMENTS"

copy_proto_files "gen/python/main/services" \
                 "../backend/exchange-service/source/api/grpc" \
                 "session*.py" \
                 "Python market data service files copied to Exchange Manager Service" \
                 "No Python market data service files found for Exchange Manager Service" \
                 "$PY_PATH_REPLACEMENTS"
                
echo "Protobuf update complete!"