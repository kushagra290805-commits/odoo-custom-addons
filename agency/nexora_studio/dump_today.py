def dump_today(env):
    import datetime
    today = datetime.date.today()
    logs = env['nexora.ai_audit_log'].search([('create_date', '>=', str(today))])
    print(f"Found {len(logs)} logs from today.")
    for l in logs:
        print(f"[{l.create_date}] Session: {l.builder_session_id.id} | Stage: {l.generation_stage}")
        print(f"Provider: {l.ai_provider}, Model: {l.ai_model_name}")

if "env" in locals():
    dump_today(env)
