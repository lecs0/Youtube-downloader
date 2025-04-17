# PowerShell script to install FFmpeg and Python requirements

# --- Configuration ---
$FFmpegDownloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$FFmpegInstallDir = "$env:ProgramFiles\FFmpeg"
$FFmpegBinDir = "$FFmpegInstallDir\bin"
$RequirementsFile = "requirements.txt"

# --- Helper Functions ---

function Test-AdminPrivilege {
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    (new-object System.Security.Principal.WindowsPrincipal $currentUser).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Add-ToPath {
    param(
        [string]$PathToAdd
    )
    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($CurrentPath -notlike "*$PathToAdd*") {
        [Environment]::SetEnvironmentVariable("Path", "$CurrentPath;$PathToAdd", "Machine")
        Write-Host "Successfully added '$PathToAdd' to the system PATH."
        Write-Host "You might need to restart your terminal or computer for the changes to take effect."
    } else {
        Write-Host "'$PathToAdd' is already in the system PATH."
    }
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination
    )
    try {
        Write-Host "Downloading '$Url' to '$Destination'..."
        Invoke-WebRequest -Uri $Url -OutFile $Destination
        Write-Host "Download complete."
        return $true
    } catch {
        Write-Error "Error downloading file: $_"
        return $false
    }
}

function Extract-ZipFile {
    param(
        [string]$ZipFilePath,
        [string]$ExtractPath
    )
    if (-not (Test-Path $ExtractPath -PathType Container)) {
        Write-Host "Creating directory '$ExtractPath'..."
        New-Item -Path $ExtractPath -ItemType Directory -Force | Out-Null
    }
    try {
        Write-Host "Extracting '$ZipFilePath' to '$ExtractPath'..."
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipFilePath, $ExtractPath)
        Write-Host "Extraction complete."
        return $true
    } catch {
        Write-Error "Error extracting ZIP file: $_"
        return $false
    }
}

# --- Main Script ---

# Check for Administrator privileges
if (-not (Test-AdminPrivilege)) {
    Write-Error "This script requires Administrator privileges to modify the system PATH. Please run it as administrator."
    exit 1
}

# --- Install FFmpeg ---
Write-Host "--- Installing FFmpeg ---"

# Check if FFmpeg is already in the PATH
if ($env:Path -notlike "*$FFmpegBinDir*") {
    # Download FFmpeg
    $ZipFileName = "ffmpeg.zip"
    $ZipFilePath = Join-Path $env:TEMP $ZipFileName
    if (Download-File -Url $FFmpegDownloadUrl -Destination $ZipFilePath) {
        # Create installation directory if it doesn't exist
        if (-not (Test-Path $FFmpegInstallDir -PathType Container)) {
            Write-Host "Creating FFmpeg installation directory '$FFmpegInstallDir'..."
            New-Item -Path $FFmpegInstallDir -ItemType Directory -Force | Out-Null
        }

        # Extract FFmpeg
        if (Extract-ZipFile -ZipFilePath $ZipFilePath -ExtractPath $FFmpegInstallDir) {
            # Add FFmpeg to PATH
            Add-ToPath -PathToAdd $FFmpegBinDir
        }
        # Clean up the downloaded zip file
        Remove-Item $ZipFilePath -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "FFmpeg is already installed and in the system PATH."
}

# --- Install Python Requirements ---
Write-Host "--- Installing Python Requirements ---"

# Check if requirements.txt exists in the same directory as the script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RequirementsFilePath = Join-Path $ScriptDir $RequirementsFile

if (Test-Path $RequirementsFilePath) {
    Write-Host "Found requirements file: '$RequirementsFilePath'"
    Write-Host "Attempting to install requirements using pip..."
    try {
        # Navigate to the script's directory to ensure pip finds the requirements.txt
        Set-Location -Path $ScriptDir
        pip install -r $RequirementsFile
        Write-Host "Successfully installed Python requirements from '$RequirementsFile'."
    } catch {
        Write-Error "Error installing Python requirements: $_"
        Write-Error "Make sure Python and pip are installed and in your system's PATH."
    } finally {
        # Go back to the original location (optional)
        # Set-Location -Path $PSScriptRoot
    }
} else {
    Write-Warning "Requirements file '$RequirementsFilePath' not found in the same directory as the script."
    Write-Host "Please ensure '$RequirementsFile' is in the correct location if you want to install Python dependencies."
}

Write-Host "--- Installation process completed ---"
Write-Host "Please restart your terminal or computer if you just installed FFmpeg."