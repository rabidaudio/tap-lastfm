"""REST client handling, including LastFMStream base class."""

import requests
from typing import Any, Dict, Optional

from singer_sdk.authenticators import APIKeyAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from tap_lastfm.property_stream import PropertyStream


class LastFMStream(PropertyStream):
    """LastFM base stream class."""

    url_base = "http://ws.audioscrobbler.com"
    # path is the same for all endpoints, they are chosen via the 'method' query param
    path = "/2.0"
    # Override this to return the method name to access
    method = None
    records_jsonpath = "$[*]"

    @property
    def authenticator(self) -> APIKeyAuthenticator:
        """Return a new authenticator object."""
        return APIKeyAuthenticator.create_for_stream(
            self, key="api_key", value=self.config.get("api_key"), location="params"
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed."""
        headers = {}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config.get("user_agent")
        return headers

    def get_next_page_token(
        self, response: requests.Response, previous_token: Optional[Any]
    ) -> Optional[Any]:
        """Return a token for identifying next page or None if no more pages."""
        if not self.total_pages_jsonpath:
            return None
        if not previous_token:
            return 1

        total_pages = int(
            next(
                iter(extract_jsonpath(self.total_pages_jsonpath, response.json())), None
            )
        )

        next_token = previous_token + 1
        if next_token > total_pages:
            return None
        return next_token

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
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
