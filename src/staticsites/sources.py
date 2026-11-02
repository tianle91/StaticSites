"""Small source adapters; fetch configuration and record semantics stay local."""
import time
import requests


def get_response(url, *, get=None, attempts=1, sleep=time.sleep, **options):
    if attempts < 1:
        raise ValueError("attempts must be positive")
    options.setdefault("timeout", 60)
    for attempt in range(attempts):
        try:
            response = (get or requests.get)(url, **options)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            sleep(2 ** attempt)


def ckan_action(base, action, params, *, user_agent, **options):
    response = get_response(base.rstrip('/') + '/api/3/action/' + action,
                            params=params, headers={"User-Agent": user_agent}, **options)
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN {action} failed: {payload}")
    return payload["result"]


def arcgis_result(payload, *, label="ArcGIS query failed"):
    if "error" in payload:
        raise ValueError(label + ": " + str(payload["error"]))
    return payload
