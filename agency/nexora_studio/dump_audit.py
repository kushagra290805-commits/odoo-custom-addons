import json
import sys

def dump_audit(env):
    logs = env['nexora.ai_audit_log'].search([], order='create_date desc', limit=10)
    print(f"Found {len(logs)} recent audit logs.")
    for l in logs:
        print(f"[{l.create_date}] Session: {l.builder_session_id.id} | Stage: {l.generation_stage}")
        print(f"Provider: {l.ai_provider}, Model: {l.ai_model_name}")
        print(f"Prompt Size: {len(l.prompt_content) if l.prompt_content else 0}")
        print(f"Response Size: {len(l.response_content) if l.response_content else 0}")
        print(f"Tokens: {l.token_usage}, Latency: {l.execution_duration}s")
        print(f"Error: {l.failure_reason}")
        print("-" * 40)

if "env" in locals():
    dump_audit(env)
