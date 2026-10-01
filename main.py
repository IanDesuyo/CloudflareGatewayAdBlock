import logging
import ipaddress
import os
import pathlib
from typing import List
import requests
from dotenv import load_dotenv

load_dotenv()

import cloudflare


class App:
    def __init__(self, adlist_name: str, adlist_url: str):
        self.adlist_name = adlist_name
        self.adlist_url = adlist_url
        self.name_prefix = f"[AdBlock-{adlist_name}]"
        self.logger = logging.getLogger("main")

    def run(self):
        self.download_file()
        domains = self.convert_to_domain_list(self.adlist_name)
        entries_per_list = int(os.getenv("CF_ENTRIES_PER_LIST", "1000"))
        max_lists = int(os.getenv("CF_MAX_LISTS", "100"))
        required_lists = (len(domains) + entries_per_list - 1) // entries_per_list

        if required_lists > max_lists:
            raise ValueError(
                f"This list contains {len(domains)} domains and needs {required_lists} "
                f"Cloudflare lists, but the configured limit is {max_lists}. "
                "Use a smaller ad list or increase your Cloudflare limits."
            )

        # Ask before removing abandoned lists left by interrupted or failed uploads.
        unused_lists = cloudflare.get_unused_lists(self.name_prefix)
        if unused_lists:
            print("\nUnused Cloudflare lists:")
            for item in unused_lists:
                print(f"  - {item['name']}")

            confirmation = input("Delete these unused lists? [y/N]: ").strip().lower()
            if confirmation == "y":
                for item in unused_lists:
                    self.logger.info(f"Deleting unused list {item['name']}")
                    cloudflare.delete_list(item["id"])
            else:
                self.logger.info("Keeping unused lists")

        cf_lists = cloudflare.get_lists(self.name_prefix)

        self.logger.info(f"Number of lists in Cloudflare: {len(cf_lists)}")
        location_ids = self.select_locations()

        # compare the lists size
        if len(domains) == sum([l["count"] for l in cf_lists]):
            self.logger.warning("Lists are the same size, skipping")

        else:
            # delete the polices
            cf_policies = cloudflare.get_firewall_policies(self.name_prefix)
            for p in cf_policies:
                self.logger.info(f"Deleting policy {p['name']}")
                cloudflare.delete_gateway_policy(p["id"])
                
            # delete the lists
            for l in cf_lists:
                self.logger.info(f"Deleting list {l['name']}")

                cloudflare.delete_list(l["id"])

            cf_lists = []

            # chunk the domains into lists of 1000 and create them
            for chunk in self.chunk_list(domains, entries_per_list):
                list_name = f"{self.name_prefix} {len(cf_lists) + 1}"

                self.logger.info(f"Creating list {list_name}")

                _list = cloudflare.create_list(list_name, chunk)

                cf_lists.append(_list)

        # get the gateway policies
        cf_policies = cloudflare.get_firewall_policies(self.name_prefix)

        self.logger.info(f"Number of policies in Cloudflare: {len(cf_policies)}")

        # setup the gateway policy
        if len(cf_policies) == 0:
            self.logger.info("Creating firewall policy")

            cf_policies = cloudflare.create_gateway_policy(
                f"{self.name_prefix} Block Ads",
                [l["id"] for l in cf_lists],
                location_ids,
            )

        elif len(cf_policies) != 1:
            self.logger.error("More than one firewall policy found")

            raise Exception("More than one firewall policy found")

        else:
            self.logger.info("Updating firewall policy")

            cloudflare.update_gateway_policy(
                f"{self.name_prefix} Block Ads",
                cf_policies[0]["id"],
                [l["id"] for l in cf_lists],
                location_ids,
            )

        self.logger.info("Done")

    def select_locations(self):
        locations = cloudflare.get_locations()

        if not locations:
            self.logger.warning("No Cloudflare locations found; applying policy to all locations")
            return []

        print("\nCloudflare locations (press Enter to use all):")
        for index, location in enumerate(locations, start=1):
            print(f"  {index}. {location['name']}")

        while True:
            selection = input("Select locations by number, separated by commas: ").strip()

            if not selection:
                return []

            try:
                selected_indexes = [int(value.strip()) for value in selection.split(",")]
                if not selected_indexes or any(
                    index < 1 or index > len(locations) for index in selected_indexes
                ):
                    raise ValueError
            except ValueError:
                print("Please enter valid location numbers, separated by commas, or press Enter for all.")
                continue

            return [locations[index - 1]["id"] for index in dict.fromkeys(selected_indexes)]

    def download_file(self):
        self.logger.info(f"Downloading file from {self.adlist_url}")

        r = requests.get(self.adlist_url, allow_redirects=True)

        path = pathlib.Path(self.adlist_name)
        open(path, "wb").write(r.content)

        self.logger.info(f"File size: {path.stat().st_size}")

    def convert_to_domain_list(self, file_name: str):
        with open(file_name, "r") as f:
            data = f.read()

        domains = []
        for line in data.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split()
            try:
                ipaddress.ip_address(fields[0])
            except ValueError:
                domain = fields[0]
            else:
                if len(fields) < 2 or fields[1] == "localhost":
                    continue
                domain = fields[1]

            domains.append(domain)

        self.logger.info(f"Number of domains: {len(domains)}")

        return domains

    def chunk_list(self, _list: List[str], n: int):
        for i in range(0, len(_list), n):
            yield _list[i : i + n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    app = App(
        os.getenv("ADLIST_NAME", "HaGeZi-ultimate"),
        os.getenv(
            "ADLIST_URL",
            "https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/wildcard/ultimate-onlydomains.txt",
        ),
    )

    app.run()
