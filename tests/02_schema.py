# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001

import unittest
from io import StringIO

from epicstuff import open, run_fix_import, s, wrap  # noqa: A004
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, StrictError, StructureError, always, repeat, required, strict, taml

from .utils import assert_equals, assert_raises, assert_raises2, create_file, raise_runtime_error, skip


class Main(unittest.TestCase):
	'Super basic schema tests.'

	def test_builtin(self) -> None:
		'Simple builtin test.'
		assert taml.loads('a: "1"', {'a': int}) == {'a': 1}
		assert taml.loads('a: {b: "5"}', {'a': {'b': int}}) == {'a': {'b': 5}}
	@parameterized.expand((
		('seperate', lambda _: taml.loads('a: str', is_schema=True)),
		('native', lambda _: {'a': str}),
		('stringio', lambda _: StringIO('a: str')),
		('str_path', str),
		('path', lambda path: path),
		('open', open),
	))
	def test_load_schema_sources(self, name, source) -> None:
		'Every supported schema source combination loads consistently.'
		with create_file('a: str', 'schema.taml') as file:
			source = source(file)
			out = taml.loads('a: 3', source)
			if name == 'open':
				assert not source.closed, 'taml.load should not be closing not it opened sources'
				source.close()
			elif isinstance(source, StringIO):
				assert not source.closed, 'taml.load should not be closing not it opened sources'

		assert out == {'a': '3'}

	@parameterized.expand([
		('scalar', 'int', int, "'1'", 1),
		('list', '[int, str]', [int, str], "['1', 'two']", [1, 'two']),
	])
	def test_root_schema(self, _name, schema, native, data, expected) -> None:
		assert_equals(schema, native, data, expected)
	@parameterized.expand([
		('list_schema_dict_data', '{}', [int], 'Expected list or None, got {} (line 1, col 1)'),
		('dict_schema_list_data', '[]', {'a': int}, 'Expected dict or None, got [] (line 1, col 1)'),
	])
	def test_root_structure_mismatch(self, _name, data, schema, msg) -> None:
		assert_raises(StructureError, lambda: taml.loads(data, schema), msg)

	def test_plain_callable_rejects_wrong_type(self) -> None:
		'A plain callable surfaces conversion type errors.'
		assert_raises2(
			'a: int',
			{'a': int},
			'a: []',
			ConversionTypeError,
			'Cannot convert [] to int (line 1, col 4)',
		)
	def test_plain_callable_rejects_bad_value(self) -> None:
		'A plain callable surfaces conversion value errors.'
		assert_raises2(
			'a: int',
			{'a': int},
			"a: 'nope'",
			ConversionValueError,
			"Cannot convert 'nope' to int (line 1, col 4)",
		)
	def test_plain_callable_propagates_unrelated_error(self) -> None:
		assert_raises(RuntimeError, lambda: taml.loads('a: value', {'a': raise_runtime_error}), 'runtime failure')
	def test_schema_reuse(self) -> None:
		schema = taml.loads('a: int', is_schema=True)

		assert taml.loads("a: '1'", schema) == {'a': 1}
		assert_raises(ConversionValueError, lambda: taml.loads("a: 'nope'", schema))
		assert taml.loads("a: '2'", schema) == {'a': 2}
	def test_empty_schema(self) -> None:
		assert taml.loads('a: 1', {}) == {'a': 1}
	def test_empty_document_preserved_under_schema(self) -> None:
		'An empty document remains None when no required value demands traversal.'
		assert_equals('a: int', {'a': int}, '', None)

class Dicts(unittest.TestCase):
	'Test dictionary structure.'

	def test_missing_keys(self) -> None:
		'Make sure missing keys are not inserted nor cause errors.'
		assert_equals(
			s('''
				d:
					a: int
					b: int
					c: str
			'''),
			{'d': {'a': int, 'b': int, 'c': str}},
			"d: {a: '1', b: '2'}",
			{'d': {'a': 1, 'b': 2}},
		)
	def test_extra_keys_unconverted(self) -> None:
		'Verify data keys absent from the schema are left unconverted.'
		assert_equals('d: {a: int}', {'d': {'a': int}}, "d: {a: '1', b: '2'}", {'d': {'a': 1, 'b': '2'}})
	def test_null_scalar_preserved(self) -> None:
		'Make sure a null under a scalar schema is preserved, not converted.'
		assert_equals('a: int', {'a': int}, 'a: null', {'a': None})
	def test_null_dict_preserved(self) -> None:
		'Make sure null, empty-dict, and null children under a nested schema are preserved.'
		schema = s('''
			a:
				b: int
		''')
		assert_equals(schema, {'a': {'b': int}}, 'a:', {'a': None})
		assert_equals(schema, {'a': {'b': int}}, 'a: {}', {'a': {}})
		assert_equals(schema, {'a': {'b': int}}, 'a: {b: null}', {'a': {'b': None}})
		assert_equals(schema, {'a': {'b': int}}, 'a:\n\tb:', {'a': {'b': None}})
	def test_type_mismatch_list(self) -> None:
		'Verify a dict schema rejects list data.'
		assert_raises2(
			s('''
				x:
					a: int
			'''),
			{'x': {'a': int}},
			'x: [1]',
			StructureError,
			'Expected dict or None, got [1] (line 1, col 4)',
		)
	def test_type_mismatch_object(self) -> None:
		'Verify a dict schema rejects scalar.'
		assert_raises2(
			s('''
				x:
					a: int
			'''),
			{'x': {'a': int}},
			'x: 1',
			StructureError,
			'Expected dict or None, got 1 (line 1, col 4)',
		)
