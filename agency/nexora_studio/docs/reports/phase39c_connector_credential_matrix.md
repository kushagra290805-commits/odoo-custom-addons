# Phase 39C.1 — Credential Requirement Classification

## Classification Definitions
1. **NO-CREDENTIAL / PUBLICLY EXECUTABLE**: Explicitly verified in the current environment without credentials.
2. **OPTIONAL CREDENTIAL**: Provider may permit anonymous/public access, but the current environment has NOT proven execution without credentials.
3. **CREDENTIAL REQUIRED**: Provider requires authentication.
4. **UNKNOWN**: Insufficient evidence.

> **IMPORTANT:** OPTIONAL CREDENTIAL does NOT qualify a tool for the Phase 37 verified no-key execution set unless anonymous execution has been independently demonstrated in the current environment. Because `github_mcp` currently has `GITHUB_PERSONAL_ACCESS_TOKEN` configured, the Phase 39B GitHub execution must NOT be cited as anonymous/no-key proof.
## Summary Matrix

| Connector | Discovered Tools | No-Key Tools | Credential Required | Optional | Unknown |
|---|---:|---:|---:|---:|---:|
| github_mcp | 26 | 0 | 12 | 14 | 0 |
| context7_mcp | 2 | 0 | 0 | 0 | 2 |
| firecrawl_mcp | 27 | 0 | 27 | 0 | 0 |
| penpot_mcp | 4 | 0 | 4 | 0 | 0 |
| tavily_mcp | 5 | 2 | 3 | 0 | 0 |


## github_mcp
- **Name:** GitHub MCP Server
- **Transport Type:** stdio
- **Configured Credentials Present:** true
- **Credential Names Only:** ["GITHUB_PERSONAL_ACCESS_TOKEN"]
- **Discovered Tool Count:** 26

### `get_commit`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo, sha
- **Destructive Operation:** False

### `get_file_contents`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `get_label`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo, name
- **Destructive Operation:** False

### `get_latest_release`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `get_me`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** None
- **Destructive Operation:** False

### `get_release_by_tag`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner, repo, tag
- **Destructive Operation:** False

### `get_tag`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo, tag
- **Destructive Operation:** False

### `get_team_members`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** org, team_slug
- **Destructive Operation:** False

### `get_teams`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** None
- **Destructive Operation:** False

### `issue_read`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** method, owner, repo, issue_number
- **Destructive Operation:** False

### `list_branches`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_commits`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_issue_fields`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner
- **Destructive Operation:** False

### `list_issue_types`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner
- **Destructive Operation:** False

### `list_issues`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_pull_requests`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_releases`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_repository_collaborators`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `list_tags`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** owner, repo
- **Destructive Operation:** False

### `pull_request_read`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** method, owner, repo, pullNumber
- **Destructive Operation:** False

### `search_code`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** query
- **Destructive Operation:** False

### `search_commits`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** query
- **Destructive Operation:** False

### `search_issues`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** query
- **Destructive Operation:** False

### `search_pull_requests`
- **Credential Requirement:** OPTIONAL CREDENTIAL
- **Safe for no-key execution:** No
- **Reason:** Public repositories can be queried anonymously, but API limits apply. Not verified keyless.
- **Required Parameters:** query
- **Destructive Operation:** False

### `search_repositories`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** query
- **Destructive Operation:** False

### `search_users`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Documentation specifies these endpoints require authentication.
- **Required Parameters:** query
- **Destructive Operation:** False

## context7_mcp
- **Name:** Context7 Documentation MCP
- **Transport Type:** stdio
- **Configured Credentials Present:** false
- **Credential Names Only:** []
- **Discovered Tool Count:** 2

### `query-docs`
- **Credential Requirement:** UNKNOWN / REQUIRES PROVIDER VERIFICATION
- **Safe for no-key execution:** No
- **Reason:** Verification reports indicate OdooSecretsProvider is used, but nature of docs query could be public.
- **Required Parameters:** libraryId, query
- **Destructive Operation:** False

### `resolve-library-id`
- **Credential Requirement:** UNKNOWN / REQUIRES PROVIDER VERIFICATION
- **Safe for no-key execution:** No
- **Reason:** Verification reports indicate OdooSecretsProvider is used, but nature of docs query could be public.
- **Required Parameters:** query, libraryName
- **Destructive Operation:** False

## firecrawl_mcp
- **Name:** Firecrawl Extraction MCP
- **Transport Type:** stdio
- **Configured Credentials Present:** false
- **Credential Names Only:** []
- **Discovered Tool Count:** 27

### `firecrawl_agent`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** prompt
- **Destructive Operation:** False

### `firecrawl_agent_status`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** False

### `firecrawl_check_crawl_status`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** False

