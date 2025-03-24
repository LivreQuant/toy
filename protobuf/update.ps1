Write-Host "Starting protobuf update process..."

# Destination paths
$TS_DEST = "../frontend/src/protobufs"

# Create a cache timestamp file if it doesn't exist
$cacheTimestampFile = "gen/.last_gen_time"
New-Item -Path "gen" -ItemType Directory -Force -ErrorAction SilentlyContinue

# Check if generation is needed based on file changes
$regenerateNeeded = $false

# Get last generation timestamp
$lastGenTime = 0
if (Test-Path $cacheTimestampFile) {
    $lastGenTime = [long](Get-Content $cacheTimestampFile)
    Write-Host "Last generation timestamp: $lastGenTime"
} else {
    Write-Host "No cache timestamp found, will generate files"
    $regenerateNeeded = $true
}

# Check if proto files have changed
if (-not $regenerateNeeded) {
    # Add more paths to check
    $pathsToCheck = @("main")
    
    Write-Host "Checking for changes in the following directories:"
    foreach ($path in $pathsToCheck) {
        Write-Host " - $path"
        if (Test-Path $path) {
            $protoFiles = Get-ChildItem -Path $path -Filter "*.proto" -Recurse -ErrorAction SilentlyContinue
            Write-Host "   Found $($protoFiles.Count) proto files"
            
            foreach ($file in $protoFiles) {
                $fileTime = [long]($file.LastWriteTime.ToFileTime())
                Write-Host "   - $($file.FullName) (Last modified: $($file.LastWriteTime))"
                if ($fileTime -gt $lastGenTime) {
                    Write-Host "   - File changed: $($file.FullName) (File time: $fileTime > Last gen time: $lastGenTime)"
                    $regenerateNeeded = $true
                    break
                }
            }
        } else {
            Write-Host "   Directory does not exist"
        }
        
        if ($regenerateNeeded) {
            break
        }
    }
}

# Run buf commands only if needed
if ($regenerateNeeded) {
    Write-Host "Changes detected, running buf build..."
    buf build

    Write-Host "Running buf generate..."
    buf generate
    
    # Store current time
    [long](Get-Date).ToFileTime() | Out-File $cacheTimestampFile
    Write-Host "Generation timestamp updated"
} else {
    Write-Host "No changes detected, skipping buf generation"
}

# Create destination directories if they don't exist
New-Item -ItemType Directory -Force -Path "$TS_DEST"

# Clean existing files
Write-Host "Cleaning existing proto files..."
Remove-Item -Path "$TS_DEST/*.ts" -ErrorAction SilentlyContinue

# COPY FUNCTION
function Copy-ProtoFiles {
    param (
        [Parameter(Mandatory)]
        [string]$SourcePath,
        [Parameter(Mandatory)]
        [string]$DestinationPath,
        [string]$FileType = "*.ts",
        [string]$SuccessMessage = "Files copied successfully",
        [string]$NoFilesMessage = "No files found to copy",
        [array]$PathReplacements = @()
    )

    # Check if source files exist
    $sourceFiles = Get-ChildItem -Path "$SourcePath/$FileType" -ErrorAction SilentlyContinue
    if ($sourceFiles.Count -eq 0) {
        Write-Host $NoFilesMessage
        return
    }

    # Copy files first
    Copy-Item "$SourcePath/$FileType" -Destination $DestinationPath -ErrorAction SilentlyContinue
    if ($?) {
        Write-Host $SuccessMessage
        
        # Apply path replacements
        if ($PathReplacements.Count -gt 0) {
            $files = Get-ChildItem -Path $DestinationPath -Filter $FileType
            
            foreach ($file in $files) {
                $content = Get-Content -Path $file.FullName -Raw
                $modified = $false
                
                foreach ($replacement in $PathReplacements) {
                    $oldPath = $replacement[0]
                    $newPath = $replacement[1]
                    
                    # Check if pattern exists in content
                    if ($content.IndexOf($oldPath) -ge 0) {
                        $content = $content.Replace($oldPath, $newPath)
                        $modified = $true
                    }
                }
                
                if ($modified) {
                    Set-Content -Path $file.FullName -Value $content
                    Write-Host "  - Fixed import paths in $($file.Name)"
                }
            }
        }
    } else {
        Write-Host $NoFilesMessage
    }
}

# Copy Typescript files
$tsPathReplacements = @(
    @("../../main/", "../../protobufs/")
)

Copy-ProtoFiles -SourcePath "gen/ts/main" `
                -DestinationPath "../frontend/src/protobufs" `
                -FileType "*.ts" `
                -SuccessMessage "TypeScript service files copied successfully" `
                -NoFilesMessage "No TypeScript service files found" `
                -PathReplacements $tsPathReplacements
                
# Copy Python files
$pyPathReplacements = @(
    ,@("from main.services import", "from source.api import")
)
                
# Exchange Manager
Copy-ProtoFiles -SourcePath "gen/python/main" `
                -DestinationPath "../backend/order-service/source/api" `
                -FileType "exchange*.py" `
                -SuccessMessage "Python market data service files copied successfully" `
                -NoFilesMessage "No Python market data service files found" `
                -PathReplacements $pyPathReplacements

# Session Manager
Copy-ProtoFiles -SourcePath "gen/python/main" `
                -DestinationPath "../backend/session-manager-service/source/api" `
                -FileType "session*.py" `
                -SuccessMessage "Python market data service files copied successfully" `
                -NoFilesMessage "No Python market data service files found" `
                -PathReplacements $pyPathReplacements
                
# Exchange Manager
Copy-ProtoFiles -SourcePath "gen/python/main" `
                -DestinationPath "../backend/exchange-manager-service/source/api" `
                -FileType "exchange*.py" `
                -SuccessMessage "Python market data service files copied successfully" `
                -NoFilesMessage "No Python market data service files found" `
                -PathReplacements $pyPathReplacements
                
Write-Host "Protobuf update complete!"