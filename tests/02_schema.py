import contextlib, unittest
from io import StringIO
from itertools import product

from epicstuff import s, wrap
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, StrictError, StructureError, always, repeat, required, strict, taml
from utils import assert_equals, assert_raises, assert_raises2, create_file, raise_runtime_error


DATA_SOURCES = ('string', 'stringio', 'str_path', 'path', 'open')
SCHEMA_SOURCES = ('parsed', 'stringio', 'str_path', 'path', 'open')


def load_with_schema_sources(data: str, data_source: str, schema: str, schema_source: str):
	with contextlib.ExitStack() as stack:
		data_path = stack.enter_context(create_file(data, 'data.taml'))
		schema_path = stack.enter_context(create_file(schema, 'schema.taml'))

		if schema_source == 'parsed':
			schema_value = taml.loads(schema, is_schema=True)
		elif schema_source == 'stringio':
			schema_value = StringIO(schema)
		elif schema_source == 'str_path':
			schema_value = str(schema_path)
		elif schema_source == 'path':
			schema_value = schema_path
		else:
			schema_value = stack.enter_context(schema_path.open())

		if data_source == 'string':
			out = taml.loads(data, schema_value)
		elif data_source == 'stringio':
			data_value = StringIO(data)
			out = taml.load(data_value, schema_value)
			assert not data_value.closed
		elif data_source == 'str_path':
			out = taml.load(str(data_path), schema_value)
		elif data_source == 'path':
			out = taml.load(data_path, schema_value)
		else:
			data_value = stack.enter_context(data_path.open())
			out = taml.load(data_value, schema_value)
			assert not data_value.closed

		if isinstance(schema_value, StringIO):
			assert not schema_value.closed
		elif schema_source == 'open':
			assert not schema_value.closed
		return out


class Main(unittest.TestCase):
	'Super basic schema tests.'

	def test_builtin(self) -> None:
		'Simple builtin test.'
		assert taml.loads('a: "1"\n', {'a': int}) == {'a': 1}
		assert taml.loads('a: {b: "5"}\n', {'a': {'b': int}}) == {'a': {'b': 5}}
	@parameterized.expand(product(DATA_SOURCES, SCHEMA_SOURCES))
	def test_load_schema_sources(self, data_source, schema_source) -> None:
		'Every supported data and schema source combination loads consistently.'
		data = s('''
			a:
				a: 3
				b: 956579776
				c:
					- 1
					- 2
					- 3
				d:
					- 1.12345
					- 2
					- {'a': 1}
					- 4
		''')
		schema = s('''
			a:
				a: str
		''')
		expected = {'a': {'a': '3', 'b': 956579776, 'c': [1, 2, 3], 'd': [1.12345, 2, {'a': 1}, 4]}}
		assert load_with_schema_sources(data, data_source, schema, schema_source) == expected
	def test_loads_is_schema(self) -> None:
		'Verify is_schema resolves schema strings before they are applied.'
		schema = taml.loads('a: int\n', is_schema=True)
		assert schema.a is int
		assert taml.loads("a: '1'\n", schema) == {'a': 1}
	def test_root_scalar_schema(self) -> None:
		assert_equals('int\n', int, "'1'\n", 1)
	def test_root_list_schema(self) -> None:
		assert_equals('[int, str]\n', [int, str], "['1', 'two']\n", [1, 'two'])
	def test_root_structure_mismatch(self) -> None:
		assert_raises(StructureError, lambda: taml.loads('{}\n', [int]))
		assert_raises(StructureError, lambda: taml.loads('[]\n', {'a': int}))
	def test_plain_callable_allows_missing_key(self) -> None:
		'A plain callable does not insert a missing key.'
		assert_equals('a: str', {'a': str}, '{}', {})
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
		assert_raises(RuntimeError, lambda: taml.loads('a: value\n', {'a': raise_runtime_error}), 'runtime failure')
	def test_schema_reuse(self) -> None:
		schema = taml.loads('a: int\n', is_schema=True)
		assert taml.loads("a: '1'\n", schema) == {'a': 1}
		assert taml.loads("a: '2'\n", schema) == {'a': 2}
	def test_schema_reuse_after_failure(self) -> None:
		schema = taml.loads('a: int\n', is_schema=True)
		assert_raises(ConversionValueError, lambda: taml.loads("a: 'nope'\n", schema))
		assert taml.loads("a: '3'\n", schema) == {'a': 3}
	def test_empty_schema(self) -> None:
		assert taml.loads('a: 1\n', {}) == {'a': 1}
	def test_empty_document_preserved_under_schema(self) -> None:
		'An empty document remains None when no required value demands traversal.'
		assert_equals('a: int\n', {'a': int}, '', None)