### `firecrawl_crawl`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** url
- **Destructive Operation:** False

### `firecrawl_developer_search`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** query
- **Destructive Operation:** False

### `firecrawl_extract`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** urls
- **Destructive Operation:** False

### `firecrawl_feedback`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** endpoint, jobId, rating
- **Destructive Operation:** False

### `firecrawl_interact`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** None
- **Destructive Operation:** True

### `firecrawl_interact_stop`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** scrapeId
- **Destructive Operation:** False

### `firecrawl_map`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** url
- **Destructive Operation:** False

### `firecrawl_monitor_check`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id, checkId
- **Destructive Operation:** False

### `firecrawl_monitor_checks`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** False

### `firecrawl_monitor_create`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** None
- **Destructive Operation:** True

### `firecrawl_monitor_delete`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** True

### `firecrawl_monitor_get`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** False

### `firecrawl_monitor_list`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** None
- **Destructive Operation:** False

### `firecrawl_monitor_run`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id
- **Destructive Operation:** False

### `firecrawl_monitor_update`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** id, body
- **Destructive Operation:** False

### `firecrawl_parse`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** filePath
- **Destructive Operation:** False

### `firecrawl_research_inspect_paper`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** paperId
- **Destructive Operation:** False

### `firecrawl_research_read_paper`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** paperId, question
- **Destructive Operation:** False

### `firecrawl_research_related_papers`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** seed_ids, intent
- **Destructive Operation:** False

### `firecrawl_research_search_github`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** query
- **Destructive Operation:** False

### `firecrawl_research_search_papers`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** query
- **Destructive Operation:** False

### `firecrawl_scrape`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** url
- **Destructive Operation:** False

### `firecrawl_search`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** query
- **Destructive Operation:** False

### `firecrawl_search_feedback`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** ADR-0059 specifies FIRECRAWL_API_KEY is required for the provider.
- **Required Parameters:** searchId, rating
- **Destructive Operation:** False

## penpot_mcp
- **Name:** Penpot Design MCP
- **Transport Type:** sse
- **Configured Credentials Present:** true
- **Credential Names Only:** ["PENPOT_API_KEY"]
- **Discovered Tool Count:** 4

### `execute_code`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Connector is configured with auth_location: query and requires PENPOT_API_KEY.
- **Required Parameters:** code
- **Destructive Operation:** False

### `export_shape`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Connector is configured with auth_location: query and requires PENPOT_API_KEY.
- **Required Parameters:** shapeId
- **Destructive Operation:** False

### `high_level_overview`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Connector is configured with auth_location: query and requires PENPOT_API_KEY.
- **Required Parameters:** None
- **Destructive Operation:** False

### `penpot_api_info`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Connector is configured with auth_location: query and requires PENPOT_API_KEY.
- **Required Parameters:** type
- **Destructive Operation:** False

## tavily_mcp
- **Name:** Tavily Web Research MCP
- **Transport Type:** stdio
- **Configured Credentials Present:** false
- **Credential Names Only:** []
- **Discovered Tool Count:** 5

### `tavily_search`
- **Credential Requirement:** NO-CREDENTIAL / PUBLICLY EXECUTABLE
- **Safe for no-key execution:** Yes
- **Reason:** Tavily explicitly logs keyless mode allows search and extract.
- **Required Parameters:** None
- **Destructive Operation:** False

### `tavily_extract`
- **Credential Requirement:** NO-CREDENTIAL / PUBLICLY EXECUTABLE
- **Safe for no-key execution:** Yes
- **Reason:** Tavily explicitly logs keyless mode allows search and extract.
- **Required Parameters:** None
- **Destructive Operation:** False

### `tavily_crawl`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Tavily logs indicate these tools require an API key.
- **Required Parameters:** None
- **Destructive Operation:** False

### `tavily_map`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Tavily logs indicate these tools require an API key.
- **Required Parameters:** None
- **Destructive Operation:** False

### `tavily_research`
- **Credential Requirement:** CREDENTIAL REQUIRED
- **Safe for no-key execution:** No
- **Reason:** Tavily logs indicate these tools require an API key.
- **Required Parameters:** None
- **Destructive Operation:** False

## Phase 37 Credential Policy
Phase 37 may use ONLY capabilities classified as:

**NO-CREDENTIAL / PUBLICLY EXECUTABLE**

and explicitly verified in the current environment.

Currently verified:
- `tavily_mcp.tavily_search`
- `tavily_mcp.tavily_extract`

The following must remain excluded until separately verified/configured:
- GitHub optional-credential tools
- Context7 tools
- Firecrawl tools
- Penpot tools
- all credential-required Tavily tools

**Verdict:** PHASE 39C.1 — CLASSIFICATION CONSISTENCY PASS