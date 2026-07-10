import datetime, os
import unittest
from pathlib import Path

from parameterized import parameterized

from epicstuff import s
from taml import taml
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaResolution(unittest.TestCase):
	def test_schema_resolution(self):
		'''Verify schema strings resolve to Python objects when loaded as schemas.'''
		schema = taml.loads('a: int', is_schema=True)
		assert schema['a'] is int

	@parameterized.expand([
		(
			'nonexistent_module',
			'a: some_nonexistent_module.fn',
			"No module named 'some_nonexistent_module' at a (line 1, col 4)",
		),
		(
			'nonexistent_attr',
			'a: os.path.nonexistent_attr',
			"No module named 'os.path.nonexistent_attr'; 'os.path' is not a package at a (line 1, col 4)",
		),
	])
	def test_schema_resolution_errors(self, _label, src, msg):
		'''Verify schema resolution reports missing modules and attributes with source locations.'''
		assert_raises(
			ImportError,
			lambda: taml.loads(src, is_schema=True),
			msg,
		)

	def test_regression_commas_inside_quoted_args(self):
		'''Verify commas inside quoted call arguments are not treated as argument separators.'''
		schema = taml.loads("x: epicstuff.BoxDict(b='1,2')\n", is_schema=True)
		assert taml.loads('x: {a: 1}\n', schema) == {'x': {'a': 1, 'b': '1,2'}}

	def test_builtins_resolution_with_args_kwargs(self):
		'''Verify builtins with keyword arguments resolve and convert data values.'''
		schema = taml.loads(
			s('''
				a: int(base=2)
				b: int(base=16)
			'''),
			is_schema=True,
		)

		assert taml.loads(
			s('''
				a: '101'
				b: 'ff'
			'''),
			schema,
		) == {'a': 5, 'b': 255}

	def test_module_resolution(self):
		'''Verify dotted module callables resolve and convert data values.'''
		schema = taml.loads(
			s('''
				d: datetime.date.fromisoformat
				p: pathlib.Path
			'''),
			is_schema=True,
		)

		out = taml.loads(
			s('''
				d: '2020-01-02'
				p: 'foo/bar'
			'''),
			schema,
		)
		assert out['d'] == datetime.date(2020, 1, 2)
		assert out['p'] == Path('foo/bar')

	def test_nested_call_expressions_inside_args(self):
		'''Verify a call used as a schema argument is evaluated: int(base=len('ab')) parses '11' as base 2.'''
		schema = taml.loads("a: int(base=len('ab'))\n", is_schema=True)
		assert taml.loads("a: '11'\n", schema) == {'a': 3}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaResolution).debug()
	print('tests passed')
