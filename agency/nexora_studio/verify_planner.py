import sys
import logging

def verify(env):
    print("Testing ProjectPlannerService.start_planning...")
    session = env['nexora.builder_session'].search([], limit=1)
    if not session:
        print("No builder session found, creating one...")
        session = env['nexora.builder_session'].create({
            'name': 'Test Session for Planner'
        })
    try:
        planner = env['nexora.project_planner_service']
        res = planner.start_planning(session.id, "Build a test website")
        print("Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if "env" in locals():
    verify(env)
