import json

def get_registry_evidence(env):
    print("--- RAW ORM QUERY ---")
    try:
        records = env['nexora.capability_registry'].sudo().search_read([])
        print(f"Record count: {len(records)}")
        print("Contents:")
        print(json.dumps(records, indent=2, default=str))
    except Exception as e:
        print(f"Error querying registry: {e}")

if __name__ == "__main__":
    if 'env' in globals():
        get_registry_evidence(env)
    else:
        print("Must be run via odoo-bin shell")
