"""Native schema-3 records cannot silently rewrite or downgrade their base."""
from pathlib import Path
import copy, hashlib, io, json, shutil, subprocess, tarfile, unittest
from unittest.mock import patch
from tests.core import test_ingress_provenance_extension as ingress

M=ingress.M

class SportsProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ingress.IngressExtensionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.base=self.fixture.record;self.record=self.base.parent/'sports-successor-fixture'
        shutil.copytree(self.base,self.record)
        self.commit='f'*40;self.build_commit='a'*40;self.writer_image='sha256:'+'6'*64;self.backend_image='sha256:'+'7'*64
        self.base_snapshot={p.name:p.read_bytes() for p in self.base.iterdir() if p.is_file()}
        prefix='modules/sports-backend/dispatcharr-live-image/'
        self.files={
            'modules/sports/Dockerfile.private-api':b'COPY modules/sports/src/private_api.py /srv/sports/private_api.py\nCOPY modules/sports/src/providers /srv/sports/providers\n',
            'modules/sports/src/private_api.py':b'new_writer=True\n',
            'modules/sports/src/providers/thesportsdb.py':b'new_provider=True\n',
            prefix+'Dockerfile':b'FROM fixture@sha256:'+b'8'*64+b'\n',
            prefix+'overlay/apps/m3u/policy.py':b'fixture_policy=True\n',
            prefix+'install_worker_environment.py':b'fixture_worker_installer=True\n',
            prefix+'install_live_pilot.py':b'fixture_pilot_installer=True\n',
            prefix+'verify_base.py':b'fixture_base_verifier=True\n',
            prefix+'verify_overlay.py':b'fixture_overlay_verifier=True\n',
        }
        manifest=dict(overlay_files={'apps/m3u/policy.py':self.sha(self.files[prefix+'overlay/apps/m3u/policy.py'])},
            base_image='fixture@sha256:'+'8'*64,worker_environment=dict(installed_entrypoint_sha256='9'*64,
                installer_sha256=self.sha(self.files[prefix+'install_worker_environment.py']),login_launch_sites=3,secret_values_written_to_profile=False))
        self.files[prefix+'manifest.json']=json.dumps(manifest).encode()
        with tarfile.open(self.record/'sports-application-source.tar.gz','w:gz',format=tarfile.PAX_FORMAT,pax_headers={'comment':self.commit}) as archive:
            for name,raw in self.files.items():
                item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;archive.addfile(item,io.BytesIO(raw))
        archived=M.archive_files(self.record/'sports-application-source.tar.gz');self.tree=M.extension_module().tree_oid(archived)
        self.put('sports-application-tracked.json',dict(commit=self.commit,tree=self.tree,files=[dict(path=name,mode='100644',oid=row['oid']) for name,row in archived.items()]))
        S=M.sports_extension_module();backend,_=S.expected_backend(self.record,archived)
        self.ext=dict(schema_version=1,base_publication=dict(id=self.base.name,manifest_sha256=M.digest(self.base/'MANIFEST.sha256')),
            source_archive_commit=self.commit,released_commit=self.commit,source_tree=self.tree,components={})
        self.validation=dict(schema_version=1,components={})
        for role,image,base,installed in (('backend',self.backend_image,'sha256:'+'8'*64,backend),
                                          ('writer',self.writer_image,'sha256:'+'0'*64,M.expected_copies(archived))):
            inputs={name:self.sha(raw) for name,raw in self.files.items() if name.startswith(prefix if role=='backend' else 'modules/sports/')}
            self.ext['components'][role]=dict(image_id=image,base_image_id=base,build_commit=self.build_commit,build_tree='b'*40,
                verified_source_commit=self.commit,installed_file_sha256=installed,validation_receipt_sha256=('c' if role=='writer' else 'd')*64)
            self.validation['components'][role]=dict(image_id=image,source_commit=self.build_commit,source_tree='b'*40,source_files=inputs,
                receipt_sha256=self.ext['components'][role]['validation_receipt_sha256'])
        self.put('sports-runtime-extension.json',self.ext);self.put('sports-image-validation.json',self.validation)
        self.gate=dict(schema_version=1,event='push',head_sha=self.commit,source_tree=self.tree,workflow_path='.github/workflows/release-gate.yml',
            run_id=456,run_attempt=1,conclusion='success',jobs={name:'success' for name in S.JOBS})
        self.put('sports-release-gate.json',self.gate)
        rows=S.image_rows(M.read(self.base/'images.tsv'));rows['/atlas-sports-writer'][5:]=[self.writer_image,self.writer_image]
        rows['/atlas-dispatcharr']=['sports','modules/sports-backend/docker-compose.yml','sports-backend','dispatcharr','/atlas-dispatcharr',self.backend_image,self.backend_image]
        (self.record/'images.tsv').write_text(''.join('|'.join(row)+'\n' for row in rows.values()))
        values=M.metadata(self.record);values.update(S.MARKERS);values.update(source_claim=S.SOURCE_CLAIM,
            deployment_id=self.record.name,scope='sports',previous_baseline=self.base.name,base_publication=self.base.name,
            sports_extension_commit=self.commit,sports_extension_tree=self.tree)
        self.fixture.fixture.write_metadata(self.record,values);M.seal(self.record)

    @staticmethod
    def sha(raw):return hashlib.sha256(raw).hexdigest()
    def put(self,name,value):(self.record/name).write_text(json.dumps(value))
    def tamper(self,name,change):
        value=json.loads((self.record/name).read_bytes());change(value);self.put(name,value);M.seal(self.record)
    def refuse(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):M.check_record(self.record)

    def test_effective_writer_and_backend_are_independent_of_preserved_controller(self):
        ledger,files,activation=M.check_record(self.record)
        self.assertEqual(ledger['ingress']['overrides']['sports-writer']['code_commit'],self.commit)
        self.assertEqual(ledger['ingress']['overrides']['sports-writer']['image_build_commit'],self.build_commit)
        self.assertEqual(ledger['sports']['controller_source_commit'],self.fixture.fixture.new)
        self.assertEqual(ledger['sports']['backend']['image'],self.backend_image)
        self.assertEqual({p.name:p.read_bytes() for p in self.base.iterdir() if p.is_file()},self.base_snapshot)

    def test_both_old_schemas_remain_valid(self):
        M.check_record(self.base);M.check_record(self.fixture.fixture.record)

    def test_native_successor_proof_binds_previous_and_current_manifests(self):
        proof=M.sports_extension_module().successor_proof(M,self.record,self.base.name)
        self.assertEqual(proof,dict(previous_publication=self.base.name,successor_publication=self.record.name,
            previous_manifest_sha256=M.digest(self.base/'MANIFEST.sha256'),successor_manifest_sha256=M.digest(self.record/'MANIFEST.sha256')))
        with self.assertRaises(ValueError):M.sports_extension_module().successor_proof(M,self.record,'another-base')

    def test_live_use_refuses_before_any_docker_or_service_query(self):
        with patch.object(M,'inspect',side_effect=AssertionError('must not query Docker')):
            with self.assertRaisesRegex(ValueError,'pending held Sports adapter'):M.check_live(self.record)

    def test_inheritance_and_restore_refuse_without_writing_destination(self):
        destination=self.record.parent/'destination';destination.mkdir()
        for callback in (lambda:M.inherit(self.record,destination),lambda:M.prepare_restore(self.record,destination)):
            with self.assertRaises(ValueError):callback()
            self.assertEqual(list(destination.iterdir()),[])

    def test_every_supplement_prevents_schema_downgrade(self):
        values=M.metadata(self.record);values.update(M.extension_module().MARKERS);values['source_claim']=M.extension_module().SOURCE_CLAIM
        self.fixture.fixture.write_metadata(self.record,values);M.seal(self.record);self.refuse()

    def test_supplement_only_record_still_detected_as_mixed(self):
        p=self.record.parent/'minimal';p.mkdir();(p/'sports-runtime-extension.json').write_bytes(b'{}')
        self.assertTrue(M.mixed(p))

    def test_native_shell_update_guard_refuses_both_extended_schemas(self):
        script=Path(__file__).resolve().parents[2]/'scripts/commands/deployment.sh'
        for record,schema in ((self.base,'2'),(self.record,'3')):
            result=subprocess.run(['bash','-c','source "$1"; atlas_deployment_validate_update_inheritance "$2" all',
                'fixture',str(script),str(record)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,1)
            self.assertIn(('schema-'+schema+' updates require').encode(),result.stderr)

    def test_missing_supplement_refuses_even_with_resealed_manifest(self):
        (self.record/'sports-image-validation.json').unlink();M.seal(self.record);self.refuse()

    def test_changed_base_manifest_link_refuses(self):
        self.tamper('sports-runtime-extension.json',lambda d:d['base_publication'].update(manifest_sha256='0'*64));self.refuse()

    def test_base_link_cannot_escape_or_link_to_self(self):
        for name in ('../outside',self.record.name,'/tmp/other'):
            self.put('sports-runtime-extension.json',self.ext)
            self.tamper('sports-runtime-extension.json',lambda d:d['base_publication'].update(id=name));self.refuse()

    def test_changed_inherited_recipe_or_ledger_refuses(self):
        for name in ('service-sources.json','maintenance-authority.service','repair-activation.json'):
            original=(self.record/name).read_bytes();(self.record/name).write_bytes(b'changed');M.seal(self.record);self.refuse()
            (self.record/name).write_bytes(original);M.seal(self.record)

    def test_unrelated_metadata_source_change_refuses(self):
        values=M.metadata(self.record);values['core_commit']='0'*40;self.fixture.fixture.write_metadata(self.record,values);M.seal(self.record);self.refuse()

    def test_changed_api_image_refuses(self):
        raw=(self.record/'images.tsv').read_text();raw=raw.replace('sha256:'+'1'*64,'sha256:'+'0'*64)
        (self.record/'images.tsv').write_text(raw);M.seal(self.record);self.refuse()

    def test_extra_unrelated_image_or_duplicate_image_refuses(self):
        original=(self.record/'images.tsv').read_text()
        for row in ('sports|recipe|project|unrelated|/foreign|ref|sha256:'+'a'*64+'\n',original.splitlines()[0]+'\n'):
            (self.record/'images.tsv').write_text(original+row);M.seal(self.record);self.refuse()

    def test_backend_and_writer_effective_image_drift_refuses(self):
        for role in ('writer','backend'):
            self.put('sports-runtime-extension.json',self.ext)
            self.tamper('sports-runtime-extension.json',lambda d:d['components'][role].update(image_id='sha256:'+'a'*64));self.refuse()

    def test_changed_or_incomplete_installed_map_refuses(self):
        self.tamper('sports-runtime-extension.json',lambda d:d['components']['backend']['installed_file_sha256'].clear());self.refuse()

    def test_incorrect_backend_base_refuses(self):
        self.tamper('sports-runtime-extension.json',lambda d:d['components']['backend'].update(base_image_id='sha256:'+'0'*64));self.refuse()

    def test_reused_writer_build_requires_every_input_to_match(self):
        self.tamper('sports-image-validation.json',lambda d:d['components']['writer']['source_files'].update({'modules/sports/src/private_api.py':'0'*64}));self.refuse()

    def test_build_input_coverage_cannot_be_omitted(self):
        self.tamper('sports-image-validation.json',lambda d:d['components']['backend']['source_files'].pop('modules/sports-backend/dispatcharr-live-image/install_live_pilot.py'));self.refuse()

    def test_raw_receipt_identity_cannot_be_substituted(self):
        self.tamper('sports-image-validation.json',lambda d:d['components']['writer'].update(receipt_sha256='0'*64));self.refuse()

    def test_release_gate_requires_exact_successful_push_and_all_six_jobs(self):
        for change in (lambda d:d.update(event='pull_request'),lambda d:d.update(head_sha='0'*40),lambda d:d['jobs'].pop('Sports'),lambda d:d.update(conclusion='failure')):
            self.put('sports-release-gate.json',self.gate);self.tamper('sports-release-gate.json',change);self.refuse()

    def test_tracked_tree_blob_mode_and_coverage_corruption_refuse(self):
        saved=json.loads((self.record/'sports-application-tracked.json').read_bytes())
        for change in (lambda d:d.update(tree='0'*40),lambda d:d['files'][0].update(oid='0'*40),lambda d:d['files'][0].update(mode='100755'),lambda d:d['files'].pop()):
            self.put('sports-application-tracked.json',saved);self.tamper('sports-application-tracked.json',change);self.refuse()

if __name__=='__main__':unittest.main()
