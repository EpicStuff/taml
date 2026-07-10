import os
import unittest
from pathlib import Path

from taml import taml, always, ConversionTypeError, ConversionValueError
from utils import assert_raises


os.chdir(Path(__file__).parent)


def list_convert(tags):
	'Convert csv/null/list to a list.'
	if tags is None:
		tags = []
	elif isinstance(tags, str):
		tags = list(map(str.strip, tags.split(',')))
	return tags


class TestSchemaAlways(unittest.TestCase):
	def test_always_runs_converter_on_present_value(self):
		'''Verify always runs converter on present value.'''
		# plain callable skips null; always makes the converter run on it
		schema = taml.loads('a: taml.always(int)\n', is_schema=True)
		assert taml.loads('a: "1"\n', schema) == {'a': 1}

	def test_always_runs_converter_on_null(self):
		'''Verify always runs converter on null.'''
		# plain callable skips null; always makes the converter run on it
		schema = taml.loads('a: taml.always(int)\n', is_schema=True)
		assert_raises(ConversionTypeError, lambda: taml.loads('a: null\n', schema), 'Cannot convert None to int (line 1, col 4)')

	def test_always_wraps_value_error(self):
		'''Verify always wraps value error.'''
		# always wraps a value-error from the converter, pointing at the value
		schema = taml.loads('a: taml.always(int)\n', is_schema=True)
		assert_raises(ConversionValueError, lambda: taml.loads("a: 'nope'\n", schema), "Cannot convert 'nope' to int (line 1, col 4)")

	def test_always_list_convert_csv(self):
		'''Verify always list convert CSV.'''
		# always(list_convert): csv string, list, and null all become a list
		schema_py = {'tags': always(list_convert)}
		assert taml.loads('tags: a, b, c\n', schema_py) == {'tags': ['a', 'b', 'c']}

	def test_always_list_convert_list(self):
		'''Verify always list convert list.'''
		# always(list_convert): csv string, list, and null all become a list
		schema_py = {'tags': always(list_convert)}
		assert taml.loads('tags: [a, b]\n', schema_py) == {'tags': ['a', 'b']}

	def test_always_list_convert_null(self):
		'''Verify always list convert null.'''
		# always(list_convert): csv string, list, and null all become a list
		schema_py = {'tags': always(list_convert)}
		assert taml.loads('tags: null\n', schema_py) == {'tags': []}

	def test_always_does_not_insert_missing_key(self):
		'''Verify always does not insert missing key.'''
		schema_py = {'tags': always(list_convert)}

		# always still does not insert a missing key
		assert 'tags' not in taml.loads('{}\n', schema_py)

	def test_always_bare_no_func_preserves_value(self):
		'''Verify always bare no func preserves value.'''
		# bare always() (no func) is a no-op, even on null  #todo, this should raise instead
		schema_py = {'a': always()}
		assert taml.loads('a: 5\n', schema_py) == {'a': 5}

	def test_always_bare_no_func_preserves_null(self):
		'''Verify always bare no func preserves null.'''
		# bare always() (no func) is a no-op, even on null  #todo, this should raise instead
		schema_py = {'a': always()}
		assert taml.loads('a: null\n', schema_py) == {'a': None}

	def test_always_defaulting_null(self):
		'''Verify always defaulting null.'''
		# defaulting use case: supply a value when the field is null
		schema_py = {'level': always(lambda x: x if x is not None else 'info')}
		assert taml.loads('level: null\n', schema_py) == {'level': 'info'}

	def test_always_defaulting_present(self):
		'''Verify always defaulting present.'''
		# defaulting use case: supply a value when the field is null
		schema_py = {'level': always(lambda x: x if x is not None else 'info')}
		assert taml.loads('level: warn\n', schema_py) == {'level': 'warn'}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaAlways).debug()
	print('tests passed')
