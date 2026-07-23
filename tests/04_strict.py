import inspect, traceback, unittest

from parameterized import parameterized
from taml import SchemaDefinitionError, StrictError, required, strict, taml
from utils import assert_equals, assert_raises, assert_raises2


class Parent: ...
class Child(Parent): ...
class Value: ...


value = Value()

def make_child(_value):
	return Child()

def return_value(_value):
	return value


class TestSchemaStrict(unittest.TestCase):
	'Testing the taml.strict object.'

	def test_basic(self) -> None:
		'Basic test with int.'
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: 1',
			{'a': 1},
		)
	def test_preserves_null(self) -> None:
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: null',
			{'a': None},
		)
	def test_allows_missing_key(self) -> None:
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'{}',
			{},
		)
	def test_rejects_wrong_type(self) -> None:
		'Reject a wrong type instead of converting.'
		assert_raises2(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: "1"',
			StrictError,
			"Expected (int), got '1' (line 1, col 4)",
		)
	def test_rejects_bool_as_int(self) -> None:
		'Exact type checking keeps bool separate from int.'
		assert_raises2(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: true',
			StrictError,
		)
	def test_rejects_subclass(self) -> None:
		'Exact type checking rejects an unlisted subclass.'
		assert_raises(
			StrictError,
			lambda: taml.loads('a: value\n', {'a': make_child}, {'a': strict(Parent)}),
		)
	def test_returns_original_object(self) -> None:
		'Strict validates without reconstructing or converting the value.'
		out = taml.loads('a: value\n', {'a': return_value}, {'a': strict(Value)})
		assert out.a is value
	def test_multiple_types_accepts_first(self) -> None:
		assert_equals(
			'a: taml.strict(int, str)',
			{'a': strict(int, str)},
			'a: 1',
			{'a': 1},
		)
	def test_multiple_types_accepts_later_type(self) -> None:
		assert_equals(
			'a: taml.strict(int, str)',
			{'a': strict(int, str)},
			'a: value',
			{'a': 'value'},
		)
	def test_multiple_type_order_does_not_matter(self) -> None:
		'Accepted type order does not change strict behavior or equality.'
		assert_equals(
			'a: taml.strict(int, str)',
			{'a': strict(str, int)},
			'a: value',
			{'a': 'value'},
		)
	def test_duplicate_types_do_not_affect_equality(self) -> None:
		'Duplicate accepted types do not change strict behavior or equality.'
		assert_equals(
			'a: taml.strict(int, int)',
			{'a': strict(int)},
			'a: 1',
			{'a': 1},
		)
	def test_multiple_types_rejects(self) -> None:
		'Test multiple types raises properly.'
		assert_raises2(
			'a: taml.strict(int, float)',
			{'a': strict(int, float)},
			'a: "1"',
			StrictError,
			"Expected (int | float), got '1' (line 1, col 4)",
		)
	@parameterized.expand([
		('callable', 'a: taml.strict(round)'),
		('value', 'a: taml.strict(1)'),
		('mixed', 'a: taml.strict(int, round)'),
	])
	def test_rejects_non_type_arguments_in_taml(self, _name, schema) -> None:
		assert_raises(SchemaDefinitionError, lambda: taml.loads(schema, is_schema=True))
	@parameterized.expand([
		('callable', lambda: strict(round)),
		('value', lambda: strict(1)),
		('mixed', lambda: strict(int, round)),
	])
	def test_rejects_non_type_arguments_natively(self, _name, make) -> None:
		assert_raises(TypeError, make)
	def test_rejects_required_inside_strict(self) -> None:
		'Required belongs outside strict so required is checked before type validation.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict(taml.required(int))', is_schema=True),
		)
		assert_raises(TypeError, lambda: strict(required(int)))
	def test_native_traceback_points_to_definition(self) -> None:
		'A native strict error includes the schema definition site.'
		schema = {'a': strict(int)}; def_line = inspect.currentframe().f_lineno
		try:
			taml.loads("a: 'wrong'\n", schema)
		except StrictError as e:
			frames = traceback.extract_tb(e.__traceback__)
			assert any(fr.name == 'test_native_traceback_points_to_definition' and fr.lineno == def_line for fr in frames), \
				f'traceback missing definition site line {def_line}: {[(fr.filename, fr.lineno, fr.name) for fr in frames]}'
		else:
			raise AssertionError('expected StrictError to be raised')
	def test_missing_func(self) -> None:
		'Strict with no type argument raises definition error.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict', is_schema=True),
			'Missing arguments for strict at a (line 1, col 4)',
		)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict()', is_schema=True),
			'Missing arguments for strict at a (line 1, col 4)',
		)
		assert_raises(
			TypeError,
			strict,
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaStrict).debug()
	print('tests passed')