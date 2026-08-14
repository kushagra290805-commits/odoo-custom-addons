import ast
import os
import json

TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def check_bypasses(node, filepath, results):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
                if func_name in ["subprocess.run", "subprocess.Popen", "requests.get", "requests.post", "httpx.get", "httpx.post", "openai.ChatCompletion", "github.Github"]:
                    # Is it intentional/legacy/violation?
                    category = "architectural violation"
                    if "execution_sandbox_service.py" in filepath and "subprocess" in func_name:
                        category = "intentional"
                    if "transports.py" in filepath and "subprocess" in func_name:
                        category = "intentional"
                    if "gosom_provider.py" in filepath and "subprocess" in func_name:
                        category = "architectural violation (legacy adapter)"
                    results.append({
                        "file": os.path.relpath(filepath, TARGET_DIR),
                        "line": node.lineno,
                        "bypass": func_name,
                        "category": category
                    })

def analyze_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        bypasses = []
        for node in ast.walk(tree):
            check_bypasses(node, filepath, bypasses)
        return bypasses
    except Exception as e:
        return []

def run_audit():
    all_bypasses = []
    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if file.endswith(".py") and "verification" not in root:
                filepath = os.path.join(root, file)
                all_bypasses.extend(analyze_file(filepath))
    
    with open("bypass_report.json", "w", encoding='utf-8') as f:
        json.dump(all_bypasses, f, indent=2)
    print(f"Audit complete. Found {len(all_bypasses)} direct calls.")

if __name__ == "__main__":
    run_audit()
