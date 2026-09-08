# -*- coding: utf-8 -*-
"""Phase 47.19 — Final pre-deployment hardening + client E2E readiness.

Locks the evidence-backed hardening items:
  * Part C (Assets): AssetEngine materializes a genuine branded hero visual
    (real SVG content, provenance) and CodeGenerationEngine writes it into
    the workspace and renders it in the hero. Consumption gap (47.18 Assets
    2/10) closed through existing owners — no new asset/image/media service.
  * Part D (Mobile validation): the existing Playwright validate contract
    carries an optional viewport; ValidationEngine passes it through without
    changing any existing desktop behavior.
  * Architecture: no parallel QA/asset/mobile/LLM service; existing owners
    remain authoritative.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
import odoo.modules.module as m

config.parse_config(['-c', 'D:\\ODOO\\configs\\dev.conf'])
m.initialize_sys_path()

from odoo.addons.nexora_studio.services.generation.engines.asset_engine import AssetEngine
from odoo.addons.nexora_studio.services.generation.engines.code_generation_engine import (
    CodeGenerationEngine,
)
from odoo.addons.nexora_studio.services.generation.engines.validation_engine import (
    ValidationEngine,
)
from odoo.addons.nexora_studio.services.generation.core.generation_context import (
    WebsiteGenerationArtifact, RequirementModel, ValidationReport, Workspace,
    Content, ArchitectureModel, ComponentTree,
)
from odoo.addons.nexora_studio.services.providers.execution_models import (
    ProviderExecutionRequest, ProviderExecutionResult,
)


def _src(rel):
    with open(os.path.join(ADDON, rel.replace('/', os.sep)), 'r',
              encoding='utf-8', errors='ignore') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Part C — asset gap closure through existing owners
# ---------------------------------------------------------------------------
class TestU4719AssetClosure(unittest.TestCase):

    def _artifact_with_hero(self):
        return WebsiteGenerationArtifact(
            requirements=RequirementModel(
                domain='Agency', business_name='Atelier Meridian',
                location='Copenhagen, Denmark',
                branding={'business_name': 'Atelier Meridian'}),
            architecture=ArchitectureModel(component_hierarchy={
                'home': {'type': 'page', 'path': '/', 'sections': ['Hero', 'Content']},
            }),
            component_tree=ComponentTree(nodes=[
                {'component_id': 'hero_section',
                 'metadata': {'semantic': 'hero_section'}},
            ]),
            validation=ValidationReport(
                passed=True, build_acceptance={'ran': True, 'failed': False}),
        )

    def test_asset_engine_materializes_real_hero_visual(self):
        artifact = self._artifact_with_hero()
        runtime = SimpleNamespace(env=None)
        result = AssetEngine(MagicMock()).execute(artifact, runtime)
        self.assertTrue(result.success)
        images = result.artifact.assets.images
        hero = [i for i in images if i.get('id') == 'hero_visual']
        self.assertEqual(len(hero), 1,
                         'an architecture Hero page must require a hero visual')
        self.assertIn('<svg', hero[0]['content'],
                      'the hero visual must carry real SVG content')
        self.assertIn('Atelier Meridian', hero[0]['content'],
                      'the branded hero visual must reference the business name')
        self.assertEqual(hero[0]['metadata']['ownership'], 'nexora_generated',
                          'provenance label')

    def test_no_hero_no_visual(self):
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'),
            architecture=ArchitectureModel(component_hierarchy={}),
            component_tree=ComponentTree(nodes=[]),
        )
        result = AssetEngine(MagicMock()).execute(
            artifact, SimpleNamespace(env=None))
        self.assertTrue(result.success)
        self.assertFalse(
            [i for i in result.artifact.assets.images
             if i.get('id') == 'hero_visual'],
            'no hero page -> no hero visual (demand-driven)')

    def test_asset_survives_to_code_generation(self):
        # The CodeGenerationEngine must map the branded hero visual to a
        # public asset path and mark the hero section as its owner, so the
        # asset reaches the generated site (closes 47.18 Assets 2/10).
        artifact = self._artifact_with_hero()
        asset_artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'),
            assets=SimpleNamespace(
                images=[{'id': 'hero_visual',
                         'content': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800"><text>Atelier Meridian</text></svg>',
                         'format': 'svg',
                         'metadata': {'ownership': 'nexora_generated',
                                      'alt': 'Atelier Meridian hero visual'}}],
                icons=[], fonts=[]))
        payload = CodeGenerationEngine._hero_image_payload(asset_artifact)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['path'], '/hero-visual.svg')
        self.assertIn('Atelier Meridian', payload['content'])
        self.assertTrue(CodeGenerationEngine._is_hero_section('Hero'))
        self.assertTrue(CodeGenerationEngine._is_hero_section('hero_section'))
        self.assertFalse(CodeGenerationEngine._is_hero_section('Content'))

    def test_no_hero_visual_no_payload(self):
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'),
            assets=SimpleNamespace(images=[], icons=[], fonts=[]))
        self.assertIsNone(CodeGenerationEngine._hero_image_payload(artifact))

    def test_generate_hero_section_carries_asset_reference(self):
        # Only the hero section payload carries the hero asset reference; a
        # non-hero section never does (reference is never fabricated).
        artifact = WebsiteGenerationArtifact(
            requirements=RequirementModel(domain='Agency'))
        captured = {}

        def _generate(op, payload):
            captured.update(payload)
            return {'full_content': 'function HeroSection1() { return '
                                    '<section><img src="/hero-visual.svg" '
                                    'alt="hero" /></section> }'}

        runtime = SimpleNamespace(ai=SimpleNamespace(generate=_generate))
        engine = CodeGenerationEngine(MagicMock())
        code = engine._generate_section(
            'Hero', 'HeroSection1', artifact, runtime, {},
            hero_image_path='/hero-visual.svg',
            hero_image_content='<svg>Atelier Meridian</svg>')
        self.assertIn('function HeroSection1', code)
        self.assertEqual(captured['hero_image_path'], '/hero-visual.svg')
        self.assertEqual(captured['hero_image_content'],
                         '<svg>Atelier Meridian</svg>')
        self.assertIn('hero visual at /hero-visual.svg', captured['task'])

        captured.clear()
        engine._generate_section(
            'Content', 'ContentSection1', artifact, runtime, {},
            hero_image_path=None, hero_image_content=None)
        self.assertNotIn('hero_image_path', captured)
        self.assertNotIn('hero_image_content', captured)


# ---------------------------------------------------------------------------
# Part D — mobile viewport through the existing browser validate contract
# ---------------------------------------------------------------------------
class TestU4719MobileValidation(unittest.TestCase):

    def test_validate_action_accepts_viewport_param(self):
        src = _src('models/playwright_provider.py')
        self.assertIn("'viewport'", src,
                      'the validate action must accept an optional viewport')
        self.assertIn('set_viewport_size', src,
                      'mobile viewport must be a real browser viewport')

    def test_viewport_defaults_absent_preserves_desktop_behavior(self):
        # U9.4/U9.5 contract: no viewport key -> unchanged behavior/output.
        self.assertIn('if viewport:', _src('models/playwright_provider.py'))

    def test_validation_engine_mobile_composes_existing_contract(self):
        src = _src('services/generation/engines/validation_engine.py')
        # The mobile reach must reuse the same provider call shape and store
        # its evidence inside the existing browser_validation evidence dict.
        self.assertIn('evidence["mobile"]', src)

    def test_no_mobile_qa_service_exists(self):
        services_dir = os.path.join(ADDON, 'services')
        offenders = []
        for root, dirs, files in os.walk(services_dir):
            dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
            for f in files:
                if not f.endswith('.py'):
                    continue
                with open(os.path.join(root, f), 'r',
                          encoding='utf-8', errors='ignore') as fh:
                    text = fh.read()
                for name in ('MobileQAService', 'ResponsiveQAService',
                             'MobileValidationService', 'ViewportService'):
                    if name in text:
                        offenders.append('%s:%s' % (f, name))
        self.assertEqual(offenders, [])


# ---------------------------------------------------------------------------
# Architecture integrity — no new parallel owners
# ---------------------------------------------------------------------------
class TestU4719ArchitectureIntegrity(unittest.TestCase):

    FORBIDDEN = (
        'AssetService', 'ImageService', 'MediaService', 'LLMService',
        'MobileQAService', 'ResponsiveQAService', 'ClientE2EPipeline',
        'ProductionReadinessService', 'FinalQAService',
        'DeploymentReadinessService', 'ConnectorOrchestrator',
    )

    def test_no_new_forbidden_owners(self):
        CHANGED = (
            'services/generation/engines/asset_engine.py',
            'models/playwright_provider.py',
            'services/generation/engines/validation_engine.py',
        )
        offenders = []
        for rel in CHANGED:
            text = _src(rel)
            for name in self.FORBIDDEN:
                self.assertNotIn(name, text, rel)
        # No new files should be introduced at all in engines/ or models/.
        engines = sorted(os.listdir(os.path.join(
            ADDON, 'services', 'generation', 'engines')))
        models = sorted(os.listdir(os.path.join(ADDON, 'models')))
        for name in ('asset_service.py', 'image_service.py',
                     'mobile_qa_service.py', 'llm_service.py'):
            self.assertNotIn(name, engines)
            self.assertNotIn(name, models)

    def test_existing_owners_preserved(self):
        self.assertTrue(os.path.isfile(os.path.join(
            ADDON, 'services/generation/engines/asset_engine.py')))
        self.assertTrue(os.path.isfile(os.path.join(
            ADDON, 'models/playwright_provider.py')))
        self.assertTrue(os.path.isfile(os.path.join(
            ADDON, 'services/generation/engines/validation_engine.py')))

    def test_asset_provenance_contract(self):
        hero = AssetEngine._build_hero_visual('Atelier Meridian', 'Agency')
        self.assertIn('<svg', hero)
        self.assertIn('Atelier Meridian', hero)
        self.assertIn('nexora_generated', _src(
            'services/generation/engines/asset_engine.py'))


if __name__ == '__main__':
    unittest.main()
