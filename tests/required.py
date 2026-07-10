import os
import unittest
from pathlib import Path

from epicstuff import s
from taml import taml, RequiredError, ConversionTypeError, ConversionValueError
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaRequired(unittest.TestCase):
	def test_required_bare_missing_key(self):
		'''Verify required bare missing key.'''
		schema = taml.loads( 'a: taml.required', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')

	def test_required_bare_null(self):
		'''Verify required bare null.'''
		schema = taml.loads( 'a: taml.required', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

	def test_required_with_type_missing_key(self):
		'''Verify required with type missing key.'''
		schema = taml.loads( 'a: taml.required(int)', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')

	def test_required_with_type_null(self):
		'''Verify required with type null.'''
		schema = taml.loads( 'a: taml.required(int)', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

	def test_required_with_type_coerces_present(self):
		'''Verify required with type coerces present.'''
		schema = taml.loads('a: taml.required(int)', is_schema=True)
		assert taml.loads('a: "1"\n', schema) == {'a': 1}

	def test_required_with_type_coerces_missing_key(self):
		'''Verify required with type coerces missing key.'''
		schema = taml.loads('a: taml.required(int)', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')

	def test_required_with_type_coerces_null(self):
		'''Verify required with type coerces null.'''
		schema = taml.loads('a: taml.required(int)', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

	def test_missing_keys_safe_callable(self):
		'''Verify missing keys safe callable.'''
		schema_safe = taml.loads('a: str\n', is_schema=True)
		out = taml.loads('{}\n', schema_safe)
		assert 'a' not in out  # schema should not insert keys

	def test_missing_keys_strict_callable_does_not_insert_missing_key(self):
		'''Verify missing keys strict callable does not insert missing key.'''
		schema_strict = taml.loads('a: int\n', is_schema=True)
		out = taml.loads('{}\n', schema_strict)
		assert 'a' not in out  # missing keys should not error unless required

	def test_missing_keys_strict_callable_preserves_null(self):
		'''Verify missing keys strict callable preserves null.'''
		schema_strict = taml.loads('a: int\n', is_schema=True)
		out = taml.loads('a: null\n', schema_strict)
		assert out['a'] is None

	def test_missing_keys_strict_callable_rejects_wrong_type(self):
		'''Verify missing keys strict callable rejects wrong type.'''
		schema_strict = taml.loads('a: int\n', is_schema=True)
		assert_raises(ConversionTypeError, lambda: taml.loads('a: []\n', schema_strict), 'Cannot convert [] to int (line 1, col 4)')

	def test_missing_keys_strict_callable_rejects_bad_value(self):
		'''Verify missing keys strict callable rejects bad value.'''
		schema_strict = taml.loads('a: int\n', is_schema=True)
		assert_raises(ConversionValueError, lambda: taml.loads("a: 'nope'\n", schema_strict), "Cannot convert 'nope' to int (line 1, col 4)")

	def test_missing_keys_nested_empty_dict(self):
		'''Verify missing keys nested empty dict.'''
		schema_nested = taml.loads(
			s('''
				a:
					b: int
			'''),
			is_schema=True,
		)

		assert taml.loads('a: {}\n', schema_nested) == {'a': {}}

	def test_missing_keys_nested_null_parent(self):
		'''Verify missing keys nested null parent.'''
		schema_nested = taml.loads(
			s('''
				a:
					b: int
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n', schema_nested) == {'a': None}

	def test_missing_keys_nested_inline_null_child(self):
		'''Verify missing keys nested inline null child.'''
		schema_nested = taml.loads(
			s('''
				a:
					b: int
			'''),
			is_schema=True,
		)
		assert taml.loads('a: {b: null}\n', schema_nested) == {'a': {'b': None}}

	def test_missing_keys_nested_block_null_child(self):
		'''Verify missing keys nested block null child.'''
		schema_nested = taml.loads(
			s('''
				a:
					b: int
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n\tb:\n', schema_nested) == {'a': {'b': None}}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaRequired).debug()
	print('tests passed')
