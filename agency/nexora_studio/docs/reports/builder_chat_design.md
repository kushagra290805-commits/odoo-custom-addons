# Builder Chat Design

## Orchestration Flow
The BuilderChatEngine acts solely as an orchestrator for planning.
It is explicitly hardcoded **never** to write changes to a workspace directly. 

## Step-by-Step Workflow
1. User submits natural language prompt: *"Redesign my landing page"*
2. Chat Engine passes prompt and Active Version to IntelligenceEngine.
3. Impact assessment is generated.
4. Chat Engine passes impact to ChangePlanningEngine.
5. An immutable ExecutionPlan is generated and saved to the database.
6. Chat Engine stops and returns the plan_uuid.

This fulfills the strict "Human Approval Workflow" requirement. The UI must prompt the user to approve the plan before it is passed to the SafeExecutionEngine.
