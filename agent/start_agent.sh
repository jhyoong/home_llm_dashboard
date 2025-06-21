#!/bin/bash
# Home LLM Dashboard - Agent Startup Script for Unix/Linux/macOS
# This script sets up and runs the monitoring agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Header
print_header "🤖 Home LLM Dashboard - Agent Startup"
print_header "======================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed."
    echo ""
    echo "Installation instructions:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv python3-full"
    echo "  CentOS/RHEL: sudo yum install python3 python3-pip python3-venv"
    exit 1
fi

print_status "Python 3 found: $(python3 --version)"

# Check if we need to use virtual environment (externally managed environment)
NEEDS_VENV=false
if python3 -c "import sys; exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" 2>/dev/null; then
    print_status "Already in virtual environment"
    PIP_CMD="pip"
    PYTHON_CMD="python"
else
    # Test if we can install packages globally
    pip3 install --dry-run --quiet psutil 2>/dev/null || NEEDS_VENV=true
    
    if [ "$NEEDS_VENV" = true ]; then
        print_warning "System has externally managed Python environment"
        print_status "Will use virtual environment for package installation"
    else
        # Check if pip is available
        if ! command -v pip3 &> /dev/null; then
            print_warning "pip3 not found, trying pip..."
            if ! command -v pip &> /dev/null; then
                print_error "pip is required but not installed."
                exit 1
            else
                PIP_CMD="pip"
            fi
        else
            PIP_CMD="pip3"
        fi
        PYTHON_CMD="python3"
    fi
fi

# Function to setup virtual environment
setup_venv() {
    VENV_DIR="venv"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_status "Creating Python virtual environment..."
        
        # Check if python3-venv is installed
        if ! python3 -m venv --help &> /dev/null; then
            print_error "python3-venv is not installed."
            echo ""
            echo "Please install it with:"
            echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3-venv python3-full"
            echo "  CentOS/RHEL: sudo yum install python3-venv"
            echo ""
            exit 1
        fi
        
        python3 -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            print_error "Failed to create virtual environment"
            exit 1
        fi
        
        print_status "Virtual environment created successfully"
    else
        print_status "Using existing virtual environment"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Update pip within venv
    print_status "Updating pip in virtual environment..."
    pip install --upgrade pip
    
    # Update global variables to use venv pip and python
    PIP_CMD="pip"
    PYTHON_CMD="python"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing/updating dependencies..."
    
    if [ -f "requirements.txt" ]; then
        $PIP_CMD install -r requirements.txt
        print_status "Dependencies installed successfully"
    else
        print_warning "requirements.txt not found, installing basic dependencies..."
        $PIP_CMD install psutil requests
        
        # Offer to install optional GPU monitoring
        if command -v nvidia-smi &> /dev/null; then
            print_status "NVIDIA GPU detected, installing GPU monitoring support..."
            $PIP_CMD install pynvml || print_warning "Failed to install pynvml, GPU monitoring may not work"
        fi
    fi
}

# Function to create config if it doesn't exist
setup_config() {
    if [ ! -f "agent_config.ini" ]; then
        if [ -f "agent_config.ini.example" ]; then
            print_status "Creating agent_config.ini from example..."
            cp agent_config.ini.example agent_config.ini
        else
            print_status "Creating default configuration..."
            python3 agent.py --create-config
        fi
        
        print_warning "Please edit agent_config.ini with your dashboard server settings:"
        print_warning "  server_ip = YOUR_DASHBOARD_SERVER_IP"
        print_warning "  server_port = 3030"
        print_warning "  time_period = 5"
        echo ""
        read -p "Press Enter to continue after editing the config file..."
    else
        print_status "Configuration file found: agent_config.ini"
    fi
}

# Function to test connection
test_connection() {
    print_status "Testing connection to dashboard server..."
    if python3 agent.py --test-connection; then
        print_status "✅ Connection test successful!"
        return 0
    else
        print_error "❌ Connection test failed!"
        print_warning "Please check:"
        print_warning "  1. Dashboard server is running"
        print_warning "  2. server_ip in agent_config.ini is correct"
        print_warning "  3. Network connectivity between machines"
        print_warning "  4. Firewall settings allow port 3030"
        return 1
    fi
}

# Function to run agent
run_agent() {
    # Ensure we're using the correct Python command
    PYTHON_EXEC="${PYTHON_CMD:-python3}"
    
    print_status "Starting monitoring agent..."
    print_status "Press Ctrl+C to stop the agent"
    echo ""
    
    # Run the agent with proper signal handling
    trap 'print_status "Shutting down agent..."; exit 0' INT TERM
    
    $PYTHON_EXEC agent.py
}

# Main execution
main() {
    case "${1:-}" in
        --install-only)
            if [ "$NEEDS_VENV" = true ]; then
                setup_venv
            fi
            install_dependencies
            setup_config
            ;;
        --test-only)
            # If using venv, we need to activate it for testing
            if [ -d "venv" ]; then
                print_status "Activating existing virtual environment..."
                source venv/bin/activate
                PYTHON_CMD="python"
            fi
            test_connection
            ;;
        --no-deps)
            # If using venv, we still need to activate it even with --no-deps
            if [ -d "venv" ]; then
                print_status "Activating existing virtual environment..."
                source venv/bin/activate
                PYTHON_CMD="python"
            fi
            setup_config
            test_connection && run_agent
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install-only    Only install dependencies and setup config"
            echo "  --test-only       Only test connection to dashboard"
            echo "  --no-deps         Skip dependency installation"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Default: Install dependencies, setup config, test connection, and run agent"
            echo ""
            echo "Note: On systems with externally managed Python environments,"
            echo "      this script will automatically create and use a virtual environment."
            ;;
        *)
            # Default: full setup and run
            if [ "$NEEDS_VENV" = true ]; then
                setup_venv
            fi
            install_dependencies
            setup_config
            
            if test_connection; then
                echo ""
                run_agent
            else
                print_error "Cannot start agent due to connection issues"
                echo ""
                print_status "Run '$0 --test-only' after fixing the connection issues"
                exit 1
            fi
            ;;
    esac
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi