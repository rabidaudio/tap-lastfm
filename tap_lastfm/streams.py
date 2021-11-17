"""Stream type classes for tap-lastfm."""

from typing import Any, Dict, Iterator, Optional
import requests
from datetime import datetime

from singer_sdk import typing as th  # JSON Schema typing helpers

from tap_lastfm.client import LastFMStream
from tap_lastfm.property_stream import PropertiesList, Property

IMAGE_SIZES = ["small", "medium", "large", "extralarge"]


def blank_to_null(v: Any) -> Any:
    return v or None


class UsersStream(LastFMStream):
    """Stream of user account info."""

    name = "users"
    method = "user.getinfo"
    primary_keys = ["name"]
    replication_key = None
    replication_method = "FULL_TABLE"
    records_jsonpath = "$.user"

    properties = PropertiesList(
        Property("name", th.StringType),
        Property("realname", th.StringType),
        Property("url", th.StringType),
        Property("country", th.StringType, description="2-letter country code"),
        Property(
            "age",
            th.IntegerType,
            cast=lambda v: None if v == 0 else v,
        ),
        Property(
            "gender",
            th.StringType,
            description="one of 'm', 'f'",
            cast=lambda v: None if v == "n" else v,
        ),
        Property("subscriber", th.BooleanType),  # cast=bool
        Property("playcount", th.IntegerType),
        Property("playlists", th.IntegerType),
        Property("bootstrap", th.BooleanType),
        Property(
            "registered_at",
            th.DateTimeType,
            jsonpath_selector='$.registered["#text"]',
            cast=datetime.fromtimestamp,
        ),
        Property(
            "image",
            th.ObjectType(
                *[
                    Property(
                        size,
                        th.StringType,
                        jsonpath_selector=f'$.image[?size="{size}"]["#text"]',
                    )
                    for size in IMAGE_SIZES
                ]
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._usernames_iterator: Iterator[str] = iter(self.config["usernames"])

    def get_next_username(self) -> Optional[str]:
        return next(self._usernames_iterator, None)

    def get_next_page_token(
        self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        return self.get_next_username()

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        return {
            **super().get_url_params(context, next_page_token),
            "user": next_page_token or self.get_next_username(),
        }

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict:
        return {
            "username": record["name"],
            "registered_at": record["registered_at"],
        }


class ScrobblesStream(LastFMStream):
    """Stream of scrobbles (plays)."""

    name = "scrobbles"
    method = "user.getRecentTracks"
    primary_keys = ["date", "name", "artist_name"]
    replication_key = "date"
    parent_stream_type = UsersStream
    ignore_parent_replication_key = True
    state_partitioning_keys = ["username"]
    records_jsonpath = "$.recenttracks.track[*]"
    total_pages_jsonpath = '$.recenttracks["@attr"].totalPages'
    is_sorted = False  # annoyingly only searches in reverse order
    properties = PropertiesList(
        Property("name", th.StringType, description="The name of the track"),
        Property(
            "mbid",
            th.StringType,
            description="The MusicBrainz recording ID, if known",
            cast=blank_to_null,
        ),
        Property("url", th.StringType),
        Property("streamable", th.BooleanType),
        Property("loved", th.BooleanType),
        Property(
            "date",
            th.DateTimeType,
            description="The time the track was listened to (scrobbled)",
            jsonpath_selector="$.date.uts",
            cast=lambda x: datetime.fromtimestamp(int(x)),
        ),
        Property(
            "artist",
            th.ObjectType(
                Property("name", th.StringType, jsonpath_selector="$.artist.name"),
                Property(
                    "mbid",
                    th.StringType,
                    jsonpath_selector="$.artist.mbid",
                    description="The MusicBrainz artist ID, if known.",
                    cast=blank_to_null,
                ),
                Property("url", th.StringType, jsonpath_selector="$.artist.url"),
                Property(
                    "image",
                    th.ObjectType(
                        *[
                            Property(
                                size,
                                th.StringType,
                                jsonpath_selector=f'$.artist.image[?size="{size}"]["#text"]',  # noqa E501
                            )
                            for size in IMAGE_SIZES
                        ]
                    ),
                ),
            ),
        ),
        Property(
            "album",
            th.ObjectType(
                Property("name", th.StringType, jsonpath_selector='$.album["#text"]'),
                Property(
                    "mbid",
                    th.StringType,
                    jsonpath_selector="$.album.mbid",
                    description="The MusicBrainz release ID, if known.",
                    cast=blank_to_null,
                ),
            ),
        ),
        Property(
            "image",
            th.ObjectType(
                *[
                    Property(
                        size,
                        th.StringType,
                        jsonpath_selector=f'$.image[?size="{size}"]["#text"]',
                    )
                    for size in IMAGE_SIZES
                ]
            ),
        ),
    )

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        params = {
            **super().get_url_params(context, next_page_token),
            "extended": "1",
            "limit": "200",
        }
        start_at = self.get_starting_timestamp(context) or context["registered_at"]
        if start_at:
            params["from"] = str(int(start_at.timestamp()))

        return params
