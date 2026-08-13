#!/bin/bash

# ==============================================================================
# UNIFIED LOCAL AI MODEL SETUP FOR M4 MACBOOK PRO (48GB RAM)
# ==============================================================================
# This script automates the creation of a high-performance local AI image 
# generation environment. It configures a shared Hugging Face cache directory,
# installs ComfyUI (node-based UI) optimized for Apple Silicon MPS, and configures
# MFlux (command-line MLX tool), linking them cleanly to avoid duplicating files.
# ==============================================================================

# Color codes for clean interface output
NC='\0330m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'

echo -e "${CYAN}========================================================"
echo -e "Starting M4 Mac Local AI Environment Installation Script"
echo -e "Target Configuration: 48GB Unified Memory Optimization"
echo -e "========================================================${NC}\n"

# 1. PREREQUISITE CHECKING (Homebrew, Git LFS, Python)
echo -e "${YELLOW}[Step 1/5] Checking System Dependencies...${NC}"

if ! command -v brew &> /dev/null; then
    echo -e "${RED}Homebrew is not installed. Please install it first from https://brew.sh and re-run.${NC}"
    exit 1
fi

# Ensure Git LFS is installed to properly handle massive model checkpoints from HF
if ! command -v git-lfs &> /dev/null; then
    echo -e "${CYAN}Installing Git LFS via Homebrew...${NC}"
    brew install git-lfs
    git lfs install
else
    echo -e "${GREEN}✓ Git LFS is installed.${NC}"
fi

# Ensure Python 3.10+ is available
PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if (( $(echo "$PYTHON_VER < 3.10" | bc -l) )); then
    echo -e "${CYAN}Upgrading Python to a compatible version via Homebrew...${NC}"
    brew install python@3.11
    export PATH="/opt/homebrew/opt/python@3.11/bin:$PATH"
else
    echo -e "${GREEN}✓ Python $PYTHON_VER is ready.${NC}"
fi

# 2. CREATE A UNIFIED WORKSPACE
# Creating a central ecosystem prevents disk bloat when loading multiple HF weights
echo -e "\n${YELLOW}[Step 2/5] Creating Unified Storage Structure...${NC}"
WORKSPACE_DIR="$HOME/LocalAI_Workspace"
HF_CACHE_DIR="$WORKSPACE_DIR/HuggingFace_Cache"
COMFYUI_DIR="$WORKSPACE_DIR/ComfyUI"

mkdir -p "$WORKSPACE_DIR"
mkdir -p "$HF_CACHE_DIR"
mkdir -p "$WORKSPACE_DIR/Models/Checkpoints"
mkdir -p "$WORKSPACE_DIR/Models/UNet"
mkdir -p "$WORKSPACE_DIR/Models/VAE"

# Configure environment variable so huggingface-cli downloads to this shared storage location
export HF_HOME="$HF_CACHE_DIR"
if ! grep -q "HF_HOME" "$HOME/.zshrc"; then
    echo "export HF_HOME=\"$HF_CACHE_DIR\"" >> "$HOME/.zshrc"
    echo -e "${GREEN}Added HF_HOME environment mapping to ~/.zshrc${NC}"
fi

echo -e "${GREEN}✓ Workspace storage structural frame ready at: $WORKSPACE_DIR${NC}"

# 3. SET UP HUGGING FACE CLI & CORE ML PACKAGES
echo -e "\n${YELLOW}[Step 3/5] Setting Up Python Virtual Environment & CLI Frameworks...${NC}"
cd "$WORKSPACE_DIR" || exit

# Isolate python dependencies in a dedicated virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip and install standard machine learning tools optimized for Apple Silicon
pip install --upgrade pip
pip install huggingface_hub[cli] setuptools wheel

# Install MFlux (built exclusively on Apple's Native MLX Architecture)
echo -e "${CYAN}Installing Apple Silicon Optimized MLX Image Generator (mflux)...${NC}"
pip install mflux

echo -e "${GREEN}✓ Core CLI utilities and Python environment initialized.${NC}"

# 4. INSTALL COMFYUI WITH HARDWARE ACCELERATION
echo -e "\n${YELLOW}[Step 4/5] Deploying ComfyUI Pipeline...${NC}"
if [ ! -d "$COMFYUI_DIR" ]; then
    git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
fi

cd "$COMFYUI_DIR" || exit

# Install PyTorch with native Metal Performance Shaders (MPS) framework support
echo -e "${CYAN}Installing PyTorch Framework optimized for Apple Silicon GPU/MPS...${NC}"
pip install --pre torch torchvision torchaudio --index-url https://pytorch.org

# Install ComfyUI dependencies
pip install -r requirements.txt

# Bind ComfyUI's internal path pointers to your shared system folder using extra_model_paths.yaml
cat <<EOF > extra_model_paths.yaml
comfy:
    base_path: $WORKSPACE_DIR
    checkpoints: Models/Checkpoints
    unet: Models/UNet
    vae: Models/VAE
EOF

echo -e "${GREEN}✓ ComfyUI successfully configured for hardware-accelerated processing.${NC}"

# 5. CREATE EXECUTABLE LAUNCHERS AND UTILITIES
echo -e "\n${YELLOW}[Step 5/5] Generating Easy Launch Utilities...${NC}"

# Create run script for ComfyUI leveraging full MPS allocations without fallback performance penalties
cat <<EOF > "$WORKSPACE_DIR/start_comfyui.sh"
#!/bin/bash
cd "$WORKSPACE_DIR"
source venv/bin/activate
cd ComfyUI
# --force-fp16 utilizes your huge 48GB unified space cleanly while maximizing generation velocity
python main.py --force-fp16
EOF
chmod +x "$WORKSPACE_DIR/start_comfyui.sh"

# Create a guide utility tool to fetch unquantized native files directly from HF repos
cat <<EOF > "$WORKSPACE_DIR/download_model.sh"
#!/bin/bash
cd "$WORKSPACE_DIR"
source venv/bin/activate

echo "========================================================="
echo "Hugging Face Model Direct Ingestion Utility"
echo "========================================================="
echo "Example Repositories:"
echo "  - black-forest-labs/FLUX.1-dev (FLUX.1 Native)"
echo "  - stabilityai/stable-diffusion-xl-base-1.0 (SDXL)"
echo "========================================================="
read -p "Enter Hugging Face Repo ID: " REPO_ID
read -p "Enter Specific Filename (e.g., flux1-dev.safetensors) or leave blank for full repo: " FILE_NAME

if [ -z "\$FILE_NAME" ]; then
    huggingface-cli download \$REPO_ID --local-dir Models/Checkpoints
else
    huggingface-cli download \$REPO_ID \$FILE_NAME --local-dir Models/Checkpoints
fi
EOF
chmod +x "$WORKSPACE_DIR/download_model.sh"

echo -e "${GREEN}========================================================"
echo -e "Installation Complete! Setup Successfully Structured."
echo -e "========================================================${NC}"
echo -e "\n${CYAN}Quick Start Instructions:${NC}"
echo -e "1. Open Terminal and go to your workspace: ${YELLOW}cd ~/LocalAI_Workspace${NC}"
echo -e "2. Activate your environment: ${YELLOW}source venv/bin/activate${NC}"
echo -e "3. To run FLUX instantly via CLI: ${YELLOW}mflux-generate --model dev --prompt \"your prompt\"${NC}"
echo -e "4. To launch the Web UI workflow: ${YELLOW}./start_comfyui.sh${NC}"
echo -e "5. To grab a model from Hugging Face: ${YELLOW}./download_model.sh${NC}\n"