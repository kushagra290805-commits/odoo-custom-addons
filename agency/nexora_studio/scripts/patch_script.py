import re

with open(r'D:\ODOO\custom-addons\agency\nexora_studio\scripts\verify_phase18_2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Isolate Stage 1 in a savepoint block
stage_1_match = re.search(r"(AdapterClass = env\['nexora\.ai_adapter\.openrouter'\]\.__class__\s*\n\s*with patch\.object.*?)(# 8\. Stage 2 - Live Validation)", content, flags=re.DOTALL)
if stage_1_match:
    stage_1_code = stage_1_match.group(1)
    # indent it
    indented = "\n".join("    " + line if line.strip() else line for line in stage_1_code.split("\n"))
    new_stage_1 = (
        f"        try:\n"
        f"            with env.cr.savepoint():\n"
        f"{indented}"
        f"                raise ValueError('Rollback Stage 1')\n"
        f"        except ValueError as e:\n"
        f"            if str(e) == 'Rollback Stage 1':\n"
        f"                _logger.info('Mock Testing Cleaned Up Successfully (Rollback)')\n"
        f"            else:\n"
        f"                raise\n\n        "
    )
    new_stage_1 = new_stage_1.replace("AdapterClass = env['nexora.ai_adapter.openrouter'].__class__", "AdapterClass = env['nexora.ai_adapter.generic_openai'].__class__")
    # Also replace test_provider.unlink() inside indented block since we don't need it. We can just leave it since the rollback will undo it if we didn't mock openrouter, but since we are fetching openrouter, unlink will be rolled back.
    # Actually, if we unlink, it's rolled back. That's fine.
    content = content[:stage_1_match.start()] + new_stage_1 + content[stage_1_match.end(1):]

content = content.replace('phase18_2_validation_report.md', 'phase18_2_1_validation_report.md')
content = content.replace('# Phase 18.2 Validation Report', '# Phase 18.2.1 Validation Report')

with open(r'D:\ODOO\custom-addons\agency\nexora_studio\scripts\verify_phase18_2_1.py', 'w', encoding='utf-8') as f:
    f.write(content)
