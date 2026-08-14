import json

def verify():
    with open('graphify-out/enriched_graph.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    links = data.get("links", [])
    
    # ORM Validation
    orm_links = [l for l in links if l.get('relation') == 'ORM_REFERENCE']
    env_ref_links = [l for l in links if l.get('relation') == 'ENV_REF']
    
    print(f"Total ORM_REFERENCE edges: {len(orm_links)}")
    print(f"Total ENV_REF edges: {len(env_ref_links)}")
    
    # XML Validation
    xml_links = [l for l in links if l.get('relation') == 'XML_REFERENCE']
    menu_actions = [l for l in links if l.get('relation') == 'MENU_ACTION']
    menu_parents = [l for l in links if l.get('relation') == 'MENU_PARENT']
    
    print(f"Total XML_REFERENCE edges (views/actions/crons): {len(xml_links)}")
    print(f"Total MENU_ACTION edges: {len(menu_actions)}")
    print(f"Total MENU_PARENT edges: {len(menu_parents)}")

if __name__ == "__main__":
    verify()
