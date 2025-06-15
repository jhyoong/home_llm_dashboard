# home_llm_dashboard
Personal dashboard to monitor my devices

1. Goals for this project:
    - **Monitoring Dashboard**: To keep track of the status and performance of all devices.
      - **Lightweight agents**: To be installed on each machine to report their status.
      - **Centralized dashboard**: To display the status of all agents in a single interface. This can be hosted on the debian machine. 
    - **Basic UI controls**: To start and stop llama-servers with preconfigured settings.
        - **Full load on VSCode extension assistant**: Utilize all available machines for a single model.
        - **Full load on Open WebUI usage**: Load a higher parameter (32B) model for the Open WebUI frontend.
        - **Sub-loads on Windows CPU**: Run small models on the WSL2 instance or directly on the windows machine with CPU limitations (16GB RAM).
        - **Unload and load models**: When not actively coding, swap to Ollama on the Mac Mini. Full-load models will be stopped, and only Ollama will run. This is on MacOS, installed via Homebrew. Best to have scripts prepared on each machine to start and stop the services.
        - **Notes**: Use `osascript -e 'tell app "Ollama" to quit'` to stop the Ollama service on MacOS. 
        - - `OLLAMA_HOST=0.0.0.0 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=2 OLLAMA_FLASH_ATTENTION=1 OLLAMA_MAX_QUEUE=20 ollama serve`
        - **Task models**: Lightweight models such as llama3.2:3b, or qwen2.5b 3b can be kept running on the debian machine.

2. What has been completed
    - Nothing yet

3. To check:
   1. Open Webui settings persist across reload? - yes, seems like it. 
   2. Ensure QwQ thinking bug is handled properly. - fixed with the custom params field. 
   3. DNS issues resolving custom domain. - fixed applied - needs testing
   4. QwQ looping when ending answers, some prompts don't get proper response endings.