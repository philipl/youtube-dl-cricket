# coding: utf-8
from __future__ import unicode_literals
import re

from .common import InfoExtractor
from ..compat import compat_str
from ..utils import (
    ExtractorError,
    determine_ext,
    strip_jsonp,
    try_get,
)


class CricketComAuLiveIE(InfoExtractor):
    IE_NAME = 'cricketcomau:live'
    _VALID_URL = r'https?://live\.cricket\.com\.au/match/(?P<competition>\d*)/(?P<id>\d*)/.*'
    _TESTS = []

    # These might be more dynamic
    _ACCOUNT_ID = '807051129001'
    _ENVIRONMENT = 'KYfw9lAsI'
    #_POLICY_KEY = 'BCpkADawqM17uKWqEHlBulux385QZ_BoC6x04LRDmsykNRb4uwwRJ8x38iHNk-7kxEqJUu3qZGMFCiKA4d8SeUB0c40Z46CutsbR219abTqUHi82DqCZMUJo36s'

    def _match_competition(cls, url):
        if '_VALID_URL_RE' not in cls.__dict__:
            cls._VALID_URL_RE = re.compile(cls._VALID_URL)
        m = cls._VALID_URL_RE.match(url)
        assert m
        return compat_str(m.group('competition'))

    def _real_extract(self, url):
        meta_format = 'https://apiv2.cricket.com.au/streams?LegacyCompetitionId=%s&LegacyFixtureId=%s&format=json'
        player_format = 'https://players.brightcove.net/%s/%s_default/index.min.js'
        stream_format = 'https://edge.api.brightcove.com/playback/v1/accounts/%s/videos/%s'
        live_format = 'https://api.cricket.com.au/matches/%s/%s/live?overLimit=5&format=json'

        fixture = self._match_id(url)
        competition = self._match_competition(url)

        meta = self._download_json(
            meta_format % (competition, fixture),
            fixture)

        live = self._download_json(
            live_format % (competition, fixture),
            fixture)

        match = try_get(live, lambda x: x['liveMatch'], dict) or {}
        match_detail = match['matchDetail']
        series = match_detail['series']['name']
        match_type = match_detail['cmsMatchType']
        match_name = match_detail['matchName']
        home = match_detail['homeTeam']['name']
        away = match_detail['awayTeam']['name']

        title = ('%s.%s.%s.%s.vs.%s' % (match_type, series, match_name, home, away)).replace(' ', '.')

        streams = try_get(meta, lambda x: x['Streams'], list) or []
        if not streams:
            raise ExtractorError(
                'No streams present for this match. Is it active yet?',
                expected=True)

        stream_id = None
        for stream in streams:
            if stream['IsLive']:
                stream_id = stream['StreamId']
                break
        if not stream_id:
            raise ExtractorError('No live stream found. Is the stream active yet?',
                                 expected=True)

        player_js = self._download_webpage(
            player_format % (self._ACCOUNT_ID, self._ENVIRONMENT),
            fixture,
            note='Downloading Player JS')

        r = re.compile(r'policyKey:\"(?P<policyKey>.*?)\"')
        m = r.search(player_js)
        policy_key = m.group('policyKey')

        stream_json = self._download_json(
            stream_format % (self._ACCOUNT_ID, stream_id),
            fixture,
            headers = { 'Accept': 'application/json;pk=%s' % policy_key})

        sources = try_get(stream_json, lambda x: x['sources'], list) or []

        url = None
        asset_id = None
        entries = []
        for source in sources:
            type = try_get(source, lambda x: x['type'], compat_str)
            if type != 'application/vnd.apple.mpegurl':
                continue
            asset_id = try_get(source, lambda x: x['asset_id'], compat_str) or fixture
            url = source['src']

            formats = self._extract_m3u8_formats(
                url, asset_id, 'ts',
                entry_protocol='m3u8',
                m3u8_id='hls', fatal=True)
            self._sort_formats(formats)

            entries.append({
                'id': asset_id,
                'title': title,
                'series': series,
                'episode_name': match_name,
                #'episode_id': matchid,
                'match_type': match_type,
                'formats': formats,
            })

        return self.playlist_result(entries, fixture)
