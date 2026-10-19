"""Offline opaque maintenance session lifetime and revocation contracts."""
import unittest
from atlas_api.auth.maintenance_sessions import MaintenanceSessions


class MaintenanceSessionsTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.active = {('u','r',3000)}
        self.store = MaintenanceSessions(lambda subject,key,expires:(subject,key,expires) in self.active,
                                         clock=lambda:self.now)

    def test_opaque_cookie_is_hashed_and_bounded(self):
        value,lifetime = self.store.issue_browser('u','r',3000)
        self.assertEqual(len(value),43)
        self.assertEqual(lifetime,900)
        self.assertNotIn(value,self.store.browser)
        self.assertEqual(self.store.browser_subject(value),'u')
        self.now += 900
        self.assertIsNone(self.store.browser_subject(value))

    def test_refresh_expiry_bounds_cookie(self):
        self.active = {('u','r',1010)}
        value,lifetime = self.store.issue_browser('u','r',1010)
        self.assertEqual(lifetime,10)
        self.now = 1010
        self.assertIsNone(self.store.browser_subject(value))

    def test_inactive_session_cannot_mint_cookie(self):
        self.active.clear()
        with self.assertRaises(ValueError):
            self.store.issue_browser('u','r',3000)

    def test_logout_rotation_and_subject_revocation_drop_all_bindings(self):
        value,_ = self.store.issue_browser('u','r',3000)
        self.store.bind_access('a','u',1500,'r',3000)
        self.assertTrue(self.store.access_active('a','u'))
        self.active.clear()
        self.assertFalse(self.store.access_active('a','u'))
        self.assertIsNone(self.store.browser_subject(value))

    def test_access_subject_and_expiry_are_enforced(self):
        self.store.bind_access('a','u',1100,'r',3000)
        self.assertFalse(self.store.access_active('a','other'))
        self.now = 1100
        self.assertFalse(self.store.access_active('a','u'))

    def test_restart_does_not_restore_browser_or_access_bindings(self):
        value,_ = self.store.issue_browser('u','r',3000)
        self.store.bind_access('a','u',1500,'r',3000)
        fresh = MaintenanceSessions(self.store.active,clock=lambda:self.now)
        self.assertIsNone(fresh.browser_subject(value))
        self.assertFalse(fresh.access_active('a','u'))

    def test_untrusted_cookie_values_do_not_authorize(self):
        for value in (None,'','x'*43,'x'*9000,123):
            with self.subTest(value=type(value)):
                self.assertIsNone(self.store.browser_subject(value))


if __name__ == '__main__':
    unittest.main()
