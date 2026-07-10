import os
import unittest
from pathlib import Path

from taml import taml, RequiredError, StrictError, SchemaDefinitionError
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaStrict(unittest.TestCase):
	def test_strict_type_accepts_int(self):
		'''Verify strict type accepts int.'''
		schema = taml.loads('a: taml.strict(int)\n', is_schema=True)
		assert taml.loads('a: 1\n', schema) == {'a': 1}

	def test_strict_type_preserves_null(self):
		'''Verify strict type preserves null.'''
		schema = taml.loads('a: taml.strict(int)\n', is_schema=True)
		assert taml.loads('a: null\n', schema) == {'a': None}

	def test_strict_type_allows_missing_key(self):
		'''Verify strict type allows missing key.'''
		schema = taml.loads('a: taml.strict(int)\n', is_schema=True)
		assert taml.loads('{}\n', schema) == {}

	def test_strict_type_rejects_str(self):
		'''Verify strict type rejects str.'''
		schema = taml.loads('a: taml.strict(int)\n', is_schema=True)
		assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema), "Expected int, got str: '1' (line 1, col 4)")

	def test_strict_wrapping_required_accepts_int(self):
		'''Verify strict wrapping required accepts int.'''
		schema = taml.loads('a: taml.strict(taml.required(int))\n', is_schema=True)
		assert taml.loads('a: 1\n', schema) == {'a': 1}

	def test_strict_wrapping_required_rejects_str(self):
		'''Verify strict wrapping required rejects str.'''
		schema = taml.loads('a: taml.strict(taml.required(int))\n', is_schema=True)
		assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema), "Expected int, got str: '1' (line 1, col 4)")

	def test_strict_wrapping_required_missing_key(self):
		'''Verify strict wrapping required missing key.'''
		schema = taml.loads('a: taml.strict(taml.required(int))\n', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')

	def test_strict_wrapping_required_null(self):
		'''Verify strict wrapping required null.'''
		schema = taml.loads('a: taml.strict(taml.required(int))\n', is_schema=True)
		assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

	def test_strict_required_missing_args(self):
		'''Verify strict required missing args.'''
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict(taml.required)\n', is_schema=True),
			'Missing arguments for required inside strict at a (line 1, col 4)',
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaStrict).debug()
	print('tests passed')
