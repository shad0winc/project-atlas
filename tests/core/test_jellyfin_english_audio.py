"""English-first VOD negotiation, independent of file and user defaults."""
import copy
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from atlas.media.jellyfin import JellyfinProvider, _english_audio_stream_index
from atlas.media.provider import MediaProviderError


def audio(index, language, default=False):
    return {'Index': index, 'Type': 'Audio', 'Language': language,
            'IsDefault': default, 'Codec': 'aac'}


class EnglishAudioTest(unittest.TestCase):
    def setUp(self):
        self.provider = JellyfinProvider('http://example.invalid', 'fixture')
        self.source = {'Id': 'source-1', 'DefaultAudioStreamIndex': 1,
            'SupportsDirectPlay': False, 'SupportsDirectStream': True,
            'SupportsTranscoding': True,
            'TranscodingUrl': '/Videos/item-1/master.m3u8?MediaSourceId=source-1',
            'MediaStreams': [audio(1, 'jpn', True), audio(2, 'eng')]}

    def negotiate(self, first=None, second=None, **kwargs):
        first = copy.deepcopy(first or self.source)
        if second is None:
            second = copy.deepcopy(first)
            second['DefaultAudioStreamIndex'] = 2
        calls = []
        def request(path, *, method='GET', payload=None, **options):
            calls.append((path, method, copy.deepcopy(payload)))
            return {'PlaySessionId': 'fixture-session',
                    'MediaSources': [copy.deepcopy(first if len(calls) == 1 else second)]}
        with patch.object(JellyfinProvider, '_request_json', side_effect=request):
            result = self.provider.get_playback_info('item-1', user_id='linked-user', **kwargs)
        return result, calls

    def test_alternate_english_is_negotiated_with_pinned_source_and_user(self):
        result, calls = self.negotiate(prefer_english_audio=True)
        self.assertEqual(len(calls), 2)
        selected = calls[1][2]
        self.assertEqual(selected['UserId'], 'linked-user')
        self.assertEqual(selected['MediaSourceId'], 'source-1')
        self.assertEqual(selected['AudioStreamIndex'], 2)
        self.assertFalse(selected['EnableDirectPlay'])
        self.assertTrue(selected['AllowVideoStreamCopy'])
        self.assertNotIn('SubtitleStreamIndex', selected)
        self.assertEqual(parse_qs(urlsplit(result['stream_path']).query)['AudioStreamIndex'], ['2'])

    def test_subtitle_off_and_burn_in_survive_audio_selection(self):
        for subtitle in (-1, 3):
            with self.subTest(subtitle=subtitle):
                _, calls = self.negotiate(prefer_english_audio=True,
                                         subtitle_stream_index=subtitle)
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[1][2]['AudioStreamIndex'], 2)
                self.assertEqual(calls[1][2]['SubtitleStreamIndex'], subtitle)
                self.assertEqual(calls[1][2].get('AlwaysBurnInSubtitleWhenTranscoding', False), subtitle >= 0)

    def test_already_default_english_avoids_extra_negotiation(self):
        source = copy.deepcopy(self.source)
        source['DefaultAudioStreamIndex'] = 2
        source['MediaStreams'][1]['IsDefault'] = True
        _, calls = self.negotiate(first=source, prefer_english_audio=True)
        self.assertEqual(len(calls), 1)

    def test_missing_english_preserves_provider_choice(self):
        source = copy.deepcopy(self.source)
        source['MediaStreams'] = [audio(1, 'jpn', True)]
        _, calls = self.negotiate(first=source, prefer_english_audio=True)
        self.assertEqual(len(calls), 1)

    def test_provider_default_is_opt_in(self):
        _, calls = self.negotiate()
        self.assertEqual(len(calls), 1)

    def test_owned_live_is_not_renegotiated(self):
        _, calls = self.negotiate(prefer_english_audio=True, live_stream_owner=object())
        self.assertEqual(len(calls), 1)

    def test_existing_live_stream_keeps_audio_negotiation_unchanged(self):
        source = copy.deepcopy(self.source)
        source["LiveStreamId"] = "existing-live"
        _, calls = self.negotiate(first=source, prefer_english_audio=True)
        self.assertEqual(len(calls), 1)

    def test_opening_live_still_requires_owner_without_audio_renegotiation(self):
        source = copy.deepcopy(self.source)
        source['RequiresOpening'] = True
        with self.assertRaisesRegex(MediaProviderError, 'requires an Atlas owner'):
            self.negotiate(first=source, prefer_english_audio=True)

    def test_inconsistent_source_audio_or_static_url_fails_closed(self):
        cases = []
        second = copy.deepcopy(self.source)
        second['DefaultAudioStreamIndex'] = 2
        for field, value in (
            ('Id', 'wrong-source'), ('DefaultAudioStreamIndex', 1),
            ('MediaStreams', [audio(1, 'jpn', True)]),
            ('TranscodingUrl', '/Videos/item-1/master.m3u8?AudioStreamIndex=1'),
            ('TranscodingUrl', '/Videos/item-1/stream?Static=true'),
            ('LiveStreamId', 'unexpected-live'),
        ):
            case = copy.deepcopy(second)
            case[field] = value
            cases.append(case)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(MediaProviderError):
                    self.negotiate(second=case, prefer_english_audio=True)

    def test_language_tags_and_track_indexes_are_required(self):
        for language in ('eng', 'EN', 'English', ' en-US ', 'en-gb'):
            with self.subTest(language=language):
                self.assertEqual(_english_audio_stream_index({'MediaStreams': [audio(2, language)]}), 2)
        for index, language in ((True, 'eng'), (-1, 'eng'), ('2', 'eng'), (2, None), (2, 'jpn')):
            with self.subTest(index=index, language=language):
                self.assertIsNone(_english_audio_stream_index({'MediaStreams': [audio(index, language)]}))
        self.assertIsNone(_english_audio_stream_index({'MediaStreams': [
            {'Type': 'Subtitle', 'Index': 2, 'Language': 'eng'}]}))

    def test_multiple_english_tracks_keep_current_choice_then_default_then_index(self):
        source = {'DefaultAudioStreamIndex': 5,
                  'MediaStreams': [audio(2, 'eng', True), audio(5, 'eng')]}
        self.assertEqual(_english_audio_stream_index(source), 5)
        source['DefaultAudioStreamIndex'] = 1
        self.assertEqual(_english_audio_stream_index(source), 2)
        source['MediaStreams'][0]['IsDefault'] = False
        self.assertEqual(_english_audio_stream_index(source), 2)

    def test_duplicate_audio_identity_is_rejected(self):
        with self.assertRaisesRegex(MediaProviderError, 'ambiguous audio'):
            _english_audio_stream_index({'MediaStreams': [audio(2, 'eng'), audio(2, 'jpn')]})
