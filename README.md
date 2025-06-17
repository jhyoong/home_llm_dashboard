# home_llm_dashboard
Personal dashboard to monitor my devices

1. Goals for this project:
    - **Monitoring Dashboard**: To keep track of the status and performance of all devices.
      - This will be done by setting up a centralized dashboard, and running lightweight agents on all devices used for model inference.
      - **Lightweight agents**: To be installed on each machine to report their status.
        - This should be coded in Python. Future work can be done to refactor to use Go.
        - Success for this is:
          - Ability to run without issues on Windows, MacOs, Debian machines.
          - Ability to collect and send key metrics such as CPU usage, RAM usage, GPU usage, VRAM usage, and network traffic stats. 
          - Key metrics should only be sent if available - e.g if a device does not have GPU, it does not need to send GPU and VRAM status as it does not exist.
          - Key metrics should be sent every 5 seconds.
          - The agent should read from a config or env file to obtain certain variables like `SERVER_IP_ADDRESS` and `time_period`
            - `SERVER_IP_ADDRESS` : IP address to send the data to
            - `time_period` : the amount of time to wait in between sending updates. Defaults to 5 seconds.
      - **Centralized dashboard**: To display the status of all agents in a single interface. This can be hosted on the debian machine.
        - This should be a web application. It should be deployed on port 3030
        - Success for this is:
          - The web application must be able to receive data from the agents, and store them in the database in chronological order. Ensure that proper timestamps are present in the data.
          - Key metrics sent from the lightweight agents are displayed on the webpage.
            - These should be split clearly, from each field (CPU, RAM, GPU, VRAM, network traffic) per device.
            - These should also have interactable fields on the UI to change the granularity of the data shown. (1 day view, 2 day view, up to a week)
            - The database holding this should be set up to accept null or missing fields. The data can be set to have a TTL of 1 week.
          - There should be a basic password login check on the main page.
    - **Basic UI controls**: To start and stop llama-servers with preconfigured settings.
        - **VSCode extension assistant**: Utilize all available machines for a single model. This will be either a 14B or 32B model with higher context limits (16k-64k). Tool usage functionality is expected.
        - **Open WebUI usage**: Load a higher parameter/context model for the Open WebUI frontend. This will be either a 14B or 32B model with higher context limits (16k-64k).
        - **Unload and load models**: When not actively coding, swap to Ollama on the Mac Mini. Full-load models will be stopped, and only Ollama will run. This is on MacOS, installed via Homebrew. Best to have scripts prepared on each machine to start and stop the services.
        - **Notes**: Use `osascript -e 'tell app "Ollama" to quit'` to stop the Ollama service on MacOS. 
        - - `OLLAMA_HOST=0.0.0.0 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 OLLAMA_MAX_QUEUE=20 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve`
        - **Task models**: Lightweight models such as llama3.2:3b, or qwen2.5b 3b can be kept running on the debian machine.
        - These should be a simple API call from the frontend to trigger certain predefined scripts stored on the machine. It should only be a simple button click, with minimal logic on the frontend. The frontend only has to show the buttons(scripts) that can be run, and they should be greyed out when any script is running. A simple read-only textbox can be displayed for basic logs sent by the scripts on the backend.
        - The backend will call the scripts without any other form of inputs to ensure security. The base scripts will be hardcoded and only made availale in the debian machine. These scripts will use SSH to send the commands to run on the linked machines for loading either the models or RPC servers.
    - Ideally, the dashboard and basic UI controls will be on the same web application.

2. What has been completed
    - Nothing yet