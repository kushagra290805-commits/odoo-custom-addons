# Nexora Studio Custom Addons

This repository contains the custom Odoo addons and foundation architecture for **Nexora Studio**, an enterprise digital service agency operating system.

## Overview

Nexora Studio extends the Odoo 19 Community engine to provide a comprehensive agency and business platform. This custom-addons repository houses the domain-specific business logic, AI integration capabilities, and Universal Connector Platform that interface with the standard Odoo core. 

These custom addons are designed to be deployed alongside the Odoo engine, extending its standard modules (such as CRM, Project, and Contacts) with specialized workflows and dynamic capability resolution.

## Repository Structure

- gency/nexora_studio: The core Nexora Studio Odoo module containing the Enterprise Foundation, Source Framework, and Universal Connector Platform.
- shared/: Reusable, cross-project business modules (e.g., 	emplate_store).
- experimental/: Prototype, proof-of-concept, and experimental features under active research.
- 	hemes/: Odoo website, backend, and eCommerce theme modules for visual styling and UX enhancements.

## Architecture

The project is built on an Odoo-based domain and application layer, significantly extended by modern integration patterns:

- **Universal Connector Platform (Phase 26+):** A robust integration framework for connecting external tools and services to the Nexora ecosystem.
- **MCP Integration & Runtime:** Full implementation of the Model Context Protocol (MCP) to dynamically discover and execute external capabilities.
- **Source Framework:** Adaptable source registries and adapters (mcp_source_adapter.py) for handling disparate data inputs and provider strategies.
- **Configuration & Credential Resolution:** A secure runtime configuration flow that resolves provider credentials dynamically rather than relying on hardcoded values.

## MCP and Connector Integrations

The Model Context Protocol (MCP) is utilized to standardize how Nexora Studio discovers and interacts with external AI models, APIs, and tools. 

Instead of hardcoding integration logic, the Universal Connector Platform uses MCP Server configurations. Credentials required by these external providers are supplied securely through Odoo's internal database configuration mechanisms or environment variables. The MCP Connector Runtime dynamically resolves these credentials when initializing a connection, ensuring that secrets are never exposed in the source code or connection definition files.

## Development Prerequisites

- Python 3.10+
- PostgreSQL
- Odoo 19.0 Community Engine
- Dependencies listed in the Odoo core equirements.txt

## Local Development

1. **Odoo Engine Setup:** Clone or download the Odoo 19 Community engine to a local directory.
2. **Addon Linking:** Configure your Odoo instance to include this custom-addons repository in its ddons_path. This can be done via your local odoo.conf file or by creating a directory junction/symlink (e.g., linking custom-addons/agency/nexora_studio into the Odoo engine's ddons/ directory).
3. **Database Initialization:** Start the Odoo server and install the 
exora_studio module.

## Configuration and Secrets

**CRITICAL SECURITY GUIDELINES:**
- **Never commit** API keys, tokens, passwords, Personal Access Tokens (PATs), private keys, or credential files to this repository.
- Credentials must be supplied exclusively through the project's supported runtime/configuration mechanisms (e.g., Odoo database settings or secure environment variables).
- When writing tests or mock configurations, always use safe placeholders (e.g., __INJECT_VIA_NEXORA_MCP_CREDENTIAL__).
- Credentials must be resolved at runtime rather than hardcoded into source or configuration files committed to Git.

## Testing and Verification

The repository employs a multi-layered verification strategy:
- **Verification Scripts:** A comprehensive suite of standalone erify_*.py scripts (e.g., erify_mcp_runtime.py, erify_e2e.py) located in gency/nexora_studio/ to validate architectural compliance and runtime behavior.
- **Integration Tests:** End-to-end tests such as 	est_e2e_generation.py located in gency/nexora_studio/tests/.

## Documentation

- **Architectural Decision Records (ADRs):** Stored in gency/nexora_studio/docs/adr/.
- **Integration & Certification Reports:** Available in gency/nexora_studio/docs/reports/.
- **Walkthroughs:** System walkthroughs and status reports are maintained in the gency/nexora_studio/ directory.

## Contributing / Development Practices

- Preserve the existing Odoo-based and MCP-driven architecture.
- Add ADRs for significant architectural decisions.
- Strictly adhere to the Configuration and Secrets guidelines; validate that no secrets are included in your changes.
- Run the appropriate verification scripts before submitting changes for integration.

## License

This project is licensed under the LGPL-3 License (as specified in the module manifest).
