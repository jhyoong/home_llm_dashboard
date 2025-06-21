#!/bin/bash
# Home LLM Dashboard - Dashboard Server Startup Script for Unix/Linux
# This script sets up and runs the dashboard web server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DASHBOARD_PORT=3030
DASHBOARD_HOST="0.0.0.0"

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

# Function to check system requirements
check_requirements() {
    print_header "🏠 Home LLM Dashboard - Server Startup"
    print_header "======================================"
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed."
        echo ""
        echo "Installation instructions:"
        echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv python3-full"
        echo "  CentOS/RHEL: sudo yum install python3 python3-pip python3-venv"
        echo "  macOS: brew install python3"
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
            # Check pip
            if ! command -v pip3 &> /dev/null; then
                print_warning "pip3 not found, trying pip..."
                if ! command -v pip &> /dev/null; then
                    print_error "pip is required but not installed."
                    echo "  Ubuntu/Debian: sudo apt install python3-pip"
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
}

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
            echo "  sudo apt update"
            echo "  sudo apt install python3-venv python3-full"
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
    print_status "Installing/updating dashboard dependencies..."
    
    if [ -f "requirements.txt" ]; then
        $PIP_CMD install -r requirements.txt
        if [ $? -eq 0 ]; then
            print_status "Dependencies installed successfully"
        else
            print_error "Failed to install dependencies"
            exit 1
        fi
    else
        print_error "requirements.txt not found!"
        print_warning "Installing basic dependencies manually..."
        $PIP_CMD install Flask Flask-SocketIO psutil requests
    fi
}

# Function to check port availability
check_port() {
    if command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$DASHBOARD_PORT "; then
            print_warning "Port $DASHBOARD_PORT is already in use!"
            print_warning "The dashboard might already be running, or another service is using this port."
            
            read -p "Do you want to continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_status "Startup cancelled by user"
                exit 1
            fi
        fi
    fi
}

# Function to create necessary directories
setup_directories() {
    print_status "Setting up directories..."
    
    # Create templates directory if it doesn't exist
    if [ ! -d "templates" ]; then
        print_warning "templates/ directory not found!"
        print_error "Please ensure dashboard.html and login.html are in the templates/ directory"
        exit 1
    fi
    
    # Create static directory if it doesn't exist
    mkdir -p static
    
    # Create logs directory
    mkdir -p logs
    
    print_status "Directory structure verified"
}

# Function to show configuration info
show_config() {
    print_status "Dashboard Configuration:"
    echo "  Host: $DASHBOARD_HOST"
    echo "  Port: $DASHBOARD_PORT"
    echo "  URL: http://$(hostname -I | awk '{print $1}'):$DASHBOARD_PORT"
    echo "  Local URL: http://localhost:$DASHBOARD_PORT"
    echo ""
    print_warning "Default login password: admin123"
    print_warning "Please change this in dashboard.py for production use!"
    echo ""
}

# Function to show firewall setup
show_firewall_info() {
    print_status "Firewall Configuration:"
    
    # Check if ufw is available
    if command -v ufw &> /dev/null; then
        if ufw status | grep -q "Status: active"; then
            print_warning "UFW firewall is active. You may need to allow port $DASHBOARD_PORT:"
            echo "  sudo ufw allow $DASHBOARD_PORT"
        fi
    fi
    
    # Check if firewalld is available  
    if command -v firewall-cmd &> /dev/null; then
        if systemctl is-active --quiet firewalld; then
            print_warning "firewalld is active. You may need to allow port $DASHBOARD_PORT:"
            echo "  sudo firewall-cmd --permanent --add-port=$DASHBOARD_PORT/tcp"
            echo "  sudo firewall-cmd --reload"
        fi
    fi
    
    echo ""
}

# Function to run dashboard
run_dashboard() {
    # Ensure we're using the correct Python command
    PYTHON_EXEC="${PYTHON_CMD:-python3}"
    
    print_status "Starting dashboard server..."
    print_status "Press Ctrl+C to stop the server"
    echo ""
    
    # Set up signal handling
    trap 'print_status "Shutting down dashboard server..."; exit 0' INT TERM
    
    # Run the dashboard with logging
    if [ "$1" = "--log" ]; then
        LOG_FILE="logs/dashboard_$(date +%Y%m%d_%H%M%S).log"
        print_status "Logging to: $LOG_FILE"
        $PYTHON_EXEC dashboard.py 2>&1 | tee "$LOG_FILE"
    else
        $PYTHON_EXEC dashboard.py
    fi
}

