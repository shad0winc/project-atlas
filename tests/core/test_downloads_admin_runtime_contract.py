from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_admin_roles_and_operator_can_manage_downloads() -> None:
    catalog=(ROOT/'apps/api/atlas_api/authorization/catalog.py').read_text()
    assert catalog.count('"downloads.*"') >= 2
    assert '"downloads.manage"' in catalog

def test_host_publisher_requires_shared_job_id_key() -> None:
    script=(ROOT/'scripts/atlas-downloads-runtime.sh').read_text()
    assert 'ATLAS_DOWNLOADS_JOB_ID_KEY:?ATLAS_DOWNLOADS_JOB_ID_KEY is required' in script
    assert 'job_id_key=os.environ["ATLAS_DOWNLOADS_JOB_ID_KEY"]' in script

def test_api_has_no_qbittorrent_credentials_or_job_key() -> None:
    compose=(ROOT/'stack/ingress.yml').read_text()
    api=compose.split('  api:\n',1)[1].split('\n  downloads-writer:\n',1)[0]
    assert 'ATLAS_DOWNLOADS_WRITER_URL' in api
    assert 'ATLAS_DOWNLOADS_WRITER_TOKEN' in api
    assert 'ATLAS_QBITTORRENT_USERNAME' not in api
    assert 'ATLAS_QBITTORRENT_PASSWORD' not in api
    assert 'ATLAS_DOWNLOADS_JOB_ID_KEY' not in api

def test_downloads_writer_is_private_and_non_file_deleting() -> None:
    compose=(ROOT/'stack/ingress.yml').read_text()
    block=compose.split('  downloads-writer:\n',1)[1].split('\n  identity-writer:\n',1)[0]
    assert '- atlas-identity' in block
    assert 'ports:' not in block
    assert 'ATLAS_QBITTORRENT_USERNAME:' in block
    assert 'ATLAS_QBITTORRENT_PASSWORD:' in block
    assert 'ATLAS_DOWNLOADS_JOB_ID_KEY:' in block
    assert 'read_only: true' in block
    assert 'no-new-privileges:true' in block
    writer=(ROOT/'apps/api/atlas_api/downloads_writer.py').read_text()
    assert '"deleteFiles": "false"' in writer
    assert '"deleteFiles": "true"' not in writer
