import time
env['nexora_studio.platform'].get_runtime()
time.sleep(10)
print('TOOLS:', list(env['nexora_studio.platform'].get_runtime().get_runtime('mcp_runtime').catalog._capabilities.keys()))
