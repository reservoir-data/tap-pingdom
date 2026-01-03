"""Stream type classes for tap-pingdom.

Copyright (c) 2025 Edgar Ramírez-Mondragón
"""

from __future__ import annotations

import datetime
from importlib import resources
from typing import TYPE_CHECKING, Any, override

from singer_sdk import OpenAPISchema, StreamSchema
from singer_sdk import typing as th

from tap_pingdom import client, openapi
from tap_pingdom.client import PingdomStream
from tap_pingdom.schema_utils import apply_schema_patch

if TYPE_CHECKING:
    from singer_sdk.helpers.types import Context, Record

OPENAPI_SCHEMA = OpenAPISchema(resources.files(openapi) / "openapi.json")


class Checks(PingdomStream):
    """Checks stream - monitors configured in Pingdom."""

    name = "checks"
    path = "/checks"
    primary_keys = ("id",)
    replication_key = None
    schema = StreamSchema(OPENAPI_SCHEMA, key="CheckWithStringType")
    records_jsonpath = "$.checks[*]"

    @override
    def get_new_paginator(self) -> client.PingdomPaginator:
        """Get a new paginator for this stream.

        Returns:
            A paginator instance configured for Checks stream.
        """
        return client.PingdomPaginator(
            start_value=0,
            page_size=25000,
            jsonpath_expression=self.records_jsonpath,
        )

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
        params = super().get_url_params(context, next_page_token)
        params["limit"] = 25000  # Max allowed
        params["include_tags"] = True
        return params

    @override
    def get_child_context(self, record: Record, context: Context | None) -> Context | None:
        """Return context for child streams.

        Args:
            record: A record from this stream.
            context: Stream sync context.

        Returns:
            A dictionary containing the check ID.
        """
        return {"checkid": record["id"]}


class Actions(PingdomStream):
    """Actions stream - alert history."""

    name = "actions"
    path = "/actions"
    primary_keys = ("checkid", "time", "userid")
    replication_key = "time"
    records_jsonpath = "$.actions.alerts[*]"

    # NOTE: Manual schema required due to OpenAPI spec issues:
    # 1. The item schema is defined inline within 'actions_alerts_entry'
    #    response wrapper, not as a reusable component that StreamSchema
    #    can reference
    # 2. OpenAPI spec has INCORRECT types: userid, checkid, time are
    #    defined as strings but actual API returns integers
    # 3. OpenAPI spec defines charged as string but it should be boolean
    # To fix: Update OpenAPI spec with correct types and extract alert
    # item schema as a standalone component (e.g., 'AlertItem'), then:
    #   schema = StreamSchema(OPENAPI_SCHEMA, key="AlertItem")
    schema = th.PropertiesList(
        th.Property(
            "checkid",
            th.IntegerType,
            required=True,
            description="Check identifier",
        ),
        th.Property(
            "time",
            th.IntegerType,
            required=True,
            description="Alert time (Unix timestamp)",
        ),
        th.Property(
            "userid",
            th.IntegerType,
            required=True,
            description="User identifier",
        ),
        th.Property("username", th.StringType, description="User name"),
        th.Property("via", th.StringType, description="Alert medium"),
        th.Property("status", th.StringType, description="Alert status"),
        th.Property("messageshort", th.StringType, description="Short message"),
        th.Property("messagefull", th.StringType, description="Full message"),
        th.Property("sentto", th.StringType, description="Recipient address"),
        th.Property("charged", th.BooleanType, description="Whether charged"),
    ).to_dict()

    @override
    def get_new_paginator(self) -> client.PingdomPaginator:
        """Get a new paginator for this stream.

        Returns:
            A paginator instance configured for Actions stream.
        """
        return client.PingdomPaginator(
            start_value=0,
            page_size=100,
            jsonpath_expression=self.records_jsonpath,
        )

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
        params = super().get_url_params(context, next_page_token)
        params["limit"] = 100  # Max allowed by Pingdom API

        # Add time filtering if start_date is configured
        if self.config.get("start_date"):
            start_date = self.config["start_date"]
            if isinstance(start_date, str):
                start_date = datetime.datetime.fromisoformat(start_date)
            params["from"] = int(start_date.timestamp())

        return params


