import importlib
import json
from pathlib import Path
from unittest.mock import Mock,patch

from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import pytest

from atlas.identity import IdentityPaths
from atlas.invitation_email_template import DEFAULT_TEMPLATE,InvitationEmailTemplateStore
from atlas_api.routes.v1 import admin_invitations as route
from atlas_api.dependencies import get_identity_writer_client
from atlas_api.services.email_sender import SMTPEmailSender
from atlas_api.services.identity_writer import IdentityWriterClient


def test_public_template_routes_require_update_permission_and_validate_before_writer(tmp_path):
    app=FastAPI();app.include_router(route.router)
    paths=IdentityPaths(tmp_path/'identity')
    def denied():raise HTTPException(403,'Forbidden')
    app.dependency_overrides[route.require_invitations_update]=denied
    writer=Mock();app.dependency_overrides[get_identity_writer_client]=lambda:writer
    client=TestClient(app)
    assert client.get('/admin/invitations/email-template').status_code==403
    assert client.put('/admin/invitations/email-template',json={'template':DEFAULT_TEMPLATE}).status_code==403
    writer.update_invitation_email_template.assert_not_called()
    app.dependency_overrides[route.require_invitations_update]=lambda:object()
    with patch.object(route,'default_identity_paths',return_value=paths):
        response=client.get('/admin/invitations/email-template')
        assert response.status_code==200 and response.json()['template']==DEFAULT_TEMPLATE
        assert not paths.root.exists()
        assert client.put('/admin/invitations/email-template',json={'template':{}}).status_code==422
        writer.update_invitation_email_template.assert_not_called()
        writer.update_invitation_email_template.return_value={'template':DEFAULT_TEMPLATE}
        response=client.put('/admin/invitations/email-template',json={'template':DEFAULT_TEMPLATE})
        assert response.status_code==200
        writer.update_invitation_email_template.assert_called_once_with(DEFAULT_TEMPLATE)


def test_identity_writer_requires_token_and_persists_in_invitation_mount(monkeypatch,tmp_path):
    monkeypatch.setenv('ATLAS_IDENTITY_WRITER_TOKEN','template-test-token')
    monkeypatch.setenv('ATLAS_IDENTITY_DIR',str(tmp_path/'identity'))
    writer=importlib.reload(importlib.import_module('atlas_api.identity_writer'))
    client=TestClient(writer.app)
    custom={**DEFAULT_TEMPLATE,'subject':'Join our Atlas community','heading':'Come on in!'}
    endpoint='/internal/v1/invitation-email-template'
    assert client.put(endpoint,json={'template':custom}).status_code==401
    response=client.put(endpoint,json={'template':custom},headers={'Authorization':'Bearer template-test-token'})
    assert response.status_code==200,response.text
    paths=IdentityPaths(tmp_path/'identity')
    assert InvitationEmailTemplateStore(paths).load()==custom
    assert not paths.password_recovery_root.exists()
    response=client.put(endpoint,json={'template':dict(custom,subject='bad\nSubject')},headers={'Authorization':'Bearer template-test-token'})
    assert response.status_code==422
    assert InvitationEmailTemplateStore(paths).load()==custom


def test_client_uses_private_writer_endpoint():
    client=IdentityWriterClient('http://writer.test','private-token')
    with patch.object(client,'_request',return_value={'template':DEFAULT_TEMPLATE}) as request:
        client.update_invitation_email_template(DEFAULT_TEMPLATE)
    request.assert_called_once_with('PUT','/internal/v1/invitation-email-template',{'template':DEFAULT_TEMPLATE})


def test_saved_copy_is_escaped_and_registration_links_remain_generated():
    sender=SMTPEmailSender(host='smtp.test',port=587,sender='atlas@example.test');sender._send=Mock()
    custom={**DEFAULT_TEMPLATE,'subject':'Join Atlas','heading':'<script>not HTML</script>',
            'welcome':'Hello & welcome\nYour community awaits.','button_label':'Join us'}
    sender.send_invitation(recipient='friend@example.test',registration_url='https://atlas.test/register#token=generated',expires_at='2030-01-01T00:00:00Z',template=custom)
    message=sender._send.call_args.args[0]
    assert message['Subject']=='Join Atlas'
    html=message.get_body(preferencelist=('html',)).get_content()
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'Hello &amp; welcome<br>Your community awaits.' in html
    assert html.count('href="https://atlas.test/register#token=generated"')==2
    assert 'Join us' in html
    assert '<script>not HTML</script>' in message.get_body(preferencelist=('plain',)).get_content()


def test_delivery_reads_saved_template_for_each_future_email(monkeypatch,tmp_path):
    from atlas_api.services.invitation_email import deliver_invitation_email
    for key,value in {
        'ATLAS_IDENTITY_DIR':str(tmp_path/'identity'), 'ATLAS_JWT_SECRET':'x'*32,
        'ATLAS_BASE_URL':'https://atlas.example.test','ATLAS_SMTP_HOST':'smtp.test',
        'ATLAS_SMTP_SENDER':'atlas@example.test',
    }.items():monkeypatch.setenv(key,value)
    store=InvitationEmailTemplateStore(IdentityPaths(tmp_path/'identity'))
    store.save({**DEFAULT_TEMPLATE,'subject':'A fresh invitation','heading':'Your community awaits'})
    with patch('atlas_api.services.email_sender.smtplib.SMTP') as smtp:
        assert deliver_invitation_email(recipient='friend@example.test',token='generated',
                                        expires_at='2030-01-01T00:00:00Z')=='accepted'
    message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert message['Subject']=='A fresh invitation'
    for kind in ('plain','html'):
        assert 'Your community awaits' in message.get_body(preferencelist=(kind,)).get_content()
