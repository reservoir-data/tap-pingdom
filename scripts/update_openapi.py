#!/usr/bin/env python

"""Update the OpenAPI schema from the Pingdom API.

Copyright (c) 2025 Edgar Ramírez-Mondragón
"""

from __future__ import annotations

import http
import json
import logging
import pathlib
import sys
import urllib.request

import yaml

OPENAPI_URL = "https://docs.pingdom.com/api/API_3.1.yaml"
PATH = "tap_pingdom/openapi/openapi.json"

logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger()


def main() -> None:
    """Update the OpenAPI schema from the Pingdom API."""
    logger.info("Updating OpenAPI schema from %s", OPENAPI_URL)

    with urllib.request.urlopen(OPENAPI_URL) as f_req:
        if f_req.status != http.HTTPStatus.OK:
            logger.error("Failed to fetch OpenAPI spec: %s", f_req.reason)
            sys.exit(1)

        # Read YAML and convert to JSON
        spec = yaml.safe_load(f_req)
        content = json.dumps(spec, indent=2) + "\n"
        pathlib.Path(PATH).write_text(content, encoding="utf-8")

    logger.info("OpenAPI schema updated successfully at %s", PATH)


if __name__ == "__main__":
    main()
