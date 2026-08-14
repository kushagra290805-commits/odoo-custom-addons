import uuid
import base64
import asyncio
from typing import Dict, Any

import warnings
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class LivePreviewEngine:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        warnings.warn(
            "Direct playwright usage in LivePreviewEngine is deprecated (Phase 23.1). "
            "Please migrate to the canonical 'nexora.provider.playwright' UCEL model.",
            DeprecationWarning, stacklevel=2
        )

    def process(self, component_code: str, device: str = "desktop") -> Dict[str, Any]:
        """Real preview generation using base64 rendering."""
        preview_id = str(uuid.uuid4())
        device_widths = {"desktop": "100%", "tablet": "768px", "mobile": "375px"}
        width = device_widths.get(device, "100%")
        html_wrapper = f"<html><body style='margin:0;padding:0;width:{width};'>{component_code}</body></html>"
        encoded = base64.b64encode(html_wrapper.encode('utf-8')).decode('utf-8')
        artifact_url = f"data:text/html;base64,{encoded}"
        
        return {
            "status": "success", 
            "preview_id": preview_id, 
            "artifact_url": artifact_url, 
            "device": device,
            "engine": "base64"
        }

    async def generate_screenshot(self, html_content: str, device: str = "desktop") -> Dict[str, Any]:
        if not HAS_PLAYWRIGHT:
            raise Exception("Playwright is required for screenshot generation")
            
        device_map = {
            "desktop": {"width": 1920, "height": 1080},
            "tablet": {"width": 768, "height": 1024},
            "mobile": {"width": 375, "height": 812}
        }
        viewport = device_map.get(device, device_map["desktop"])
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport=viewport)
            await page.set_content(html_content, wait_until="networkidle")
            screenshot_bytes = await page.screenshot(full_page=True)
            await browser.close()
            
            b64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
            return {
                "status": "success",
                "artifact_url": f"data:image/png;base64,{b64_image}",
                "device": device,
                "engine": "chromium"
            }
            
    async def generate_dom_snapshot(self, html_content: str) -> Dict[str, Any]:
        if not HAS_PLAYWRIGHT:
            raise Exception("Playwright is required for DOM snapshots")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")
            dom_snapshot = await page.evaluate("() => document.documentElement.outerHTML")
            await browser.close()
            
            return {
                "status": "success",
                "snapshot": dom_snapshot,
                "engine": "chromium"
            }