# Function to run as daemon
run_daemon() {
    print_status "Starting dashboard as background daemon..."
    
    # Ensure we're using the correct Python command
    PYTHON_EXEC="${PYTHON_CMD:-python3}"
    
    # Create PID file directory
    mkdir -p /tmp/llm-dashboard
    PID_FILE="/tmp/llm-dashboard/dashboard.pid"
    LOG_FILE="logs/dashboard_daemon.log"
    
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "Dashboard is already running (PID: $PID)"
            echo "Use '$0 --stop' to stop the dashboard"
            exit 1
        else
            print_warning "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    # Prepare environment for daemon
    DAEMON_ENV=""
    if [ -d "venv" ]; then
        # If using venv, we need to activate it in the daemon
        DAEMON_ENV="source $(pwd)/venv/bin/activate && "
    fi
    
    # Start daemon
    bash -c "${DAEMON_ENV}nohup $PYTHON_EXEC dashboard.py > '$LOG_FILE' 2>&1 & echo \$!" > "$PID_FILE"
    DASHBOARD_PID=$(cat "$PID_FILE")
    
    # Wait a moment and check if it started successfully
    sleep 3
    if ps -p "$DASHBOARD_PID" > /dev/null 2>&1; then
        print_status "Dashboard started successfully (PID: $DASHBOARD_PID)"
        print_status "Log file: $LOG_FILE"
        print_status "Use '$0 --stop' to stop the dashboard"
    else
        print_error "Dashboard failed to start. Check $LOG_FILE for details."
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to stop daemon
stop_daemon() {
    PID_FILE="/tmp/llm-dashboard/dashboard.pid"
    
    if [ ! -f "$PID_FILE" ]; then
        print_warning "PID file not found. Dashboard might not be running as daemon."
        
        # Try to find process anyway
        PIDS=$(pgrep -f "python3 dashboard.py" || true)
        if [ -n "$PIDS" ]; then
            print_status "Found dashboard processes: $PIDS"
            read -p "Kill these processes? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                kill $PIDS
                print_status "Dashboard processes terminated"
            fi
        else
            print_status "No dashboard processes found"
        fi
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        print_status "Stopping dashboard (PID: $PID)..."
        kill "$PID"
        
        # Wait for process to stop
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "Process didn't stop gracefully, forcing termination..."
            kill -9 "$PID"
        fi
        
        rm -f "$PID_FILE"
        print_status "Dashboard stopped successfully"
    else
        print_warning "Process not found, removing stale PID file"
        rm -f "$PID_FILE"
    fi
}

# Function to show status
show_status() {
    PID_FILE="/tmp/llm-dashboard/dashboard.pid"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_status "Dashboard is running (PID: $PID)"
            
            # Show resource usage if possible
            if command -v ps &> /dev/null; then
                echo "Resource usage:"
                ps -p "$PID" -o pid,ppid,pcpu,pmem,etime,cmd
            fi
            
            # Check if port is listening
            if command -v netstat &> /dev/null; then
                if netstat -tuln | grep -q ":$DASHBOARD_PORT "; then
                    print_status "Dashboard is listening on port $DASHBOARD_PORT"
                else
                    print_warning "Dashboard process running but port $DASHBOARD_PORT not listening"
                fi
            fi
        else
            print_warning "PID file exists but process not running"
            rm -f "$PID_FILE"
        fi
    else
        print_status "Dashboard is not running as daemon"
        
        # Check for any dashboard processes
        PIDS=$(pgrep -f "python3 dashboard.py" || true)
        if [ -n "$PIDS" ]; then
            print_warning "Found non-daemon dashboard processes: $PIDS"
        fi
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --install-only     Only install dependencies and setup"
    echo "  --no-deps          Skip dependency installation"
    echo "  --daemon           Run as background daemon"
    echo "  --stop             Stop daemon dashboard"
    echo "  --restart          Restart daemon dashboard"
    echo "  --status           Show dashboard status"
    echo "  --log              Run with console logging to file"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Default: Install dependencies, setup, and run dashboard interactively"
    echo ""
    echo "Examples:"
    echo "  $0                 # Start dashboard normally"
    echo "  $0 --daemon        # Start as background service"
    echo "  $0 --stop          # Stop background service"
    echo "  $0 --status        # Check if running"
    echo ""
}

# Main execution
main() {
    case "${1:-}" in
        --install-only)
            check_requirements
            if [ "$NEEDS_VENV" = true ]; then
                setup_venv
            fi
            install_dependencies
            setup_directories
            show_config
            ;;
        --daemon)
            check_requirements
            if [ "${2:-}" != "--no-deps" ]; then
                if [ "$NEEDS_VENV" = true ]; then
                    setup_venv
                fi
                install_dependencies
            fi
            setup_directories
            check_port
            show_config
            show_firewall_info
            run_daemon
            ;;
        --stop)
            stop_daemon
            ;;
        --restart)
            stop_daemon
            sleep 2
            main --daemon --no-deps
            ;;
        --status)
            show_status
            ;;
        --no-deps)
            check_requirements
            # If using venv, we still need to activate it even with --no-deps
            if [ -d "venv" ]; then
                print_status "Activating existing virtual environment..."
                source venv/bin/activate
                PYTHON_CMD="python"
            fi
            setup_directories
            check_port
            show_config
            show_firewall_info
            run_dashboard
            ;;
        --log)
            check_requirements
            if [ "$NEEDS_VENV" = true ]; then
                setup_venv
            fi
            install_dependencies
            setup_directories
            check_port
            show_config
            show_firewall_info
            run_dashboard --log
            ;;
        --help|-h)
            show_help
            ;;
        *)
            # Default: full setup and run
            check_requirements
            if [ "$NEEDS_VENV" = true ]; then
                setup_venv
            fi
            install_dependencies
            setup_directories
            check_port
            show_config
            show_firewall_info
            run_dashboard
            ;;
    esac
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi