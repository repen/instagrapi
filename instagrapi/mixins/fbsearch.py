from typing import Dict, List, Tuple, Union

from instagrapi.extractors import (
    extract_hashtag_v1,
    extract_location,
    extract_track,
    extract_user_short,
    extract_media_v1
)
from instagrapi.types import Hashtag, Location, Track, UserShort, Media


class FbSearchMixin:
    def fbsearch_places(
        self, query: str, lat: float = 40.74, lng: float = -73.94
    ) -> List[Location]:
        params = {
            "search_surface": "places_search_page",
            "timezone_offset": self.timezone_offset,
            "lat": lat,
            "lng": lng,
            "count": 30,
            "query": query,
        }
        result = self.private_request("fbsearch/places/", params=params)
        locations = []
        for item in result["items"]:
            locations.append(extract_location(item["location"]))
        return locations

    def fbsearch_topsearch_flat(self, query: str) -> List[dict]:
        params = {
            "search_surface": "top_search_page",
            "context": "blended",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "query": query,
        }
        result = self.private_request("fbsearch/topsearch_flat/", params=params)
        return result["list"]

    def search_users(self, query: str) -> List[UserShort]:
        params = {
            "search_surface": "user_search_page",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "q": query,
        }
        result = self.private_request("users/search/", params=params)
        return [extract_user_short(item) for item in result["users"]]

    def search_music(self, query: str) -> List[Track]:
        params = {
            "query": query,
            "browse_session_id": self.generate_uuid(),
        }
        result = self.private_request("music/audio_global_search/", params=params)
        return [extract_track(item["track"]) for item in result["items"]]

    def search_hashtags(self, query: str) -> List[Hashtag]:
        params = {
            "search_surface": "hashtag_search_page",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "q": query,
        }
        result = self.private_request("tags/search/", params=params)
        return [extract_hashtag_v1(ht) for ht in result["results"]]

    def fbsearch_suggested_profiles(self, user_id: str) -> List[UserShort]:
        params = {
            "target_user_id": user_id,
            "include_friendship_status": "true",
        }
        result = self.private_request("fbsearch/accounts_recs/", params=params)
        return result["users"]

    def fbsearch_recent(self) -> List[Tuple[int, Union[UserShort, Hashtag, Dict]]]:
        """
        Retrieves recently searched results

        Returns
        -------
        List[Tuple[int, Union[UserShort, Hashtag, Dict]]]
            Returns list of Tuples where first value is timestamp of searh, second is retrived result
        """
        result = self.private_request("fbsearch/recent_searches/")
        assert result.get("status", "") == "ok", "Failed to retrieve recent searches"

        data = []
        for item in result.get("recent", []):
            if "user" in item.keys():
                data.append(
                    (item.get("client_time", None), extract_user_short(item["user"]))
                )
            if "hashtag" in item.keys():
                hashtag = item.get("hashtag")
                hashtag["media_count"] = hashtag.pop("formatted_media_count")
                data.append((item.get("client_time", None), Hashtag(**hashtag)))
            if "keyword" in item.keys():
                data.append((item.get("client_time", None), item["keyword"]))
        return data

    def _extract_media_for_web_top_search(self, result) -> List[Media]:
        medias = []
        for item in result["media_grid"]["sections"]:
            if item["layout_type"] == "media_grid":
                for container in item["layout_content"]["medias"]:
                    media = container["media"]
                    medias.append(extract_media_v1(media))
            elif item["layout_type"] == "one_by_two_left" or item["layout_type"] == "one_by_two_right":
                for container in item["layout_content"]["fill_items"]:
                    media = container["media"]
                    medias.append(extract_media_v1(media))
            else:
                self.logger.warning(f'Unknown layout_type {item["layout_type"]}')
        return medias


    def _fbsearch_web_top_serp(self, query: str, limit):
        temp = []
        params = {
            "query": query,
            "enable_metadata": True,
            "search_session_id":self.client_session_id,
        }
        result = self.private_request(
            "fbsearch/web/top_serp/", params=params,
            domain="www.instagram.com"
        )
        temp.extend(self._extract_media_for_web_top_search(result))
        self.logger.debug(f"extract media {len(temp)}")
        if len(temp) >= limit:
            return temp

        params["search_session_id"] = ""

        while len(temp) <= limit:
            params["rank_token"] = result["media_grid"]["rank_token"]
            params["next_max_id"] = result["media_grid"]["next_max_id"]
            result = self.private_request(
                "fbsearch/web/top_serp/", params=params,
                domain="www.instagram.com"
            )
            temp.extend(self._extract_media_for_web_top_search(result))
            self.logger.debug(f"extract media {len(temp)}")
        return temp

    def fbsearch_web_top_serp(self, query: str, limit=100) -> List[Media]:
        return self._fbsearch_web_top_serp(query, limit=limit)
