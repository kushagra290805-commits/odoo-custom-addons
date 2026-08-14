param = env['ir.config_parameter'].sudo().get_param('nexora.workspace_root')
print(f"Current nexora.workspace_root = '{param}'")
