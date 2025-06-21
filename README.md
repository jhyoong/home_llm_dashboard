# Home LLM Dashboard
Personal dashboard to monitor my devices and control distributed AI inference systems

## 🎯 Project Goals

### 1. Monitoring Dashboard
- **Real-time device monitoring**: Track CPU, RAM, GPU, VRAM, and network traffic across all machines
- **Centralized dashboard**: Web-based interface displaying metrics from all devices
- **Historical data**: View performance trends with configurable time ranges (1 hour to 1 week)
- **Device status**: Online/offline indicators with automatic device discovery

### 2. Basic UI Controls
- **Model deployment controls**: Start and stop llama-servers with preconfigured settings
- **VSCode extension assistant**: Utilize all machines for distributed inference
- **Open WebUI support**: Load high-parameter models for web interface
- **Ollama integration**: Switch between full models and Ollama-only mode
- **Script automation**: One-click deployment and management

### 3. Use Cases
- **VSCode Assistant**: Distributed 14B-32B models with high context (16k-64k tokens)
- **Open WebUI**: High-parameter models for general conversational AI
- **Task Models**: Lightweight models (3B) for specific tasks
- **Resource optimization**: Dynamic model loading based on current needs

## 🏗️ Architecture

```
home_llm_dashboard/
├── agent/                      # Lightweight monitoring agents
│   ├── agent.py               # Cross-platform monitoring script
│   └── requirements.txt       # Agent dependencies
├── dashboard/                  # Web dashboard server
│   ├── dashboard.py           # Main Flask application
│   ├── templates/             # HTML templates
│   │   ├── dashboard.html     # Main dashboard interface
│   │   └── login.html         # Authentication page
│   └── requirements.txt       # Dashboard dependencies
└── README.md                  # This file
```

## 🚀 Quick Start

### Dashboard Server Setup (Debian Machine)

1. **Clone the repository**:
```bash
git clone <your-repo-url>
cd home_llm_dashboard/dashboard
```

2. **Install dependencies**:
```bash
pip3 install -r requirements.txt
```

3. **Start the dashboard**:
```bash
python3 dashboard.py
```

4. **Access the dashboard**:
   - Open browser to `http://your-debian-ip:3030`
   - Default password: `admin123` (change in production!)

### Device Agent Setup (All Machines)

1. **Copy agent files** to each machine you want to monitor

2. **Install agent dependencies**:
```bash
cd home_llm_dashboard/agent
pip3 install -r requirements.txt

# For NVIDIA GPU monitoring (optional):
pip3 install pynvml
```

3. **Create configuration**:
```bash
python3 agent.py --create-config
```

4. **Edit configuration** (`agent_config.ini`):
```ini
[agent]
server_ip = 192.168.50.210  # Your Debian machine IP
server_port = 3030
time_period = 5             # Send metrics every 5 seconds
```

5. **Test and run**:
```bash
# Test connection
python3 agent.py --test-connection

# Run agent
python3 agent.py
```

## 💻 Platform-Specific Setup

### macOS (Mac Mini M4 24GB)
```bash
brew install python3
pip3 install -r requirements.txt
python3 agent.py --create-config
# Edit config, then run agent
```

### Windows Machine (WSL2)
```bash
sudo apt update && sudo apt install python3 python3-pip
pip3 install -r requirements.txt pynvml  # pynvml for GPU monitoring
python3 agent.py --create-config
# Configure for Windows WSL2 environment
```

### Debian Machine
```bash
sudo apt update && sudo apt install python3 python3-pip
pip3 install -r requirements.txt
# Can monitor the dashboard server itself
```

## 🎛️ Control Scripts Configuration

The dashboard includes placeholder scripts for your AI infrastructure. To customize:

1. **Edit `ScriptManager` class** in `dashboard/dashboard.py`
2. **Replace placeholder SSH commands** with your actual deployment commands
3. **Set up SSH key authentication**

