import json
import re
from typing import List, Optional
import requests
import logging
import os

logger = logging.getLogger("cloudflare")
REQUEST_TIMEOUT = 30

CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_IDENTIFIER = os.environ.get("CF_IDENTIFIER") or os.environ.get("CF_ZONE_ID")

if not CF_API_TOKEN or not CF_IDENTIFIER:
    raise Exception("Missing Cloudflare credentials")

session = requests.Session()
session.headers.update({"Authorization": f"Bearer {CF_API_TOKEN}"})


def _raise_api_error(operation: str, response: requests.Response):
    try:
        details = response.json().get("errors") or response.json()
    except ValueError:
        details = response.text[:500]

    raise Exception(
        f"Cloudflare {operation} failed ({response.status_code}): {details}"
    )


def get_lists(name_prefix: str):
    r = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists",
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[get_lists] {r.status_code}")

    if r.status_code != 200:
        _raise_api_error("get lists", r)

    lists = r.json()["result"] or []

    return [l for l in lists if l["name"].startswith(name_prefix)]


def get_unused_lists(name_prefix: str):
    lists = get_lists(name_prefix)
    policies = get_firewall_policies(name_prefix)
    used_list_ids = set()

    for policy in policies:
        traffic = policy.get("traffic", "")
        used_list_ids.update(re.findall(r"\$([A-Za-z0-9_-]+)", traffic))

    return [item for item in lists if item["id"] not in used_list_ids]


def create_list(name: str, domains: List[str]):
    r = session.post(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists",
        json={
            "name": name,
            "description": "Created by script.",
            "type": "DOMAIN",
            "items": [*map(lambda d: {"value": d}, domains)],
        },
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[create_list] {r.status_code}")

    if r.status_code != 200:
        _raise_api_error(f"create list '{name}'", r)

    return r.json()["result"]


def delete_list(list_id: str):
    r = session.delete(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists/{list_id}",
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[delete_list] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to delete Cloudflare list")

    return r.json()["result"]


def get_firewall_policies(name_prefix: str):
    r = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules",
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[get_firewall_policies] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to get Cloudflare firewall policies")

    lists = r.json()["result"] or []

    return [l for l in lists if l["name"].startswith(name_prefix)]


def get_locations():
    r = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/locations",
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[get_locations] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to get Cloudflare locations")

    return r.json()["result"] or []


def _build_gateway_traffic(list_ids: List[str], location_ids: Optional[List[str]] = None):
    domain_expression = " or ".join(
        [f"any(dns.domains[*] in ${list_id})" for list_id in list_ids]
    )
    expressions = [f"({domain_expression})"]

    if location_ids:
        locations = " ".join(json.dumps(location_id) for location_id in location_ids)
        expressions.append(f"dns.location in {{{locations}}}")

    return " and ".join(expressions)


def create_gateway_policy(
    name: str, list_ids: List[str], location_ids: Optional[List[str]] = None
):
    r = session.post(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules",
        json={
            "name": name,
            "description": "Created by script.",
            "action": "block",
            "enabled": True,
            "filters": ["dns"],
            "traffic": _build_gateway_traffic(list_ids, location_ids),
            "rule_settings": {
                "block_page_enabled": False,
            },
        },
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[create_gateway_policy] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to create Cloudflare firewall policy")

    return r.json()["result"]


def update_gateway_policy(
    name: str,
    policy_id: str,
    list_ids: List[str],
    location_ids: Optional[List[str]] = None,
):
    r = session.put(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules/{policy_id}",
        json={
            "name": name,
            "action": "block",
            "enabled": True,
            "traffic": _build_gateway_traffic(list_ids, location_ids),
        },
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[update_gateway_policy] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to update Cloudflare firewall policy")

    return r.json()["result"]


def delete_gateway_policy(policy_id: str):
    r = session.delete(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules/{policy_id}",
        timeout=REQUEST_TIMEOUT,
    )

    logger.debug(f"[delete_gateway_policy] {r.status_code}")

    if r.status_code != 200:
        raise Exception("Failed to delete Cloudflare firewall policy")

    return r.json()["result"]
