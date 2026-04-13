"""REST client handling, including PingdomStream base class.

Copyright (c) 2025 Edgar Ramírez-Mondragón
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from singer_sdk import RESTStream
from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.helpers import jsonpath
from singer_sdk.pagination import OffsetPaginator

if TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Context


class PingdomPaginator(OffsetPaginator):
    """Paginator for Pingdom API offset-based pagination."""

    def __init__(
        self,
        start_value: int,
        page_size: int,
        jsonpath_expression: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize paginator.

        Args:
            start_value: Initial offset value.
            page_size: Number of records per page.
            jsonpath_expression: JSONPath expression to extract records from response.
            args: Additional positional arguments.
            kwargs: Additional keyword arguments.
        """
        super().__init__(start_value, page_size, *args, **kwargs)
        self._jsonpath = jsonpath_expression
        self._records_count = 0

    @override
    def has_more(self, response: requests.Response) -> bool:
        """Check if there are more pages to fetch.

        Args:
            response: API response object.

        Returns:
            True if more pages exist, False otherwise.
        """
        # Parse the response to count records
        data = response.json()
        records = list(jsonpath.extract_jsonpath(self._jsonpath, data))

        # If we got a full page, there might be more
        # If we got less than a full page, we're done
        self._records_count = len(records)
        return self._records_count >= self._page_size


class PingdomStream(RESTStream[int]):
    """Pingdom stream class."""

    url_base = "https://api.pingdom.com/api/3.1"

    @override
    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        """Get an authenticator object."""
        return BearerTokenAuthenticator(token=self.config["token"])

    @override
    def get_url_params(
        self,
        context: Context | None,
        next_page_token: int | None,
    ) -> dict[str, Any]:
        """Get URL query parameters.

        Args:
            context: Stream sync context.
            next_page_token: Next offset for pagination.

        Returns:
            Mapping of URL query parameters.
        """
        params: dict[str, Any] = {}

        if next_page_token:
            params["offset"] = next_page_token

        return params

    @override
    def get_new_paginator(self) -> PingdomPaginator:
        """Get a new paginator for offset-based pagination.

        Returns:
            A paginator instance configured for this stream.
        """
        return PingdomPaginator(
            start_value=0,
            page_size=100,
            jsonpath_expression=self.records_jsonpath,
        )
