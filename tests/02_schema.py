import unittest

from epicstuff import s, wrap, open  # noqa: A004
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, StructureError, taml
from utils import test_taml_path, test_schame_path, assert_equals, assert_raises2


class Main(unittest.TestCase):
	'Super basic schema tests.'

	def test_builtin(self) -> None:
		'Simple builtin test.'
		assert taml.loads('a: "1"\n', {'a': int}) == {'a': 1}
		assert taml.loads('a: {b: "5"}\n', {'a': {'b': int}}) == {'a': {'b': 5}}
	@parameterized.expand([
		('path', lambda path: path),
		('str', str),
		('open', None),
	])
	def test_load_schema_sources(self, name, schema_source) -> None:
		'Verify load accepts path and stream schema sources.'
		if name == 'open':
			with open(test_schame_path) as file:
				out = taml.load(test_taml_path, file)
		else:
			out = taml.load(test_taml_path, schema_source(test_schame_path))
		assert out.a.a == '3'
	def test_loads_is_schema(self) -> None:
		'Verify is_schema resolves schema strings before they are applied.'
		schema = taml.loads('a: int\n', is_schema=True)
		assert schema.a is int
		assert taml.loads("a: '1'\n", schema) == {'a': 1}
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
			'Expected dict or None, got CommentedSeq: [1] (line 1, col 4)',
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
			{'lst': [1, 2]},  # does not append missing indices
		)
	def test_null_list_preserved(self) -> None:
		'Verify null and empty lists under a list schema are preserved.'
		assert_equals('lst: [int]\n', {'lst': [int]}, 'lst:\n', {'lst': None})
		assert_equals('lst: [int]\n', {'lst': [int]}, 'lst: []\n', {'lst': []})
	def test_type_mismatch_dict(self) -> None:
		'Verify a list schema rejects dict data.'
		assert_raises2('x: [int]\n', {'x': [int]}, 'x: {a: 1}\n', StructureError, "Expected list or None, got dotCommentedMap: {'a': 1} (line 1, col 4)")
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
	'Tests merging of multiple schemas.'

	def test_multiple(self) -> None:
		'Verify multiple schema arguments deep-merge — three schemas each contribute a conversion to the same path.'
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
	def test_disjoint_schemas(self) -> None:
		'Verify disjoint schemas each convert their matching data key.'
		assert taml.loads("a: '1'\nb: '2'\n", {'a': int}, {'b': int}) == {'a': 1, 'b': 2}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	unittest.TestLoader().loadTestsFromTestCase(Dicts).debug()
	unittest.TestLoader().loadTestsFromTestCase(Lists).debug()
	unittest.TestLoader().loadTestsFromTestCase(Multiple).debug()
	print('tests passed')
