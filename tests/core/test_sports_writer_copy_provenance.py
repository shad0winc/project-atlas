"""Exercise the real writer COPY layout, including its shared Atlas input."""
from pathlib import Path
import hashlib,io,json,tarfile,unittest
from tests.core import test_sports_provenance_extension as foundation
M=foundation.M
WRITER_DOCKERFILE=b'FROM python:3.13-slim\n\nARG PUID\nARG PGID\n\nRUN test -n "${PUID}" \\\n    && test -n "${PGID}" \\\n    && groupadd --gid "${PGID}" atlas \\\n    && useradd \\\n        --uid "${PUID}" \\\n        --gid atlas \\\n        --no-create-home \\\n        --shell /usr/sbin/nologin \\\n        atlas\n\nWORKDIR /srv/sports\n\nCOPY modules/sports/src/private_api.py /srv/sports/private_api.py\nCOPY modules/sports/src/atlas_live_policy_claim.py /srv/sports/atlas_live_policy_claim.py\nCOPY modules/sports/src/shared_admission.py /srv/sports/shared_admission.py\nCOPY atlas/sports_shared_admission_config.py /srv/sports/sports_shared_admission_config.py\nCOPY modules/sports/src/games_state.py /srv/sports/games_state.py\nCOPY modules/sports/src/dispatcharr_admin.py /srv/sports/dispatcharr_admin.py\nCOPY modules/sports/src/dispatcharr_channel_bindings.py /srv/sports/dispatcharr_channel_bindings.py\nCOPY modules/sports/src/live_tv_bindings.py /srv/sports/live_tv_bindings.py\nCOPY modules/sports/src/live_sources.py /srv/sports/live_sources.py\nCOPY modules/sports/src/subscriptions.py /srv/sports/subscriptions.py\nCOPY modules/sports/src/source_lifecycle.py /srv/sports/source_lifecycle.py\nCOPY modules/sports/src/providers /srv/sports/providers\nCOPY modules/sports/config/metadata-refresh.disabled.json /srv/sports/metadata-refresh.disabled.json\n\nENV PYTHONDONTWRITEBYTECODE="1" \\\n    PYTHONPATH="/srv/sports"\n\nUSER atlas\n\nCMD ["python3", "/srv/sports/private_api.py"]\n'
WRITER_DOCKERFILE_SHA256='be959c51edfe92a9f90c3679abd15f5e507d1c124338106524d3640dd95cd690'
COPIED_INPUTS=['atlas/sports_shared_admission_config.py', 'modules/sports/config/metadata-refresh.disabled.json', 'modules/sports/src/atlas_live_policy_claim.py', 'modules/sports/src/dispatcharr_admin.py', 'modules/sports/src/dispatcharr_channel_bindings.py', 'modules/sports/src/games_state.py', 'modules/sports/src/live_sources.py', 'modules/sports/src/live_tv_bindings.py', 'modules/sports/src/private_api.py', 'modules/sports/src/providers/__init__.py', 'modules/sports/src/providers/base.py', 'modules/sports/src/providers/espn_directory.py', 'modules/sports/src/providers/espn_metadata.py', 'modules/sports/src/providers/metadata_broker.py', 'modules/sports/src/providers/metadata_client.py', 'modules/sports/src/providers/metadata_discovery.py', 'modules/sports/src/providers/metadata_identity.py', 'modules/sports/src/providers/metadata_refresh.py', 'modules/sports/src/providers/metadata_schedule.py', 'modules/sports/src/providers/metadata_service.py', 'modules/sports/src/providers/metadata_store.py', 'modules/sports/src/providers/registry.py', 'modules/sports/src/providers/thesportsdb.py', 'modules/sports/src/shared_admission.py', 'modules/sports/src/source_lifecycle.py', 'modules/sports/src/subscriptions.py']

class WriterCopyProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=foundation.SportsProvenanceTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.record=f.record
        # Preserve the accepted Dockerfile byte for byte. The copied contents are
        # synthetic; no application is imported or provider contacted.
        f.files['modules/sports/Dockerfile.private-api']=WRITER_DOCKERFILE
        for name in COPIED_INPUTS:
            if name not in f.files:f.files[name]=('fixture bytes for '+name+'\n').encode()
        self.repack()

    def repack(self):
        f=self.fixture
        with tarfile.open(self.record/'sports-application-source.tar.gz','w:gz',format=tarfile.PAX_FORMAT,pax_headers={'comment':f.commit}) as archive:
            for name,raw in f.files.items():
                item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;archive.addfile(item,io.BytesIO(raw))
        archived=M.archive_files(self.record/'sports-application-source.tar.gz')
        tree=M.extension_module().tree_oid(archived)
        f.put('sports-application-tracked.json',dict(commit=f.commit,tree=tree,files=[dict(path=n,mode='100644',oid=r['oid']) for n,r in archived.items()]))
        f.ext['source_tree']=tree
        f.ext['components']['writer']['installed_file_sha256']=M.expected_copies(archived)
        f.validation['components']['writer']['source_files']={name:hashlib.sha256(f.files[name]).hexdigest() for name in ['modules/sports/Dockerfile.private-api',*COPIED_INPUTS]}
        f.put('sports-runtime-extension.json',f.ext);f.put('sports-image-validation.json',f.validation)
        f.gate['source_tree']=tree;f.put('sports-release-gate.json',f.gate)
        values=M.metadata(self.record);values['sports_extension_tree']=tree
        f.fixture.fixture.write_metadata(self.record,values);M.seal(self.record)

    def validation_change(self,change):
        value=json.loads((self.record/'sports-image-validation.json').read_bytes())
        change(value['components']['writer']['source_files'])
        self.fixture.put('sports-image-validation.json',value);M.seal(self.record)
    def refuse(self):
        with self.assertRaises(ValueError):M.check_record(self.record)

    def test_exact_accepted_dockerfile_with_all_27_build_inputs_passes(self):
        self.assertEqual(hashlib.sha256(WRITER_DOCKERFILE).hexdigest(),WRITER_DOCKERFILE_SHA256)
        self.assertEqual(len(COPIED_INPUTS),26)
        ledger,_,_=M.check_record(self.record)
        copied=ledger['ingress']['overrides']['sports-writer']['copied_file_sha256']
        self.assertIn('/srv/sports/sports_shared_admission_config.py',copied)
        self.assertIn('/srv/sports/metadata-refresh.disabled.json',copied)

    def test_missing_shared_atlas_helper_build_pin_refuses(self):
        self.validation_change(lambda d:d.pop('atlas/sports_shared_admission_config.py'));self.refuse()

    def test_missing_non_python_configuration_build_pin_refuses(self):
        self.validation_change(lambda d:d.pop('modules/sports/config/metadata-refresh.disabled.json'));self.refuse()

    def test_wrong_shared_helper_build_hash_refuses(self):
        self.validation_change(lambda d:d.update({'atlas/sports_shared_admission_config.py':'0'*64}));self.refuse()

    def test_an_unrelated_atlas_module_is_not_allowed(self):
        name='atlas/unrelated.py';self.fixture.files[name]=b'fixture=True\n';self.repack()
        self.validation_change(lambda d:d.update({name:hashlib.sha256(self.fixture.files[name]).hexdigest()}));self.refuse()

    def test_every_real_copy_input_is_required_individually(self):
        original=(self.record/'sports-image-validation.json').read_bytes()
        for name in COPIED_INPUTS:
            with self.subTest(source=name):
                (self.record/'sports-image-validation.json').write_bytes(original)
                self.validation_change(lambda d:d.pop(name));self.refuse()

if __name__=='__main__':unittest.main()
