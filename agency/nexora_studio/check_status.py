def dump(env):
    rec = env['nexora.ai_model_catalog'].search([('model_id','=','openrouter/free')])
    print(f"Status: {rec.status}")

if "env" in locals():
    dump(env)
