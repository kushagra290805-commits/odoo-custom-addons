def dump_today_full(env):
    import datetime
    today = datetime.date.today()
    logs = env['nexora.ai_audit_log'].search([('create_date', '>=', str(today))], order='create_date asc')
    
    out = ["# AI Pipeline Validation Trace\n"]
    out.append(f"Found {len(logs)} AI invocations in the production pipeline.\n")
    
    for l in logs:
        out.append(f"### {l.generation_stage}")
        out.append(f"- **Provider:** {l.ai_provider}")
        out.append(f"- **Model:** {l.ai_model_name}")
        out.append(f"- **Prompt Size:** {len(l.prompt_content) if l.prompt_content else 0} characters")
        out.append(f"- **Response Size:** {len(l.response_content) if l.response_content else 0} characters")
        out.append(f"- **Token Usage:** {l.token_usage}")
        out.append(f"- **Latency:** {l.execution_duration:.2f}s")
        if l.failure_reason:
            out.append(f"- **Error:** {l.failure_reason}")
        if l.affected_files:
            out.append(f"- **Affected Files:** {l.affected_files}")
        out.append("\n")
        
    with open('D:/ODOO/custom-addons/agency/nexora_studio/ai_trace.md', 'w') as f:
        f.write('\n'.join(out))
    
    print("Trace written to ai_trace.md")

if "env" in locals():
    dump_today_full(env)