class Probes(PingdomStream):
    """Probes stream - Pingdom probe servers."""

    name = "probes"
    path = "/probes"
    primary_keys = ("id",)
    replication_key = None
    schema = StreamSchema(OPENAPI_SCHEMA, key="Probe")
    records_jsonpath = "$.probes[*]"


class Maintenance(PingdomStream):
    """Maintenance windows stream."""

    name = "maintenance"
    path = "/maintenance"
    primary_keys = ("id",)
    replication_key = None

    # NOTE: Manual schema required because:
    # 1. The item schema is defined inline within 'maintenance_resp_attrs'
    #    response wrapper, not as a reusable component that StreamSchema
    #    can reference
    # 2. OpenAPI spec includes extra properties (repeatevery, effectiveto)
    #    that may not be consistently returned by the API
    # To fix: Extract maintenance item schema from OpenAPI spec as a
    # standalone component (e.g., 'MaintenanceWindow'), verify which
    # properties are actually used, then:
    #   schema = StreamSchema(OPENAPI_SCHEMA, key="MaintenanceWindow")
    schema = th.PropertiesList(
        th.Property(
            "id",
            th.IntegerType,
            required=True,
            description="Maintenance window identifier",
        ),
        th.Property("description", th.StringType, description="Description"),
        th.Property("from", th.IntegerType, description="Start timestamp"),
        th.Property("to", th.IntegerType, description="End timestamp"),
        th.Property("recurrencetype", th.StringType, description="Recurrence type"),
        th.Property(
            "checks",
            th.ObjectType(
                th.Property("uptime", th.ArrayType(th.IntegerType)),
                th.Property("tms", th.ArrayType(th.IntegerType)),
            ),
            description="Affected checks",
        ),
    ).to_dict()
    records_jsonpath = "$.maintenance[*]"


class MaintenanceOccurrences(PingdomStream):
    """Maintenance occurrences stream."""

    name = "maintenance_occurrences"
    path = "/maintenance.occurrences"
    primary_keys = ("id",)
    replication_key = None

    # NOTE: Manual schema required because:
    # 1. The item schema is defined inline within the response wrapper
    #    'maintenance.occurrences_resp_attrs', not as a reusable
    #    component that StreamSchema can reference
    # To fix: Extract occurrence item schema from OpenAPI spec as a
    # standalone component (e.g., 'MaintenanceOccurrence'), then:
    #   schema = StreamSchema(OPENAPI_SCHEMA, key="MaintenanceOccurrence")
    schema = th.PropertiesList(
        th.Property(
            "id",
            th.IntegerType,
            required=True,
            description="Occurrence identifier",
        ),
        th.Property(
            "maintenanceid",
            th.IntegerType,
            description="Parent maintenance window ID",
        ),
        th.Property("from", th.IntegerType, description="Start timestamp"),
        th.Property("to", th.IntegerType, description="End timestamp"),
    ).to_dict()
    records_jsonpath = "$.occurrences[*]"


class Teams(PingdomStream):
    """Alerting teams stream."""

    name = "teams"
    path = "/alerting/teams"
    primary_keys = ("id",)
    replication_key = None
    schema = StreamSchema(OPENAPI_SCHEMA, key="AlertingTeams")
    records_jsonpath = "$.teams[*]"


