import copy
import math
import unittest
from atlas.deployment_completion_context import compare_completion_context,CompletionContextError


class CompletionContextTests(unittest.TestCase):
    def setUp(self):
        self.expected=dict(publication_id='fixture-publication',original_owner={'deployment_id':'fixture-owner'},
            source={'commit':'fixture-source'},runtime={'fixture-container':{'identity':'fixture'}},
            intent_sha256='1'*64,record_manifest_sha256='2'*64,current_sha256='3'*64,generation_sha256='4'*64)
        self.current=copy.deepcopy(self.expected)
        self.calls=[]
    def admit(self,expected,current):self.calls.append((copy.deepcopy(expected),copy.deepcopy(current)))
    def run_compare(self,admit=None):
        return compare_completion_context(self.expected,self.current,generation_admission=self.admit if admit is None else admit)
    def test_equal_context_still_requires_native_admission(self):
        result=self.run_compare();self.assertEqual(len(self.calls),1)
        self.assertFalse(result['generation_fingerprint_changed'])
    def test_generation_difference_requires_native_admission_and_grants_no_permission(self):
        self.current['generation_sha256']='5'*64
        result=self.run_compare();self.assertEqual(len(self.calls),1)
        self.assertTrue(result['generation_fingerprint_changed'])
        for name in ('historical_receipt_revalidated','fresh_private_acceptance_proven','external_admission_proven','production_completion_permitted','public_reopen_permitted'):
            self.assertFalse(result[name])
    def test_other_component_changes_refuse_before_callback(self):
        for name in self.expected.keys()-{'generation_sha256'}:
            with self.subTest(name=name):
                self.current=copy.deepcopy(self.expected)
                value=self.current[name]
                self.current[name]=dict(value,unexpected='change') if isinstance(value,dict) else ('6'*64 if name.endswith('sha256') else 'other-publication')
                with self.assertRaises(CompletionContextError):self.run_compare()
        self.assertEqual(self.calls,[])
    def test_native_verifier_refusal_propagates(self):
        def refuse(*args):raise RuntimeError('fixture-native-refusal')
        with self.assertRaisesRegex(RuntimeError,'fixture-native-refusal'):self.run_compare(refuse)
    def test_missing_verifier_refuses(self):
        with self.assertRaises(CompletionContextError):compare_completion_context(self.expected,self.current,generation_admission=None)
    def test_boolean_or_dictionary_verifier_result_refuses(self):
        for value in (True,False,{'verified':True}):
            with self.subTest(value=value),self.assertRaises(CompletionContextError):self.run_compare(lambda *args:value)
    def test_mutating_callback_refuses_and_caller_context_is_preserved(self):
        original=copy.deepcopy(self.current)
        def mutate(expected,current):current['generation_sha256']='7'*64
        with self.assertRaises(CompletionContextError):self.run_compare(mutate)
        self.assertEqual(self.current,original)
    def test_malformed_fingerprint_refuses(self):
        self.current['generation_sha256']='unverified'
        with self.assertRaises(CompletionContextError):self.run_compare()
    def test_unknown_or_missing_context_fields_refuse(self):
        self.current['unexpected']='field'
        with self.assertRaises(CompletionContextError):self.run_compare()
        self.current=copy.deepcopy(self.expected);self.current.pop('runtime')
        with self.assertRaises(CompletionContextError):self.run_compare()
    def test_nonfinite_context_values_refuse(self):
        self.current['runtime']['fixture-container']['value']=math.nan
        with self.assertRaises(CompletionContextError):self.run_compare()


if __name__=='__main__':unittest.main()
