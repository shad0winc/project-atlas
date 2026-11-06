import json
from pathlib import Path
import tempfile
import unittest

from atlas.identity import IdentityPaths
from atlas.invitation_email_template import (
    DEFAULT_TEMPLATE, FIELD_LIMITS, InvitationEmailTemplateStore,
    InvitationTemplateError, validate_template,
)


class TemplateStoreTests(unittest.TestCase):
    def test_defaults_are_read_only_and_each_load_is_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = IdentityPaths(Path(folder)/'identity')
            store = InvitationEmailTemplateStore(paths)
            loaded = store.load();loaded['heading']='changed'
            self.assertEqual(store.load(),DEFAULT_TEMPLATE)
            self.assertFalse(paths.root.exists())

    def test_saved_copy_survives_new_store_without_recovery_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = IdentityPaths(Path(folder)/'identity')
            custom = {**DEFAULT_TEMPLATE,'heading':'Welcome, friends!','welcome':'First line\nSecond line'}
            InvitationEmailTemplateStore(paths).save(custom)
            self.assertEqual(InvitationEmailTemplateStore(paths).load(),custom)
            self.assertFalse(paths.password_recovery_root.exists())
            self.assertEqual((paths.invitations_root/'email-template.json').stat().st_mode & 0o777,0o644)
            self.assertFalse(list(paths.invitations_root.glob('.email-template-*')))

    def test_validation_refuses_headers_blank_extra_and_overlong_fields(self):
        cases = [dict(DEFAULT_TEMPLATE,subject='Hello\r\nBcc: attacker@example.test'),
                 dict(DEFAULT_TEMPLATE,heading='  '),dict(DEFAULT_TEMPLATE,button_label=4),
                 dict(DEFAULT_TEMPLATE,token='must-not-be-editable')]
        for key,limit in FIELD_LIMITS.items():cases.append(dict(DEFAULT_TEMPLATE,**{key:'x'*(limit+1)}))
        for case in cases:
            with self.subTest(case=case),self.assertRaises(InvitationTemplateError):validate_template(case)

    def test_corrupt_or_symlink_document_never_silently_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=IdentityPaths(Path(folder)/'identity');store=InvitationEmailTemplateStore(paths)
            store.save(DEFAULT_TEMPLATE)
            store.path.write_text('{broken')
            with self.assertRaises(InvitationTemplateError):store.load()
            store.path.unlink();other=Path(folder)/'other';other.write_text('{}')
            store.path.symlink_to(other)
            with self.assertRaises(InvitationTemplateError):store.load()
            with self.assertRaises(InvitationTemplateError):store.save(DEFAULT_TEMPLATE)
            self.assertEqual(other.read_text(),'{}')


if __name__=='__main__':unittest.main()
