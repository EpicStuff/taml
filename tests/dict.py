import os
import unittest
from pathlib import Path

from taml import taml, required, strict, repeat, RequiredError, StrictError, StructureError
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaDict(unittest.TestCase):
	def test_dict_schema_bare_builtin(self):
		'''Verify dict-schema bare builtin.'''
		# bare builtin converts value
		schema_py = {'a': int}
		assert taml.loads('a: "1"\n', schema_py) == {'a': 1}

	def test_dict_schema_wrong_value_errors(self):
		'''Verify dict-schema wrong value errors.'''
		schema_py = {'a': int}
		assert_raises((TypeError, ValueError), lambda: taml.loads("a: 'nope'\n", schema_py))

	def test_dict_schema_wrong_type_errors(self):
		'''Verify dict-schema wrong type errors.'''
		schema_py = {'a': int}
		assert_raises((TypeError, ValueError), lambda: taml.loads('a: []\n', schema_py))

	def test_dict_schema_missing_key_not_inserted(self):
		'''Verify dict-schema missing key not inserted.'''
		schema_py = {'a': int}
		assert 'a' not in taml.loads('{}\n', schema_py)

	def test_dict_schema_null_preserved(self):
		'''Verify dict-schema null preserved.'''
		schema_py = {'a': int}
		assert taml.loads('a: null\n', schema_py)['a'] is None

	def test_dict_schema_nested_converts_value(self):
		'''Verify dict-schema nested converts value.'''
		# nested dict schema
		schema_nested_py = {'a': {'b': int}}
		assert taml.loads('a: {b: "5"}\n', schema_nested_py) == {'a': {'b': 5}}

	def test_dict_schema_nested_preserves_null_parent(self):
		'''Verify dict-schema nested preserves null parent.'''
		# nested dict schema
		schema_nested_py = {'a': {'b': int}}
		assert taml.loads('a:\n', schema_nested_py) == {'a': None}

	def test_dict_schema_nested_allows_empty_dict(self):
		'''Verify dict-schema nested allows empty dict.'''
		# nested dict schema
		schema_nested_py = {'a': {'b': int}}
		assert taml.loads('a: {}\n', schema_nested_py) == {'a': {}}

	def test_dict_schema_list_keeps_unmatched_items(self):
		'''Verify dict-schema list keeps unmatched items.'''
		# list inside dict schema, plus structure mismatches
		schema_list_py = {'lst': [int]}
		assert taml.loads("lst: ['1', '2']\n", schema_list_py) == {'lst': [1, '2']}

	def test_dict_schema_list_rejects_dict(self):
		'''Verify dict-schema list rejects dict.'''
		# list inside dict schema, plus structure mismatches
		schema_list_py = {'lst': [int]}
		assert_raises(StructureError, lambda: taml.loads('lst: {a: 1}\n', schema_list_py))

	def test_dict_schema_list_rejects_scalar(self):
		'''Verify dict-schema list rejects scalar.'''
		# list inside dict schema, plus structure mismatches
		schema_list_py = {'lst': [int]}
		assert_raises(StructureError, lambda: taml.loads('lst: 1\n', schema_list_py))

	def test_dict_schema_list_repeat_marker(self):
		'''Verify dict-schema list repeat marker.'''
		# list inside dict schema: explicit repeat marker covers every item
		schema_list_py = {'lst': [repeat(int)]}
		assert taml.loads("lst: ['1', '2']\n", schema_list_py) == {'lst': [1, 2]}

	def test_dict_schema_bare_repeat_value_converts_items(self):
		'''Verify dict-schema bare repeat value converts items.'''
		# bare repeat(int) as a value behaves the same as [repeat(int)]
		schema_list_bare = {'lst': repeat(int)}
		assert taml.loads("lst: ['1', '2']\n", schema_list_bare) == {'lst': [1, 2]}

	def test_dict_schema_bare_repeat_value_rejects_dict(self):
		'''Verify dict-schema bare repeat value rejects dict.'''
		# bare repeat(int) as a value behaves the same as [repeat(int)]
		schema_list_bare = {'lst': repeat(int)}
		assert_raises(StructureError, lambda: taml.loads('lst: {a: 1}\n', schema_list_bare))

	def test_dict_schema_bare_repeat_value_rejects_scalar(self):
		'''Verify dict-schema bare repeat value rejects scalar.'''
		# bare repeat(int) as a value behaves the same as [repeat(int)]
		schema_list_bare = {'lst': repeat(int)}
		assert_raises(StructureError, lambda: taml.loads('lst: 1\n', schema_list_bare))

	def test_dict_schema_required_instance_missing_key(self):
		'''Verify dict-schema required instance missing key.'''
		# required and strict instances used directly
		schema_req_py = {'a': required('a', 0, 0)}
		assert_raises(RequiredError, lambda: taml.loads('{}\n', schema_req_py))

	def test_dict_schema_required_instance_null(self):
		'''Verify dict-schema required instance null.'''
		# required and strict instances used directly
		schema_req_py = {'a': required('a', 0, 0)}
		assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema_req_py))

	def test_dict_schema_required_instance_present(self):
		'''Verify dict-schema required instance present.'''
		# required and strict instances used directly
		schema_req_py = {'a': required('a', 0, 0)}
		assert taml.loads("a: 'present'\n", schema_req_py) == {'a': 'present'}

	def test_dict_schema_strict_instance_accepts_int(self):
		'''Verify dict-schema strict instance accepts int.'''
		# required and strict instances used directly
		schema_strict_py = {'a': strict('a', 0, 0, int)}
		assert taml.loads('a: 1\n', schema_strict_py) == {'a': 1}

	def test_dict_schema_strict_instance_rejects_str(self):
		'''Verify dict-schema strict instance rejects str.'''
		# required and strict instances used directly
		schema_strict_py = {'a': strict('a', 0, 0, int)}
		assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema_strict_py))


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaDict).debug()
	print('tests passed')
