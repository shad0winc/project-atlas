"""Completion-only context comparison with mandatory native generation admission.

Never use this comparator to validate or renew a historical private receipt. The
original owner-preservation context remains immutable. A source-verified host
driver must supply generation_admission and independently establish fresh gates,
external admission and transition authority. This module performs no I/O.
"""
import hashlib
import json
import re


class CompletionContextError(RuntimeError):
    pass


def require(value):
    if not value:
        raise CompletionContextError('completion_context_refused')


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def freeze(value):
    require(isinstance(value,dict))
    try:
        return json.loads(encoded(value))
    except (ValueError,TypeError):
        raise CompletionContextError('completion_context_refused') from None


def compare_completion_context(expected,current,*,generation_admission):
    require(callable(generation_admission))
    expected=freeze(expected);current=freeze(current)
    keys={'publication_id','original_owner','source','runtime','intent_sha256',
          'record_manifest_sha256','current_sha256','generation_sha256'}
    require(set(expected)==set(current)==keys)
    for context in (expected,current):
        require(isinstance(context['publication_id'],str) and
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',context['publication_id']))
        for name in ('original_owner','source','runtime'):
            require(isinstance(context[name],dict) and bool(context[name]))
        for name in ('intent_sha256','record_manifest_sha256','current_sha256','generation_sha256'):
            require(isinstance(context[name],str) and re.fullmatch('[a-f0-9]{64}',context[name]))
    require(all(expected[name]==current[name] for name in keys-{'generation_sha256'}))
    before=(encoded(expected),encoded(current))
    # Always run the native verifier, even when aggregate hashes happen to match.
    # A dictionary or boolean is not an executable generation verifier.
    require(generation_admission(expected,current) is None)
    require((encoded(expected),encoded(current))==before)
    return dict(schema_version=1,scope='completion-context-equivalence-only',
        publication_id=current['publication_id'],
        original_context_sha256=hashlib.sha256(before[0]).hexdigest(),
        current_context_sha256=hashlib.sha256(before[1]).hexdigest(),
        generation_fingerprint_changed=expected['generation_sha256']!=current['generation_sha256'],
        native_generation_admission_completed=True,
        historical_receipt_revalidated=False,fresh_private_acceptance_proven=False,
        external_admission_proven=False,production_completion_permitted=False,
        public_reopen_permitted=False)