Example script customization:
```python
'vscode_assistant_start': {
    'name': 'Start VSCode Assistant (Full Load)',
    'description': 'Load coding model across all available machines',
    'commands': [
        'ssh macminijh@192.168.50.139 "cd ~/ai-inference/bin && ./llama-server -m ~/ai-inference/models/qwen2.5-coder-32b-instruct-q4_k_m.gguf --rpc 192.168.50.139:50053 --host 0.0.0.0 --port 8080 -ngl 60 &"',
        'ssh user@192.168.50.139 "CUDA_VISIBLE_DEVICES=0 ./rpc-server --host 0.0.0.0 --port 50053 &"'
    ]
}
```

## 📊 Features

### Dashboard Features
- **Real-time monitoring**: Live CPU, RAM, GPU, VRAM, Network metrics
- **Interactive charts**: Performance graphs with Chart.js
- **Multiple time ranges**: 1 hour to 1 week historical views
- **Device management**: Online/offline status with last-seen timestamps
- **WebSocket updates**: Real-time data without page refresh

### Control Panel Features
- **One-click deployment**: Start/stop models with predefined scripts
- **Real-time logs**: Watch script execution progress
- **Safety mechanisms**: Prevent multiple scripts running simultaneously
- **SSH integration**: Secure remote command execution

### Agent Features
- **Cross-platform**: macOS, Linux, Windows support
- **Lightweight**: Minimal resource footprint
- **Robust networking**: Auto-reconnection and error handling
- **Configurable**: File-based or environment variable configuration
- **GPU monitoring**: NVIDIA GPU support (optional)

## 🔧 Current Hardware Setup

1. **Mac Mini M4 24GB**: Primary inference node
   - Up to 18GB GPU allocation
   - Runs 27B-32B models with RPC distribution

2. **Windows Machine (32GB RAM, RTX 3070 8GB)**: Secondary compute
   - CPU inference via WSL2 (up to 16GB RAM)
   - GPU inference (up to 6-7GB VRAM)
   - RPC server for distributed processing

3. **Debian Machine**: Control center
   - Hosts dashboard and Open WebUI
   - Lightweight task models
   - Central orchestration point

## 📈 Performance Insights

Based on your testing logs:
- **Qwen2.5-Coder-32B**: 50% avg GPU (Mac), 25% GPU (RTX3070), 18-20Mbps network
- **QwQ-32B**: Similar resource usage with reasoning capabilities
- **Gemma-3-27B**: 30% avg load, good balance across machines

## 🔒 Security & Production

### Security Checklist
- [ ] Change default dashboard password
- [ ] Set up SSH key authentication
- [ ] Configure firewall rules
- [ ] Use HTTPS in production (reverse proxy)
- [ ] Regular dependency updates

### Production Deployment
```bash
# Dashboard as systemd service
sudo systemctl enable llm-dashboard
sudo systemctl start llm-dashboard

# Agent as systemd service on each machine
sudo systemctl enable llm-agent
sudo systemctl start llm-agent
```

## 🚦 Status

- ✅ **Dashboard server**: Complete with monitoring and controls
- ✅ **Device agents**: Cross-platform monitoring ready
- ✅ **Web interface**: Real-time dashboard with charts
- ✅ **SSH integration**: Script execution framework
- 🔄 **Script customization**: Placeholder scripts ready for your commands
- 🔄 **Production deployment**: Ready for systemd service setup

## 📝 Next Steps

1. **Deploy and test** the basic monitoring functionality
2. **Customize SSH scripts** with your actual llama-server commands  
3. **Set up SSH key authentication** between machines
4. **Configure systemd services** for production deployment
5. **Add monitoring alerts** (future enhancement)

## 🤝 Integration Notes

This dashboard integrates with your existing infrastructure:
- Monitors your current Mac Mini, Windows, and Debian setup
- Controls your existing llama-server and RPC server deployments
- Provides visibility into resource usage for optimal model selection
- Supports your VSCode extension and Open WebUI workflows

The system is designed to complement your current AI infrastructure while providing centralized monitoring and control capabilities.