class Equality(unittest.TestCase):
	'Test semantic schema equality.'

	def test_required_path_does_not_affect_equality(self) -> None:
		assert required(int, 'a') == required(int, 'b')
	def test_different_strict_types_are_not_equal(self) -> None:
		assert strict(int) != strict(str)
	def test_different_schema_classes_are_not_equal(self) -> None:
		assert always(int) != required(int)
	def test_repeat_coerce_affects_equality(self) -> None:
		assert repeat(int, coerce=True) != repeat(int, coerce=False)


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
			"d: {a: '1', b: '2'}\n",
			{'d': {'a': 1, 'b': 2}},
		)
	def test_extra_keys_unconverted(self) -> None:
		'Verify data keys absent from the schema are left unconverted.'
		assert_equals('d: {a: int}\n', {'d': {'a': int}}, "d: {a: '1', b: '2'}\n", {'d': {'a': 1, 'b': '2'}})
	def test_null_scalar_preserved(self) -> None:
		'Make sure a null under a scalar schema is preserved, not converted.'
		assert_equals('a: int', {'a': int}, 'a: null', {'a': None})
	def test_null_dict_preserved(self) -> None:
		'Make sure null, empty-dict, and null children under a nested schema are preserved.'
		schema = s('''
			a:
				b: int
		''')
		assert_equals(schema, {'a': {'b': int}}, 'a:\n', {'a': None})
		assert_equals(schema, {'a': {'b': int}}, 'a: {}\n', {'a': {}})
		assert_equals(schema, {'a': {'b': int}}, 'a: {b: null}\n', {'a': {'b': None}})
		assert_equals(schema, {'a': {'b': int}}, 'a:\n\tb:\n', {'a': {'b': None}})
	def test_type_mismatch_list(self) -> None:
		'Verify a dict schema rejects list data.'
		assert_raises2(
			s('''
				x:
					a: int
			'''),
			{'x': {'a': int}},
			'x: [1]\n',
			StructureError,
			'Expected dict or None, got list: [1] (line 1, col 4)',
		)
	def test_type_mismatch_object(self) -> None:
		'Verify a dict schema rejects scalar.'
		assert_raises2(
			s('''
				x:
					a: int
			'''),
			{'x': {'a': int}},
			'x: 1\n',
			StructureError,
			'Expected dict or None, got int: 1 (line 1, col 4)',
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
			"lst: ['1', '2']\n",
			{'lst': [1, 2]},
		)
	def test_null_list_preserved(self) -> None:
		'Verify null and empty lists under a list schema are preserved.'
		assert_equals('lst: [int]\n', {'lst': [int]}, 'lst:\n', {'lst': None})
		assert_equals('lst: [int]\n', {'lst': [int]}, 'lst: []\n', {'lst': []})
	def test_type_mismatch_dict(self) -> None:
		'Verify a list schema rejects dict data.'
		assert_raises2('x: [int]\n', {'x': [int]}, 'x: {a: 1}\n', StructureError, "Expected list or None, got dict: {'a': 1} (line 1, col 4)")
	def test_type_mismatch_object(self) -> None:
		'Verify a list schema rejects scalar data.'
		assert_raises2('x: [int]\n', {'x': [int]}, 'x: 1\n', StructureError, 'Expected list or None, got int: 1 (line 1, col 4)')
	def test_extra_items_unconverted(self) -> None:
		'Verify data items beyond the schema length are left unconverted.'
		assert_equals('lst: [int]\n', {'lst': [int]}, "lst: ['1', '2']\n", {'lst': [1, '2']})
	def test_tuple_schema(self) -> None:
		'Verify native tuple schemas convert list data.'
		assert_equals('values: [int, str]', {'values': (int, str)}, "values: ['1', 'two']", {'values': [1, 'two']})


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
		data = 'a: [1, 2]\n'
		assert taml.loads(data, {'a': str}, {'a': len}) == {'a': 6}
		assert taml.loads(data, {'a': len}, {'a': str}) == {'a': '2'}
	def test_structural_handoff_between_schemas(self) -> None:
		'A later schema traverses a structure created by an earlier conversion.'
		decode = taml.loads('payload: json.loads\n', is_schema=True)
		convert = taml.loads('payload: {a: int}\n', is_schema=True)
		assert taml.loads("payload: '{\"a\": \"1\"}'\n", decode, convert) == {'payload': {'a': 1}}
	def test_later_schema_failure_uses_original_location(self) -> None:
		assert_raises(
			StrictError,
			lambda: taml.loads("a: '1'\n", {'a': int}, {'a': strict(str)}),
			'Expected (str), got 1 (line 1, col 4)',
		)
	def test_disjoint_schemas(self) -> None:
		'Verify disjoint schemas each convert their matching data key.'
		assert taml.loads("a: '1'\nb: '2'\n", {'a': int}, {'b': int}) == {'a': 1, 'b': 2}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	unittest.TestLoader().loadTestsFromTestCase(Equality).debug()
	unittest.TestLoader().loadTestsFromTestCase(Dicts).debug()
	unittest.TestLoader().loadTestsFromTestCase(Lists).debug()
	unittest.TestLoader().loadTestsFromTestCase(Multiple).debug()
	print('tests passed')
