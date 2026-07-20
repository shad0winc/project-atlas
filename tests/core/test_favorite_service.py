from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from atlas.favorite_service import FavoriteService
from atlas.favorites import FavoriteError, FavoriteStore
from atlas.media.provider import MediaItem, MediaProviderError

class StubProvider:
    name = "jellyfin"
    def __init__(self, error: Exception | None = None): self.error = error
    def get_item(self, item_id: str) -> MediaItem:
        if self.error: raise self.error
        return MediaItem("jellyfin", item_id, "movie", "The Matrix", {"year": 1999})

class FavoriteServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.store = FavoriteStore(Path(self.temp.name)); self.events=[]
    def tearDown(self): self.temp.cleanup()
    def publisher(self, name, payload): self.events.append((name, dict(payload)))
    def test_add_enriches_record_and_publishes_event(self):
        service=FavoriteService(self.store,{"jellyfin":StubProvider()},self.publisher)
        result=service.add("usr_"+"a"*32,"Jellyfin","abc",metadata={"source":"cli"})
        self.assertEqual("The Matrix",result.record["title"]); self.assertEqual({"year":1999,"source":"cli"},result.record["metadata"])
        self.assertEqual("favorite.created",self.events[0][0]); self.assertIsNone(result.event_error)
    def test_remove_publishes_event(self):
        service=FavoriteService(self.store,{"jellyfin":StubProvider()},self.publisher)
        record=service.add("usr_"+"b"*32,"jellyfin","abc").record; self.events.clear()
        result=service.remove(record["favorite_id"])
        self.assertEqual("favorite.removed",self.events[0][0]); self.assertEqual(record["favorite_id"],result.record["favorite_id"])
    def test_provider_failure_and_unknown_provider_are_errors(self):
        service=FavoriteService(self.store,{"jellyfin":StubProvider(MediaProviderError("missing"))})
        with self.assertRaisesRegex(FavoriteError,"missing"): service.add("usr_"+"c"*32,"jellyfin","abc")
        with self.assertRaisesRegex(FavoriteError,"unsupported"): service.add("usr_"+"c"*32,"plex","abc")
    def test_event_failure_does_not_rollback(self):
        def fail(*_): raise RuntimeError("event down")
        service=FavoriteService(self.store,{"jellyfin":StubProvider()},fail)
        result=service.add("usr_"+"d"*32,"jellyfin","abc")
        self.assertEqual("event down",result.event_error); self.assertEqual(1,len(self.store.list()))
