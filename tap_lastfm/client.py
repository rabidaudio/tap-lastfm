"""REST client handling, including LastFMStream base class."""

from typing import Any, Callable, Dict, Optional

import backoff
import requests
from singer_sdk.authenticators import APIKeyAuthenticator
from singer_sdk.exceptions import RetriableAPIError
from singer_sdk.helpers.jsonpath import extract_jsonpath

from tap_lastfm.property_stream import PropertyStream


class LastFMStream(PropertyStream):
    """LastFM base stream class."""

    url_base = "http://ws.audioscrobbler.com"
    # path is the same for all endpoints, they are chosen via the 'method' query param
    path = "/2.0"
    # Override this to return the method name to access
    method: str
    records_jsonpath = "$[*]"
    total_pages_jsonpath: Optional[str] = None

    @property
    def authenticator(self) -> APIKeyAuthenticator:
        """Return a new authenticator object."""
        return APIKeyAuthenticator.create_for_stream(
            self,
            key="api_key",
            value=str(self.config.get("api_key")),
            location="params",
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed."""
        headers = {}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config.get("user_agent")
        return headers

    def get_next_page_token(
        self, response: requests.Response, previous_token: Optional[int]
    ) -> Optional[int]:
        """Return a token for identifying next page or None if no more pages."""
        if not self.total_pages_jsonpath:
            return None
        if not previous_token:
            return 2  # we already requested page 1

            # TODO: I think this is confusing design for the SDK.
            # The first time `get_next_page_token` is called is after
            # the first request. Often pagination logic is split between
            # `get_next_page_token` and `get_url_params` which needs to know
            # how to set up the first page.
            # Also `get_next_page_token` should maybe have access to context.

        total_pages = int(
            next(iter(extract_jsonpath(self.total_pages_jsonpath, response.json())), 0)
        )

        next_token = previous_token + 1
        if next_token > total_pages:
            return None
        return next_token

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[int]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params: dict = {
            "format": "json",
            "method": self.method,
        }
        if next_page_token:
            params["page"] = next_page_token
        if context and "username" in context:
            params["user"] = context["username"]
        return params

    # TODO: temporary workaround
    # remove this after https://github.com/meltano/sdk/issues/1236
    # is merged and SDK version bumped
    def request_decorator(self, func: Callable) -> Callable:
        """Instantiate a decorator for handling request failures.
        Uses a wait generator defined in `backoff_wait_generator` to
        determine backoff behaviour. Try limit is defined in
        `backoff_max_tries`, and will trigger the event defined in
        `backoff_handler` before retrying. Developers may override one or
        all of these methods to provide custom backoff or retry handling.
        Args:
            func: Function to decorate.
        Returns:
            A decorated method.
        """
        decorator: Callable = backoff.on_exception(
            self.backoff_wait_generator,
            (
                ConnectionResetError,
                RetriableAPIError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ),
            max_tries=self.backoff_max_tries,
            on_backoff=self.backoff_handler,
        )(func)
        return decorator
