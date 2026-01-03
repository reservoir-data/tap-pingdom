"""Pingdom tap class.

Copyright (c) 2025 Edgar Ramírez-Mondragón
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from singer_sdk import Stream, Tap
from singer_sdk import typing as th

from tap_pingdom import streams

if TYPE_CHECKING:
    from singer_sdk.streams import RESTStream

STREAM_TYPES: list[type[RESTStream[Any]]] = [
    streams.Checks,
    streams.Actions,
    # streams.Probes,  # Requires special permissions
    # streams.Maintenance,  # Requires special permissions
    # streams.MaintenanceOccurrences,  # Requires special permissions
    # streams.Teams,  # Requires special permissions
    streams.Contacts,
    # streams.TMSChecks,  # Requires special permissions
    streams.Results,
]


class TapPingdom(Tap):
    """Singer tap for Pingdom."""

    name = "tap-pingdom"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "token",
            th.StringType,
            required=True,
            secret=True,
            title="API Token",
            description="API Token for Pingdom",
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            title="Start Date",
            description="Earliest datetime to get data from",
        ),
    ).to_dict()

    @override
    def discover_streams(self) -> list[Stream]:
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