class Lists(unittest.TestCase):
	'Test list structure.'

	def test_list_does_not_append_missing_indices(self) -> None:
		'Make sure items are not appened nor cause errors.'
		assert_equals(
			s('''
				lst:
					- int
					- int
					- str
			'''),
			{'lst': [int, int, str]},
			"lst: ['1', '2']",
			{'lst': [1, 2]},  # does not append missing indices
		)
	def test_null_list_preserved(self) -> None:
		'Verify null and empty lists under a list schema are preserved.'
		assert_equals('lst: [int]', {'lst': [int]}, 'lst:', {'lst': None})
		assert_equals('lst: [int]', {'lst': [int]}, 'lst: []', {'lst': []})
	def test_type_mismatch_dict(self) -> None:
		'Verify a list schema rejects dict data.'
		assert_raises2('x: [int]', {'x': [int]}, 'x: {a: 1}', StructureError, "Expected list or None, got {'a': 1} (line 1, col 4)")
	def test_type_mismatch_object(self) -> None:
		'Verify a list schema rejects scalar data.'
		assert_raises2('x: [int]', {'x': [int]}, 'x: 1', StructureError, 'Expected list or None, got 1 (line 1, col 4)')
	def test_extra_items_unconverted(self) -> None:
		'Verify data items beyond the schema length are left unconverted.'
		assert_equals('lst: [int]', {'lst': [int]}, "lst: ['1', '2']", {'lst': [1, '2']})
	def test_tuple_schema(self) -> None:
		'Verify native tuple schemas convert list data.'
		self.assertEqual(taml.loads("values: ['1', 'two']", {'values': (int, str)}), {'values': [1, 'two']})
class Multiple(unittest.TestCase):
	'Tests ordered application of multiple schemas.'

	def test_multiple_schemas_apply_left_to_right(self) -> None:
		'Three schemas each contribute a conversion to the same path in argument order.'
		schema1 = taml.loads(
			s('''
				cfg:
					a: float
			'''),
			is_schema=True,
		)
		schema2 = {
			'cfg': {
				'a': wrap(round, ndigits=2),
				'b': int,
			},
		}
		schema3 = taml.loads(
			s('''
				cfg:
					a: str
					c: int
			'''),
			is_schema=True,
		)

		out = taml.loads(s('''
			cfg:
				a: '1.23456789'
				b: '2'
				c: '3'
		'''), schema1, schema2, schema3)
		assert out == {'cfg': {'a': '1.23', 'b': 2, 'c': 3}}
	def test_multiple_schema_order_changes_result(self) -> None:
		data = 'a: [1, 2]'
		assert taml.loads(data, {'a': str}, {'a': len}) == {'a': 6}
		assert taml.loads(data, {'a': len}, {'a': str}) == {'a': '2'}
	def test_structural_handoff_between_schemas(self) -> None:
		'A later schema traverses a structure created by an earlier conversion.'
		decode = taml.loads('payload: json.loads', is_schema=True)
		convert = taml.loads('payload: {a: int}', is_schema=True)
		assert taml.loads("payload: '{\"a\": \"1\"}'", decode, convert) == {'payload': {'a': 1}}
	def test_later_schema_failure_uses_original_location(self) -> None:
		assert_raises(
			StrictError,
			lambda: taml.loads("a: '1'", {'a': int}, {'a': strict(str)}),
			'Expected str, got 1 (line 1, col 4)',
		)
	def test_disjoint_schemas(self) -> None:
		'Verify disjoint schemas each convert their matching data key.'
		assert taml.loads("a: '1'\nb: '2'", {'a': int}, {'b': int}) == {'a': 1, 'b': 2}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	unittest.TestLoader().loadTestsFromTestCase(Dicts).debug()
	unittest.TestLoader().loadTestsFromTestCase(Lists).debug()
	unittest.TestLoader().loadTestsFromTestCase(Multiple).debug()
	print('tests passed')
