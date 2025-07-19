# src/api_client.py

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ApiClient:
    def __init__(self, base_url: str):
        if not base_url or not base_url.startswith("http"):
            raise ValueError("A valid API base URL is required.")
        self.base_url = base_url.rstrip('/')
        logger.info(f"ApiClient initialized with base URL: {self.base_url}")

    async def get_api_spec(self) -> Optional[Dict[str, Any]]:
        spec_paths = ["/v3/api-docs", "/openapi.json", "/swagger.json"]
        for path in spec_paths:
            try:
                url = f"{self.base_url}{path}"
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    logger.info(f"Successfully fetched API spec from {url}")
                    return response.json()
            except Exception as e:
                logger.warning(f"Could not fetch spec from {url}: {e}")
        logger.error("Could not find or fetch the API specification.")
        return None

    async def make_request(self, method: str, endpoint: str, json_payload: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.info(f"Making {method} request to {url} with JSON: {json_payload} and Params: {params}")
                
                response = await client.request(method.upper(), url, json=json_payload, params=params, timeout=30.0)
                response.raise_for_status()

                if not response.content:
                    return {"status": "SUCCESS", "message": f"Request successful with status {response.status_code}."}
                
                try:
                    return response.json()
                except Exception:
                    return {"status": "SUCCESS", "data": response.text}
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                logger.error(f"API request failed with status {e.response.status_code}: {error_text}")
                return {"status": "FAILED", "message": f"API Error ({e.response.status_code}): {error_text}"}
            except Exception as e:
                logger.error(f"An unexpected error occurred during API request: {e}", exc_info=True)
                return {"status": "FAILED", "message": f"An unexpected client-side error occurred: {e}"}