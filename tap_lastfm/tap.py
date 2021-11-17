"""LastFM tap class."""

from typing import List

from singer_sdk import Tap, Stream
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_lastfm.streams import (
    ScrobblesStream,
    UsersStream,
)

STREAM_TYPES = [
    UsersStream,
    ScrobblesStream,
]


class TapLastFM(Tap):
    """LastFM tap class."""

    name = "tap-lastfm"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "api_key",
            th.StringType,
            required=True,
            description="The API key to authenticate against the API service",
        ),
        th.Property(
            "usernames",
            th.ArrayType(th.StringType),
            required=True,
            description="The usernames of users to fetch scrobble data for",
        ),
        th.Property(
            "user_agent",
            th.StringType,
            description="The earliest record date to sync",
            default="tap-lastfm",
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            description="The earliest record date to sync",
        ),
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        """Return a list of discovered streams."""
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]
