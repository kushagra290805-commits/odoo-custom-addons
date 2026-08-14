import time
import json
import os
import subprocess
import threading
import queue

def test_penpot_boot():
    print("--- PENPOT BOOT TRACE ---")
    registry_path = r"d:\ODOO\custom-addons\agency\nexora_studio\config\mcp_registry.json"
    with open(registry_path, 'r') as f:
        registry = json.load(f)
        
    penpot_config = registry['mcpServers']['penpot_mcp']
    
    cmd = [penpot_config['startup_command']] + penpot_config['startup_args']
    print(f"Process spawn: {cmd}")
    
    start = time.time()
    try:
        env = os.environ.copy()
        if 'environment_variables' in penpot_config:
            env.update(penpot_config['environment_variables'])
            
        process = subprocess.Popen(
            cmd,
            cwd=penpot_config['cwd'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nexora", "version": "1.0.0"}
            }
        }
        
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()
        
        q = queue.Queue()
        def reader():
            while True:
                line = process.stdout.readline()
                if not line: break
                q.put(line.strip())
                
        t = threading.Thread(target=reader)
        t.daemon = True
        t.start()
        
        print("Reading stdout lines:")
        while time.time() - start < 5.0:
            try:
                line = q.get(timeout=1.0)
                print(f"STDOUT: {line}")
                if "jsonrpc" in line and '"id":1' in line.replace(" ", ""):
                    print("JSON-RPC Initialize Response received!")
                    process.terminate()
                    return
            except queue.Empty:
                pass
                
        print("[TIMEOUT] Execution stalled at JSON-RPC 'initialize' stage. No valid JSON response.")
        process.terminate()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_penpot_boot()
