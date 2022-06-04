"""Stream type classes for tap-lastfm."""

from typing import Any, Dict, Iterator, Optional
from urllib import parse

import pendulum
import requests
from pendulum.datetime import DateTime
from singer_sdk import typing as th  # JSON Schema typing helpers

from tap_lastfm.client import LastFMStream
from tap_lastfm.property_stream import Property

IMAGE_SIZES = ["small", "medium", "large", "extralarge"]


def blank_to_null(v: Any) -> Any:  # noqa: D103
    return v or None


def get_query_params(request: requests.PreparedRequest) -> dict:
    """Parse a param dictionary from a request object."""
    return {
        k: v[0]
        for k, v in parse.parse_qs(str(parse.urlparse(request.url).query)).items()
    }


class UsersStream(LastFMStream):
    """Stream of user account info."""

    name = "users"
    method = "user.getinfo"
    primary_keys = ["name"]
    replication_key = None
    replication_method = "FULL_TABLE"
    records_jsonpath = "$.user"

    properties = th.PropertiesList(
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
            cast=pendulum.from_timestamp,
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
        """Construct a UsersStream."""
        super().__init__(*args, **kwargs)
        self._usernames_iterator: Iterator[str] = iter(self.config["usernames"])

    def get_next_username(self) -> Optional[str]:
        """Return the next username from the list of usernames in the config."""
        return next(self._usernames_iterator, None)

    def get_next_page_token(
        self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        """Return a token for identifying next page or None if no more pages."""
        return self.get_next_username()

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        return {
            **super().get_url_params(context, next_page_token),
            "user": next_page_token or self.get_next_username(),
        }

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict:
        """Create a context for child streams to use.

        Contains both the username of the user and the date they registered.
        """
        return {
            "username": record["name"],
            "registered_at": record["registered_at"],
        }


class ScrobblesStream(LastFMStream):
    """Stream of scrobbles (plays)."""

    name = "scrobbles"
    method = "user.getRecentTracks"
    primary_keys = ["date", "name"]
    replication_key = "date"
    parent_stream_type = UsersStream
    ignore_parent_replication_key = True
    state_partitioning_keys = ["username"]
    records_jsonpath = "$.recenttracks.track[*]"
    total_pages_jsonpath = '$.recenttracks["@attr"].totalPages'
    is_sorted = False  # annoyingly only searches in reverse order
    properties = th.PropertiesList(
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
            cast=lambda x: pendulum.from_timestamp(int(x)),
        ),
        Property("username", th.StringType),
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

    def _start_time(self, context: dict) -> DateTime:
        start_at = self.get_starting_timestamp(context)
        if not start_at:
            start_at = context["registered_at"]
        if context["registered_at"] > start_at:
            start_at = context["registered_at"]
        assert start_at is not None
        return pendulum.instance(start_at)

    def _page_token_for(self, start: DateTime, page: int) -> dict:
        return {
            "from": str(int(start.timestamp())),
            "to": str(int(start.add(days=self.config["step_days"]).timestamp())),
            "page": page,
        }

    def get_next_page_token(
        self,
        response: requests.Response,
        previous_token: Optional[Any],
    ) -> Optional[Any]:
        """Return a token for identifying next page or None if no more pages."""
        req_params = get_query_params(response.request)
        prev_page = previous_token["page"] if previous_token else None
        next_page = super().get_next_page_token(response, prev_page)
        if next_page:
            return {
                "from": req_params["from"],
                "to": req_params["to"],
                "page": next_page,
            }
        new_start = pendulum.from_timestamp(int(req_params["to"]))
        if new_start > pendulum.now():
            return None
        self.finalize_state_progress_markers()  # emit state
        return self._page_token_for(new_start, page=1)

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        assert context is not None
        if not next_page_token:
            start_time = self._start_time(context)
            next_page_token = self._page_token_for(start_time, 1)
        self.logger.debug(
            f"fetching scrobbles for [{context['username']}] "
            f"from {next_page_token['from']} -> {next_page_token['to']} "
            f"page:{next_page_token['page']}"
        )
        return {
            **super().get_url_params(context, None),
            **next_page_token,
            "extended": "1",
            "limit": "200",
        }

    def post_process(self, row: dict, context: Optional[dict] = None) -> Optional[dict]:
        """As needed, append or transform raw data to match expected structure."""
        # add the username from context as it isn't in the response body
        assert context is not None
        row["username"] = context["username"]
        return super().post_process(row, context)


# FriendsStream
# LovedTracksStream
# AlbumStream
# ArtistStream
