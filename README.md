# Cloudflare Zero Trust Gateway Ad Block

Using Cloudflare Zero Trust Gateway with WRAP to block ads on your devices.

## What is this?

This script convert adblock list like [StevenBlack/hosts](https://github.com/StevenBlack/hosts) or [AdAway blocklist](https://adaway.org/hosts.txt) to domain list, split it into chunks and upload to Cloudflare Zero Trust Lists, and create a new policy to block those domains using Cloudflare Zero Trust Gateway.

## Getting Started

### Prerequisites

Cloudflare provides a free plan for Zero Trust Gateway, which is enough for this script.

- Cloudflare account with Zero Trust Free plan
- API Token with `Zero Trust:Edit` and `Account Firewall Access Rules:Edit` permissions, which can be created in [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens).

### Usage

1. Clone this repository.
2. Install dependencies in the project virtual environment.
3. Set environment variables.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# API Token
export CF_API_TOKEN=your_api_token
# Zone ID of your domain, can be found in url like https://dash.cloudflare.com/{zone_id}
export CF_ZONE_ID=your_zone_id
export ADLIST_NAME=HaGeZi-ultimate-mini
export ADLIST_URL=https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/wildcard/ultimate.mini-onlydomains.txt
# Standard Cloudflare Gateway limits (defaults shown)
export CF_MAX_LISTS=100
export CF_ENTRIES_PER_LIST=1000
```

4. Run the script with the virtual environment's Python.

```bash
.venv/bin/python main.py
```

When the script runs, it displays your Cloudflare Gateway locations. Press Enter to apply the policy to all locations, or enter one or more location numbers separated by commas, such as `1,3`.

The default Standard plan limits allow up to 100 lists with 1,000 entries per list. If the selected feed is larger, choose a smaller feed or configure higher limits only if your Cloudflare plan supports them.