class Contacts(PingdomStream):
    """Alerting contacts stream."""

    name = "contacts"
    path = "/alerting/contacts"
    primary_keys = ("id",)
    replication_key = None
    schema = StreamSchema(OPENAPI_SCHEMA, key="ContactTargets")
    records_jsonpath = "$.contacts[*]"

    @property
    @override
    def effective_schema(self) -> dict[str, Any]:
        """Apply patches to simplify the OpenAPI schema.

        The ContactTargets OpenAPI schema uses complex anyOf types for
        notification_targets which include multiple schema references
        (SMSes, Emails, APNS, AGCM). This override simplifies it to a
        generic object type which is sufficient for data extraction.

        Returns:
            Patched schema dictionary.
        """
        base_schema = super().effective_schema

        # Simplify notification_targets from complex anyOf to simple object
        patches = {
            "properties": {
                "notification_targets": {
                    "anyOf": None,  # Remove complex anyOf
                    "type": ["object", "null"],
                    "description": "Notification targets configuration",
                },
            },
        }

        return apply_schema_patch(base_schema, patches)


class TMSChecks(PingdomStream):
    """Transaction Monitoring (TMS) checks stream."""

    name = "tms_checks"
    path = "/tms/check"
    primary_keys = ("id",)
    replication_key = None
    schema = StreamSchema(OPENAPI_SCHEMA, key="CheckGeneral")
    records_jsonpath = "$.checks[*]"


class Results(PingdomStream):
    """Results stream - raw test results for a specific check.

    This is a child stream of Checks.
    """

    name = "results"
    path = "/results/{checkid}"
    primary_keys = ("checkid", "time")
    replication_key = "time"

    # NOTE: Manual schema required because:
    # 1. The item schema is defined inline within 'results_resp_attrs'
    #    response wrapper, not as a reusable component that StreamSchema
    #    can reference
    # 2. OpenAPI spec is missing the 'probedesc' property that actual
    #    API returns
    # 3. The 'checkid' property is added via post_process() from parent
    #    context and isn't in the OpenAPI response schema
    # To fix: Extract result item schema from OpenAPI spec as a standalone
    # component (e.g., 'ResultItem'), add missing probedesc property,
    # document that checkid is injected from context, then:
    #   schema = StreamSchema(OPENAPI_SCHEMA, key="ResultItem")
    schema = th.PropertiesList(
        th.Property(
            "checkid",
            th.IntegerType,
            required=True,
            description="Check identifier",
        ),
        th.Property(
            "time",
            th.IntegerType,
            required=True,
            description="Test timestamp (Unix time)",
        ),
        th.Property("status", th.StringType, description="Test result status"),
        th.Property("responsetime", th.IntegerType, description="Response time (ms)"),
        th.Property("statusdesc", th.StringType, description="Status description"),
        th.Property(
            "statusdesclong", th.StringType, description="Long status description"
        ),
        th.Property("probeid", th.IntegerType, description="Probe identifier"),
        th.Property("probedesc", th.StringType, description="Probe description"),
    ).to_dict()
    records_jsonpath = "$.results[*]"
    parent_stream_type = Checks

    @override
    def get_new_paginator(self) -> client.PingdomPaginator:
        """Get a new paginator for this stream.

        Returns:
            A paginator instance configured for Results stream.
        """
        return client.PingdomPaginator(
            start_value=0,
            page_size=1000,
            jsonpath_expression=self.records_jsonpath,
        )

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
        params = super().get_url_params(context, next_page_token)
        params["limit"] = 1000  # Max allowed

        # Add time filtering if start_date is configured
        if self.config.get("start_date"):
            start_date = self.config["start_date"]
            if isinstance(start_date, str):
                start_date = datetime.datetime.fromisoformat(start_date)
            params["from"] = int(start_date.timestamp())

        return params

    @override
    def post_process(
        self,
        row: Record,
        context: Context | None = None,
    ) -> Record | None:
        """Add checkid from context to each result record.

        Args:
            row: Individual record in the stream.
            context: Stream partition or context dictionary.

        Returns:
            The resulting record dict, or `None` if the record should be excluded.
        """
        if context:
            row["checkid"] = context["checkid"]
        return row
