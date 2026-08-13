# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001

import inspect, traceback, unittest, itertools

from epicstuff import run_fix_import  # noqa: F401
from parameterized import parameterized
from taml import SchemaDefinitionError, StrictError, required, strict, taml

from .utils import assert_equals, assert_raises, assert_raises2


class Parent: ...
class Child(Parent):
	def __repr__(self) -> str:
		return 'Child()'
class Value: ...
value = Value()

def make_child(_value) -> Child:
	return Child()
def return_value(_value) -> Value:
	return value


class Main(unittest.TestCase):
	def test_basic1(self) -> None:
		'Correct type does nothing.'
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: 1',
			{'a': 1},
		)
	def test_basic2(self) -> None:
		'Wrong type raises.'
		assert_raises2(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: "1"',
			StrictError,
			"Expected int, got '1' (line 1, col 4)",
		)
	def test_rejects_null(self) -> None:
		'Make sure null is rejected.'
		assert_raises2(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: null',
			StrictError,
			'Expected int, got None (line 1, col 4)',
		)
	def test_allows_missing(self) -> None:
		'Make sure missing key is allowed.'
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'{}',
			{},
		)
	def test_rejects_subclass(self) -> None:
		'e.g. bool under int, Child under Parent.'
		assert_raises(
			StrictError,
			lambda: taml.loads('a: value\n', {'a': make_child}, {'a': strict(Parent)}),
			'Expected Parent, got Child() (line 1, col 4)',
		)
	def test_root(self) -> None:
		'Works as root.'
		assert taml.loads('taml.strict(int)', is_schema=True) == strict(int)
	def test_returns_original_object(self) -> None:
		'Validates without reconstructing or converting.'
		out = taml.loads('a: value\n', {'a': return_value}, {'a': strict(Value)})
		assert out.a is value
	@parameterized.expand(itertools.product((('a: 1', 1), ('a: value', 'value')), (('a: taml.strict(int, str)', strict(int, str)), ('a: taml.strict(int, str)', strict(str, int)))))
	def test_multiple(self, data, schema) -> None:
		assert_equals(
			schema[0],
			{'a': schema[1]},
			data[0],
			{'a': data[1]},
		)
	def test_duplicate_types_do_not_affect_equality(self) -> None:
		'Duplicate accepted types do not change strict behavior or equality.'
		a = taml.loads('taml.strict(int)', is_schema=True)
		b = taml.loads('taml.strict(int, int)', is_schema=True)
		c = strict(int)
		d = strict(int, int)
		self.assertEqual(a, b)
		self.assertEqual(b, c)
		self.assertEqual(c, d)

	def test_different_strict_types_are_not_equal(self) -> None:
		assert strict(int) != strict(str)
	def test_multiple_types_rejects(self) -> None:
		'Test multiple types raises properly.'
		assert_raises2(
			'a: taml.strict(int, float)',
			{'a': strict(int, float)},
			'a: "1"',
			StrictError,
			"Expected int | float, got '1' (line 1, col 4)",
		)
	@parameterized.expand([
		('callable', 'a: taml.strict(round)', 'round at a is not a type (line 1, col 16)'),
		('value', 'a: taml.strict(1)', '1 at a is not a type (line 1, col 16)'),
		('mixed', 'a: taml.strict(int, round)', 'round at a is not a type (line 1, col 21)'),
		('required', 'a: taml.strict(taml.required(int))', 'required at a is not a type (line 1, col 16)'),
	])
	def test_non_type_raises(self, _name, schema, msg) -> None:
		assert_raises(SchemaDefinitionError, lambda: taml.loads(schema, is_schema=True), msg)
	@parameterized.expand([
		('callable', lambda: strict(round)),  # pyright: ignore[reportArgumentType]
		('value', lambda: strict(1)),  # pyright: ignore[reportArgumentType]
		('mixed', lambda: strict(int, round)),  # pyright: ignore[reportArgumentType]
		('required', lambda: strict(required(int))),  # pyright: ignore[reportArgumentType]
	])
	def test_native_non_type_raises(self, _name, func) -> None:
		assert_raises(TypeError, func)
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
	def test_missing_arg(self) -> None:
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
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
