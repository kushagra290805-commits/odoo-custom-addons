def run(env):
    rec = env['res.config.settings'].browse(14)
    print(f"Record 14 default model ID: {rec.nexora_openrouter_default_model_id.id}")

if "env" in locals():
    run(env)
