from __future__ import annotations

import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

log = logging.getLogger("jellyplexsync")


class ApiError(RuntimeError):
    pass


def client(timeout: int, verify: bool) -> httpx.Client:
    return httpx.Client(timeout=timeout, verify=verify, follow_redirects=True)


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=20),
    retry=retry_if_exception_type((httpx.TransportError, ApiError)),
)
def request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    response = client.request(method, url, **kwargs)
    if response.status_code >= 500:
        raise ApiError(f"{method} {url} -> {response.status_code}")
    if response.status_code >= 400:
        log.warning("HTTP %s %s -> %s %s", method, url, response.status_code, response.text[:300])
        response.raise_for_status()
    return response
