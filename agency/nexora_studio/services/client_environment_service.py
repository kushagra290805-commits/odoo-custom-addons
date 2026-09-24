# -*- coding: utf-8 -*-
import json
import logging
import re
from odoo import models, api, _
from odoo.exceptions import ValidationError
import odoo

_logger = logging.getLogger(__name__)

class ClientEnvironmentService(models.AbstractModel):
    _name = 'nexora.client_environment_service'
    _description = 'Client Environment Service'

    def _sanitize_db_name(self, name):
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        if not name:
            name = 'client'
        return 'nexora_' + name[:20]

    @api.model
    def _agency_database_names(self):
        """Normalized set of agency database identities (fail closed).

        Odoo 19 declares ``db_name`` as a 'comma' option (tools/config.py:
        ``type='comma'``), so the canonical runtime representation is a
        LIST of strings (``-d nexora_studio`` → ``['nexora_studio']``).
        A plain string may also occur through programmatic assignment.
        Any other representation — or any non-string entry inside a
        collection — means the agency identity cannot be determined
        safely and the caller MUST be blocked (fail closed).
        """
        names = set()
        config_db = odoo.tools.config.get('db_name')
        if config_db is None or config_db == '' or config_db == []:
            # No config-side identity configured; the runtime cursor
            # remains the authoritative agency identity.
            pass
        elif isinstance(config_db, str):
            names.add(config_db)
        elif isinstance(config_db, (list, tuple, set, frozenset)):
            for item in config_db:
                if not isinstance(item, str) or not item.strip():
                    raise ValidationError(
                        _('Malformed db_name configuration entry (%r); '
                          'refusing unsafe database selection.') % (item,)
                    )
                names.add(item)
        else:
            raise ValidationError(
                _('Unexpected db_name configuration type %s; refusing '
                  'unsafe database selection.') % type(config_db).__name__
            )
        # The runtime cursor's database is always authoritative.
        names.add(self.env.cr.dbname)
        return names

    @api.model
    def _is_agency_database(self, db_name):
        """Fail-closed agency-DB detection (canonical safety owner).

        The candidate database name must be a single non-empty string.
        Any other representation — a list (the exact shape of Odoo 19's
        ``config['db_name']``), None, an empty string, or any unexpected
        type — is an ambiguous database identity and BLOCKS the
        operation instead of silently comparing unequal (the incident
        class fixed by this hardening).
        """
        if not isinstance(db_name, str) or not db_name.strip():
            raise ValidationError(
                _('Unsafe database identity %r; refusing to proceed with a '
                  'database operation.') % (db_name,)
            )
        return db_name in self._agency_database_names()

    def _encrypt_password(self, password):
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
        provider = OdooSecretsProvider(env=self.env)
        return provider._encrypt(password)

    def _decrypt_password(self, encrypted):
        from odoo.addons.nexora_studio.services.connector.credentials.odoo_secrets_provider import OdooSecretsProvider
        provider = OdooSecretsProvider(env=self.env)
        return provider._decrypt(encrypted)

    @api.model
    def create_environment(self, project_id, name=None):
        project = self.env['nexora.project'].browse(project_id).exists()
        if not project:
            raise ValidationError(_('Project not found.'))

        db_name = self._sanitize_db_name(name or project.name)
        # Phase 47.34.x safety hardening: the deterministic client naming
        # scheme (``nexora_`` + sanitized identifier) can collide with the
        # agency DB (e.g. identifier "studio" → "nexora_studio"). Reject
        # the collision at creation time — fail closed.
        if self._is_agency_database(db_name):
            raise ValidationError(
                _('The generated client database name %s collides with the '
                  'agency database; choose a different client/environment '
                  'name.') % db_name
            )
        existing = self.env['nexora.client_environment'].search([('db_name', '=', db_name)], limit=1)
        if existing:
            raise ValidationError(_('Database name already exists: %s') % db_name)

        env = self.env['nexora.client_environment'].create({
            'project_id': project.id,
            'name': name or project.name,
            'db_name': db_name,
            'status': 'draft',
        })
        return env

    @api.model
    def _provision(self, env_record):
        try:
            db_name = env_record.db_name
            # Phase 47.34.x safety hardening: defense-in-depth — the
            # agency DB can never be a client-DB creation target, no
            # matter how db_name was populated (guarded at creation and
            # by the model constraint; re-checked here as the last line
            # of defense before the Odoo primitive).
            if self._is_agency_database(db_name):
                raise ValidationError(
                    _('Refusing to create the client database: %s is the '
                      'agency database.') % db_name
                )
            admin_password = self.env['ir.config_parameter'].sudo().get_param(
                'nexora.client_db_admin_password', 'admin'
            )
            odoo.service.db.exp_create_database(db_name, False, 'en_US', admin_password)

            encrypted = self._encrypt_password(admin_password)
            env_record.write({
                'status': 'ready',
                'encrypted_admin_password': encrypted,
                'error_message': False,
            })
            _logger.info('Client database created: %s', db_name)
        except Exception as e:
            env_record.write({'status': 'failed', 'error_message': str(e)})
            # Make the failure state immediately durable: Odoo defers field
            # writes to flush time, and the re-raised exception can clear
            # the ORM cache before the surrounding transaction ends.
            env_record.flush_recordset()
            _logger.error('Provisioning failed for %s: %s', env_record.db_name, e)
            raise

    @api.model
    def _delete(self, env_record):
        try:
            db_name = env_record.db_name
            if self._is_agency_database(db_name):
                raise ValidationError(_('Cannot delete the agency database.'))
            odoo.service.db.exp_drop(db_name)
            env_record.write({'status': 'deleted', 'error_message': False})
            _logger.info('Client database deleted: %s', db_name)
        except Exception as e:
            env_record.write({'status': 'failed', 'error_message': str(e)})
            env_record.flush_recordset()
            _logger.error('Deletion failed for %s: %s', env_record.db_name, e)
            raise

    @api.model
    def provision(self, env_id):
        env_record = self.env['nexora.client_environment'].browse(env_id).exists()
        if not env_record:
            raise ValidationError(_('Environment not found.'))
        return env_record.action_provision()

    @api.model
    def delete(self, env_id):
        env_record = self.env['nexora.client_environment'].browse(env_id).exists()
        if not env_record:
            raise ValidationError(_('Environment not found.'))
        return env_record.action_delete()

    # ── Phase 47.34: Odoo module provisioning & capability mapping ───────────
    # This service remains the ONE canonical owner for client-environment
    # control-plane operations. Module provisioning reuses the same owner
    # (no second provisioning orchestrator). DB lifecycle ownership is NOT
    # taken over by the module layer: `status` is never modified here.

    @api.model
    def build_module_plan(self, capabilities):
        """Deterministically map capabilities to an approved Module Plan.

        Pure delegation to the platform-owned module policy; no LLM, no I/O.
        Unknown capabilities are rejected (ModulePolicyError).
        """
        from odoo.addons.nexora_studio.services.design.module_policy import (
            build_module_plan as policy_build_module_plan,
        )
        return policy_build_module_plan(capabilities)

    @api.model
    def provision_modules(self, env_id, capabilities):
        """Provision the approved module plan into the client Odoo DB.

        Chain: capabilities → deterministic module policy → approved plan →
        client environment → real Odoo module installation → verified result.

        Guarantees:
        - only allowlisted module names can reach the installation primitive
        - the agency DB can never be targeted
        - the client DB lifecycle state is never modified here
        - repeated requests are idempotent (installed modules are skipped)
        - failures are observable and recoverable (partial state preserved)
        """
        from odoo.addons.nexora_studio.services.design.module_policy import (
            ModulePolicyError,
        )

        env_record = self.env['nexora.client_environment'].browse(env_id).exists()
        if not env_record:
            raise ValidationError(_('Environment not found.'))

        # DB lifecycle must permit provisioning (DB exists and is ready).
        if env_record.status == 'deleted':
            raise ValidationError(
                _('Environment is deleted; module provisioning is not possible.')
            )
        if env_record.status != 'ready':
            raise ValidationError(
                _('Environment is not ready (status: %s); provision the client '
                  'database first.') % env_record.status
            )

        db_name = env_record.db_name
        # Explicit agency DB isolation proof — never target the agency DB.
        if self._is_agency_database(db_name):
            raise ValidationError(
                _('Refusing to provision modules: %s is the agency database.')
                % db_name
            )

        # The client database must physically exist (canonical Odoo check).
        if not odoo.service.db.exp_db_exist(db_name):
            raise ValidationError(
                _('Client database %s does not exist; module provisioning '
                  'is not possible.') % db_name
            )

        try:
            plan = self.build_module_plan(capabilities)
        except ModulePolicyError as exc:
            # Unknown/arbitrary capability: rejected, no installation, and
            # previously recorded provisioning state is preserved.
            _logger.warning('Module plan rejected: %s', exc)
            raise ValidationError(str(exc))

        # Serialize duplicate provisioning requests for the same environment
        # using the existing Odoo transaction/row-lock mechanism. A concurrent
        # duplicate blocks here, then re-reads actual module states and
        # completes as an idempotent no-op.
        self.env.cr.execute(
            "SELECT id FROM nexora_client_environment WHERE id = %s FOR UPDATE",
            [env_record.id],
        )
        if not self.env.cr.fetchall():
            raise ValidationError(_('Environment disappeared during provisioning.'))

        module_names = [entry['name'] for entry in plan['modules']]
        env_record.write({
            'module_provisioning_state': 'provisioning',
            'module_plan': json.dumps(plan, sort_keys=True),
            'module_provisioning_error': False,
        })

        if not module_names:
            # All capabilities explicitly unresolved — honest no-op.
            env_record.write({
                'module_provisioning_state': 'provisioned',
                'module_provisioning_result': json.dumps({
                    'installed': [],
                    'skipped': [],
                    'unresolved_capabilities': plan['unresolved_capabilities'],
                }, sort_keys=True),
            })
            return {
                'plan': plan,
                'installed': [],
                'skipped': [],
                'state': 'provisioned',
            }

        try:
            outcome = self._install_modules_in_client_db(db_name, module_names)
        except Exception as exc:
            # Determine the actual post-failure state (recoverability):
            # the client DB is preserved; already-installed modules remain.
            partial = False
            try:
                post_states = self._read_client_module_states(db_name, module_names)
                partial = any(
                    state == 'installed' for state in post_states.values()
                ) and not all(
                    state == 'installed' for state in post_states.values()
                )
            except Exception:
                post_states = {}
            env_record.write({
                'module_provisioning_state': 'partial' if partial else 'failed',
                'module_provisioning_error': str(exc),
                'module_provisioning_result': json.dumps({
                    'post_states': post_states,
                    'unresolved_capabilities': plan['unresolved_capabilities'],
                }, sort_keys=True) if post_states else False,
            })
            # Make the failure observable immediately (Odoo defers writes).
            env_record.flush_recordset()
            _logger.error('Module provisioning failed for %s: %s', db_name, exc)
            raise ValidationError(
                _('Module provisioning failed for %s: %s') % (db_name, exc)
            )

        state = 'provisioned' if not outcome['not_installed'] else 'partial'
        env_record.write({
            'module_provisioning_state': state,
            'module_provisioning_result': json.dumps({
                'installed': outcome['installed'],
                'skipped': outcome['skipped'],
                'post_states': outcome['post_states'],
                'unresolved_capabilities': plan['unresolved_capabilities'],
            }, sort_keys=True),
            'module_provisioning_error': False,
        })
        _logger.info(
            'Module provisioning complete for %s: installed=%s skipped=%s',
            db_name, outcome['installed'], outcome['skipped'],
        )
        return {
            'plan': plan,
            'installed': outcome['installed'],
            'skipped': outcome['skipped'],
            'state': state,
        }

    # ── Privileged installer (narrowly scoped) ──────────────────────────────
    # ONE execution owner. Never creates/deletes databases, never runs
    # generation, never manages AI/Console/frontend. Only allowlisted,
    # pre-verified module names may reach Registry.new (the same canonical
    # primitive `odoo-bin -i` and odoo.service.server use).

    @api.model
    def _install_modules_in_client_db(self, db_name, module_names):
        """Install approved modules in the client DB (idempotent, verified).

        :raise ValidationError: unavailable module (fails safely BEFORE any
            installation), module operation in progress, or a non-allowlisted
            module name (defense-in-depth — arbitrary names can never reach
            the Odoo primitive).
        """
        from odoo.addons.nexora_studio.services.design.module_policy import (
            is_module_allowed,
        )
        from odoo.modules.registry import Registry
        from odoo.api import Environment

        module_names = list(dict.fromkeys(module_names))
        if not module_names:
            return {
                'installed': [], 'skipped': [], 'not_installed': [],
                'pre_states': {}, 'post_states': {},
            }

        # Defense-in-depth: allowlist re-verification at the trust boundary.
        # Plain (untranslated) diagnostics: the privileged installer must not
        # depend on the translation machinery while operating on the client DB.
        disallowed = [n for n in module_names if not is_module_allowed(n)]
        if disallowed:
            raise ValidationError(
                'Module(s) %s are not part of the platform-owned allowlist; '
                'arbitrary module installation is forbidden.'
                % ', '.join(disallowed)
            )

        # Agency DB isolation proof, again, directly at the installer.
        if self._is_agency_database(db_name):
            raise ValidationError(
                'The agency database can never be a module installation target.'
            )

        registry = Registry(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})
            Module = env['ir.module.module']
            # Canonical availability refresh (same primitive the Odoo CLI uses).
            Module.update_list()
            records = Module.search([('name', 'in', module_names)])
            pre_states = {record.name: record.state for record in records}

        unavailable = sorted(set(module_names) - set(pre_states))
        if unavailable:
            # Fail safely BEFORE installing anything: no silent substitution,
            # no partial installation from an availability failure.
            raise ValidationError(
                'Approved module(s) %s are not available in the client Odoo '
                'runtime; provisioning failed safely.' % ', '.join(unavailable)
            )

        transient = sorted(
            name for name, state in pre_states.items()
            if state in ('to install', 'to upgrade', 'to remove')
        )
        if transient:
            raise ValidationError(
                'A module operation is in progress or was interrupted for '
                'module(s) %s; retry after the operation completes or the '
                'module states are reset.' % ', '.join(transient)
            )

        to_install = sorted(
            name for name, state in pre_states.items() if state != 'installed'
        )
        skipped = sorted(
            name for name, state in pre_states.items() if state == 'installed'
        )

        if to_install:
            # Canonical Odoo installation primitive (odoo/service/server.py:1552):
            # resolves legitimate dependencies, skips already-installed modules,
            # and rebuilds the client registry in-process.
            Registry.new(db_name, update_module=True, install_modules=tuple(to_install))

        post_states = self._read_client_module_states(db_name, module_names)
        not_installed = sorted(
            name for name, state in post_states.items() if state != 'installed'
        )
        return {
            'installed': to_install,
            'skipped': skipped,
            'not_installed': not_installed,
            'pre_states': pre_states,
            'post_states': post_states,
        }

    @api.model
    def _read_client_module_states(self, db_name, module_names):
        """Read verified ir.module.module states from the client DB."""
        from odoo.modules.registry import Registry
        from odoo.api import Environment

        if self._is_agency_database(db_name):
            raise ValidationError(
                'The agency database can never be inspected as a module '
                'provisioning target.'
            )
        registry = Registry(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})
            records = env['ir.module.module'].search([('name', 'in', list(module_names))])
            return {record.name: record.state for record in records}

    # ── Phase 47.35: Client API + authentication ────────────────────────────
    # The client-facing API credential and operations are owned by THIS
    # canonical environment service (no separate auth service, no second
    # token store). The BFF exposes thin client routes that delegate here
    # with the bearer token; the token — never a db_name, never an
    # environment id — IS the resolution key, so tenant crossing is
    # structurally impossible: there is no selector to tamper with.
    #
    # Error contract (stable, sanitized codes; never Odoo internals):
    #   CLIENT_AUTH_INVALID          -> 401 (missing/unknown/malformed token)
    #   CLIENT_AUTH_EXPIRED          -> 401 (past expiry)
    #   CLIENT_ENV_DELETED           -> 410
    #   CLIENT_ENV_NOT_READY         -> 503 (incl. corrupted agency-pointed envs: fail closed)
    #   CLIENT_CAPABILITY_UNAVAILABLE-> 403 (server-derived capability check)
    #   CLIENT_DB_UNAVAILABLE        -> 503 (client DB cannot be reached)
    #   CLIENT_REQUEST_INVALID       -> 422 (payload validation)
    #   CLIENT_BACKEND_ERROR         -> 502 (unexpected internal failure)

    CLIENT_API_TOKEN_PREFIX = 'nex_cli_'
    CLIENT_API_DEFAULT_TTL_DAYS = 365

    @api.model
    def issue_client_api_token(self, env_id, ttl_days=None):
        """Control plane: issue (or rotate) the client API token.

        :return: dict with the plaintext token (shown ONCE) and expiry.
        Only a SHA-256 hash is stored. Rotation invalidates the previous
        token immediately (single active token per environment).
        Privileged: agency system-group only (operators); the BFF never
        calls this — client routes only consume token-authenticated reads.
        """
        import hashlib
        import secrets
        from datetime import timedelta
        from odoo import fields as odoo_fields
        from odoo.exceptions import AccessError

        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError('Administrator privileges required to issue client API tokens.')

        env_record = self.env['nexora.client_environment'].browse(env_id).exists()
        if not env_record:
            raise ValidationError(_('Environment not found.'))

        try:
            ttl = int(ttl_days if ttl_days is not None else self.env['ir.config_parameter'].sudo().get_param(
                'nexora.client_api_token_ttl_days', self.CLIENT_API_DEFAULT_TTL_DAYS))
        except (TypeError, ValueError):
            raise ValidationError(_('Invalid token TTL.'))
        if ttl <= 0 or ttl > 3650:
            raise ValidationError(_('Token TTL must be between 1 and 3650 days.'))

        token = self.CLIENT_API_TOKEN_PREFIX + secrets.token_urlsafe(32)
        now = odoo_fields.Datetime.now()
        env_record.sudo().write({
            'client_api_token_hash': hashlib.sha256(token.encode('utf-8')).hexdigest(),
            'client_api_token_issued_at': now,
            'client_api_token_expires_at': now + timedelta(days=ttl),
            'client_api_token_active': True,
        })
        _logger.info(
            'Client API token issued for environment %s (env_id=%s, ttl_days=%s)',
            env_record.name, env_record.id, ttl,
        )
        # Plaintext is returned exactly ONCE; only the hash is stored.
        return {'token': token, 'expires_at': str(env_record.client_api_token_expires_at)}

    @api.model
    def revoke_client_api_token(self, env_id):
        """Control plane: revoke the active client API token."""
        from odoo.exceptions import AccessError

        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError('Administrator privileges required to revoke client API tokens.')

        env_record = self.env['nexora.client_environment'].browse(env_id).exists()
        if not env_record:
            raise ValidationError(_('Environment not found.'))
        env_record.sudo().write({
            'client_api_token_hash': False,
            'client_api_token_active': False,
            'client_api_token_expires_at': False,
        })
        _logger.info('Client API token revoked for environment %s (env_id=%s)',
                     env_record.name, env_record.id)
        return True

    @api.model
    def _resolve_client_token(self, token):
        """INTERNAL (underscore = not RPC-reachable): token → environment.

        :return: (env_record, None) on success or (None, error_code).
        """
        import hashlib
        from odoo import fields as odoo_fields

        if (not isinstance(token, str)
                or not token.startswith(self.CLIENT_API_TOKEN_PREFIX)
                or len(token) > 128):
            return None, 'CLIENT_AUTH_INVALID'
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        records = self.env['nexora.client_environment'].sudo().search([
            ('client_api_token_active', '=', True),
            ('client_api_token_hash', '=', digest),
        ], limit=1)
        if not records:
            return None, 'CLIENT_AUTH_INVALID'
        env_record = records[0]
        expires = env_record.client_api_token_expires_at
        if expires and expires < odoo_fields.Datetime.now():
            return None, 'CLIENT_AUTH_EXPIRED'
        return env_record, None

    @api.model
    def _client_error(self, code):
        return {'ok': False, 'error_code': code}

    @api.model
    def _client_authorized_capabilities(self, env_record):
        """Server-derived business capabilities (never client-claimed).

        Derived from the approved Module Plan (Phase 47.34); only
        capabilities with an approved module mapping are API-authorizable.
        """
        try:
            plan = json.loads(env_record.module_plan) if env_record.module_plan else {}
        except Exception:
            return []
        from odoo.addons.nexora_studio.services.design.module_policy import (
            CAPABILITY_MODULE_ALLOWLIST,
        )
        return [c for c in plan.get('capabilities', [])
                if c in CAPABILITY_MODULE_ALLOWLIST]

    @api.model
    def _client_api_prelude(self, token, capability=None):
        """Common authentication + environment validation for client ops.

        Order: authentication → environment state → agency-DB guard
        (fail closed, Phase 47.34.x owner reused) → capability
        authorization. Resolution uses ONLY the stored environment
        identity; no client-supplied db_name/environment id exists.
        """
        env_record, error = self._resolve_client_token(token)
        if env_record is None:
            _logger.info('client.auth_failed (error=%s)', error)
            return None, self._client_error(error)
        if env_record.status == 'deleted':
            return None, self._client_error('CLIENT_ENV_DELETED')
        if env_record.status != 'ready':
            return None, self._client_error('CLIENT_ENV_NOT_READY')
        if self._is_agency_database(env_record.db_name):
            # Corrupted/agency-pointed environment record: fail closed.
            _logger.error(
                'client.env_blocked: environment %s (env_id=%s) points at a '
                'reserved database; refusing client API access.',
                env_record.name, env_record.id,
            )
            return None, self._client_error('CLIENT_ENV_NOT_READY')
        if capability is not None and capability not in self._client_authorized_capabilities(env_record):
            _logger.info('client.authz_denied (env_id=%s, capability=%s)',
                         env_record.id, capability)
            return None, self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        _logger.info('client.authenticated (env_id=%s)', env_record.id)
        return env_record, None

    @api.model
    def _client_module_installed(self, db_name, module_name):
        """Verified module state in the client DB (defense in depth).

        The plan is intent; the installed state is reality — a capability
        is served only when its module is actually installed.
        """
        try:
            states = self._read_client_module_states(db_name, [module_name])
            return states.get(module_name) == 'installed'
        except Exception:
            return False

    def _client_registry_env(self, db_name):
        """Open a short-lived client-DB environment (context-managed cursor)."""
        from odoo.modules.registry import Registry
        from odoo.api import Environment
        registry = Registry(db_name)
        return registry, registry.cursor(), Environment

    @api.model
    def client_api_whoami(self, token):
        """Client API: authenticated identity + server-derived capabilities."""
        env_record, error = self._client_api_prelude(token)
        if error:
            return error
        return {
            'ok': True,
            'project': env_record.project_id.name,
            'environment': env_record.name,
            'capabilities': self._client_authorized_capabilities(env_record),
            # Deliberately NO db_name, no technical module names.
        }

    @api.model
    def client_api_health(self, token):
        """Client API: environment + client-backend health (sanitized)."""
        env_record, error = self._client_api_prelude(token)
        if error:
            return error
        db_ok = False
        try:
            db_ok = bool(odoo.service.db.exp_db_exist(env_record.db_name))
        except Exception:
            db_ok = False
        return {
            'ok': True,
            'environment_status': env_record.status,
            'module_provisioning_state': env_record.module_provisioning_state,
            'client_db_available': db_ok,
        }

    @api.model
    def client_api_list_products(self, token, limit=50):
        """Client API (capability: products): read products from the CLIENT DB."""
        env_record, error = self._client_api_prelude(token, capability='products')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'product'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            return self._client_error('CLIENT_REQUEST_INVALID')
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                records = cenv['product.product'].search(
                    [], limit=limit, order='write_date desc, id desc')
                products = [{
                    'id': r.id,
                    'name': r.display_name,
                    'price': r.list_price,
                    'sku': r.default_code or '',
                } for r in records]
        except Exception as exc:
            _logger.error('client.products_failed (env_id=%s): %s', env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        return {'ok': True, 'products': products}

    # ------------------------------------------------------------------
    # Phase 47.41: bounded commerce catalog contracts (capability:
    # products). Same prelude, same agency guard, same payload-whitelist
    # discipline as client_api_create_lead. No arbitrary model/method/
    # field/domain/db selectors exist on this path — the browser may only
    # express bounded catalog intent (query/category/sort/pagination),
    # never Odoo search primitives.
    # ------------------------------------------------------------------

    # Bounded sort vocabulary (platform data — never client-supplied SQL).
    _CATALOG_SORTS = {
        'relevance': 'write_date desc, id desc',
        'name_asc': 'name asc, id asc',
        'name_desc': 'name desc, id desc',
        'price_asc': 'list_price asc, id asc',
        'price_desc': 'list_price desc, id desc',
    }

    @api.model
    def _client_catalog_domain(self, payload):
        """Deterministic bounded domain for the catalog operation.

        Returns (domain, error_code). Only literal Odoo terms built from
        validated scalars — a client can never inject a domain leaf.
        """
        domain = []
        query = payload.get('query')
        if query:
            # Bounded substring search on Odoo's own name search field set.
            domain.append(('name', 'ilike', query))
        category_id = payload.get('category_id')
        if category_id is not None:
            domain.append(('categ_id', '=', category_id))
        if payload.get('in_stock_only'):
            domain.append(('type', '=', 'consu'))
        return domain, None

    @api.model
    def _client_catalog_projection(self, record):
        """Explicit product projection — bounded fields only (Phase 47.41).

        Demo/rating metadata is clearly separated from real Odoo facts:
        nothing here fabricates reviews. `rating_*` fields are absent
        unless the client DB genuinely carries them.
        """
        description = record.description_sale or record.description or ''
        image = ''
        try:
            if record.image_1920:
                # Attachment-backed image route (same-origin BFF route,
                # Phase 47.41) — never a giant base64 payload.
                image = '/api/v1/client/products/%s/image' % record.id
        except Exception:
            image = ''
        return {
            'id': record.id,
            'name': record.display_name,
            'sku': record.default_code or '',
            'price': record.list_price,
            'compare_at_price': None,
            'category_id': record.categ_id.id if record.categ_id else None,
            'category': record.categ_id.display_name if record.categ_id else '',
            'description': description[:500] if description else '',
            'in_stock': True,
            'image': image,
        }

    @api.model
    def _client_catalog_params(self, payload):
        """Validate the bounded catalog parameter contract.

        Returns (params dict, error_code). Every parameter is optional;
        every value is bounded and type-checked (no domains, no SQL, no
        model/method names can pass through these keys).
        """
        params = {
            'query': '', 'category_id': None, 'sort': 'relevance',
            'limit': 24, 'offset': 0, 'in_stock_only': False,
        }
        if payload.get('query') is not None:
            query = payload.get('query')
            if not isinstance(query, str) or len(query) > 80:
                return None, 'CLIENT_REQUEST_INVALID'
            params['query'] = query.strip()
        if payload.get('category_id') is not None:
            try:
                params['category_id'] = int(payload.get('category_id'))
            except (TypeError, ValueError):
                return None, 'CLIENT_REQUEST_INVALID'
        if payload.get('sort') is not None:
            sort = payload.get('sort')
            if sort not in self._CATALOG_SORTS:
                return None, 'CLIENT_REQUEST_INVALID'
            params['sort'] = sort
        if payload.get('limit') is not None:
            try:
                limit = int(payload.get('limit'))
            except (TypeError, ValueError):
                return None, 'CLIENT_REQUEST_INVALID'
            if limit < 1 or limit > 100:
                return None, 'CLIENT_REQUEST_INVALID'
            params['limit'] = limit
        if payload.get('offset') is not None:
            try:
                offset = int(payload.get('offset'))
            except (TypeError, ValueError):
                return None, 'CLIENT_REQUEST_INVALID'
            if offset < 0 or offset > 10000:
                return None, 'CLIENT_REQUEST_INVALID'
            params['offset'] = offset
        if payload.get('in_stock_only') is not None:
            params['in_stock_only'] = bool(payload.get('in_stock_only'))
        return params, None

    @api.model
    def client_api_catalog(self, token, payload):
        """Client API (capability: products): bounded catalog query.

        Search/category/sort/pagination with an explicit projection and a
        truthful total count. The resolved client environment comes from
        the token (server-derived); no db selector exists.
        """
        env_record, error = self._client_api_prelude(token, capability='products')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'product'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        if not isinstance(payload, dict):
            return self._client_error('CLIENT_REQUEST_INVALID')
        params, error = self._client_catalog_params(payload)
        if error:
            return self._client_error(error)
        domain, error = self._client_catalog_domain(params)
        if error:
            return self._client_error(error)
        order = self._CATALOG_SORTS[params['sort']]
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                Product = cenv['product.product']
                total = Product.search_count(domain)
                records = Product.search(
                    domain, limit=params['limit'],
                    offset=params['offset'], order=order)
                products = [self._client_catalog_projection(r)
                            for r in records]
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.error('client.catalog_failed (env_id=%s): %s',
                          env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        return {'ok': True, 'products': products, 'total': total,
                'limit': params['limit'], 'offset': params['offset']}

    @api.model
    def client_api_product_detail(self, token, product_id):
        """Client API (capability: products): ONE product's bounded detail.

        The requested product is read from the RESOLVED client
        environment only — a product id from another tenant simply does
        not exist in this DB (structural tenant isolation).
        """
        env_record, error = self._client_api_prelude(token, capability='products')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'product'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return self._client_error('CLIENT_REQUEST_INVALID')
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                record = cenv['product.product'].browse(product_id).exists()
                if not record:
                    return self._client_error('CLIENT_REQUEST_INVALID')
                product = self._client_catalog_projection(record)
                description = (record.description_sale
                               or record.description or '')
                product['description_full'] = description[:4000] if description else ''
        except Exception as exc:
            _logger.error('client.product_detail_failed (env_id=%s): %s',
                          env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        return {'ok': True, 'product': product}

    @api.model
    def client_api_product_image(self, token, product_id):
        """Client API (capability: products): ONE product's image bytes.

        Streams the stored product image through the BFF (the browser
        carries no credential; the same-origin proxy attaches it) so
        catalog payloads never embed giant base64 blobs.
        """
        env_record, error = self._client_api_prelude(token, capability='products')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'product'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return self._client_error('CLIENT_REQUEST_INVALID')
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                record = cenv['product.product'].browse(product_id).exists()
                if not record or not record.image_1920:
                    return self._client_error('CLIENT_REQUEST_INVALID')
                image = record.image_1920
        except Exception as exc:
            _logger.error('client.product_image_failed (env_id=%s): %s',
                          env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        return {'ok': True, 'image': image}

    @api.model
    def client_api_list_categories(self, token):
        """Client API (capability: products): the client DB's product
        categories (bounded projection: id, name, product_count)."""
        env_record, error = self._client_api_prelude(token, capability='products')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'product'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                categories = cenv['product.category'].search(
                    [], order='name asc, id asc')
                result = [{
                    'id': c.id,
                    'name': c.display_name,
                    'product_count': c.product_count,
                } for c in categories]
        except Exception as exc:
            _logger.error('client.categories_failed (env_id=%s): %s',
                          env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        return {'ok': True, 'categories': result}

    @api.model
    def client_api_create_lead(self, token, payload):
        """Client API (capability: leads): create ONE crm.lead in the CLIENT DB.

        Explicit field whitelist — no model/method passthrough, no
        arbitrary values.
        """
        env_record, error = self._client_api_prelude(token, capability='leads')
        if error:
            return error
        if not self._client_module_installed(env_record.db_name, 'crm'):
            return self._client_error('CLIENT_CAPABILITY_UNAVAILABLE')
        if not isinstance(payload, dict):
            return self._client_error('CLIENT_REQUEST_INVALID')

        def _clean_str(value, field, max_len, required=False):
            if value is None or value == '':
                if required:
                    return None, False
                return False, True
            if not isinstance(value, str) or not value.strip() or len(value) > max_len:
                return None, False
            return value.strip(), True

        name, ok = _clean_str(payload.get('name'), 'name', 200, required=True)
        if not ok:
            return self._client_error('CLIENT_REQUEST_INVALID')
        email, ok = _clean_str(payload.get('email'), 'email', 200)
        if not ok or (email and '@' not in email):
            return self._client_error('CLIENT_REQUEST_INVALID')
        phone, ok = _clean_str(payload.get('phone'), 'phone', 100)
        if not ok:
            return self._client_error('CLIENT_REQUEST_INVALID')
        message, ok = _clean_str(payload.get('message'), 'message', 4000)
        if not ok:
            return self._client_error('CLIENT_REQUEST_INVALID')

        vals = {'name': name}
        if email:
            vals['email_from'] = email
        if phone:
            vals['phone'] = phone
        if message:
            vals['description'] = message
        try:
            registry, cursor, EnvironmentCls = self._client_registry_env(env_record.db_name)
            with cursor as cr:
                cenv = EnvironmentCls(cr, odoo.SUPERUSER_ID, {})
                lead = cenv['crm.lead'].create(vals)
                lead_id = lead.id
        except Exception as exc:
            _logger.error('client.lead_create_failed (env_id=%s): %s', env_record.id, exc)
            return self._client_error('CLIENT_DB_UNAVAILABLE')
        _logger.info('client.lead_created (env_id=%s, lead_id=%s)', env_record.id, lead_id)
        return {'ok': True, 'lead_id': lead_id}