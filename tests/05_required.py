import inspect, traceback, unittest

from epicstuff import s
from parameterized import parameterized
from taml import RequiredError, StrictError, required, strict, taml
from utils import assert_equals, assert_raises2


class Main(unittest.TestCase):
	'Testing the taml.required object.'

	# test required working properly
	def test_no_arg(self) -> None:
		'Bare required does nothing when value.'
		assert_equals(
			'a: taml.required',
			{'a': required(None, 'a')},
			"a: 'present'",
			{'a': 'present'},
		)
		assert_equals(
			'a: taml.required()',
			{'a': required(None, 'a')},
			"a: 'present'",
			{'a': 'present'},
		)
	def test_arg(self) -> None:
		'Required with func converts.'
		assert_equals(
			'a: taml.required(int)',
			{'a': required(int, 'a')},
			'a: "1"',
			{'a': 1},
		)

	# test required raises proper errors
	@parameterized.expand([
		('no_arg_and_no_key', 'a: taml.required', {'a': required(None, 'a')}, '{}', 'a is required (line 1, col 1)'),
		('no_arg_and_key', 'a: taml.required', {'a': required(None, 'a')}, 'a: null', 'a is required (line 1, col 4)'),
		('arg_and_no_key', 'a: taml.required(int)', {'a': required(int, 'a')}, '{}', 'a is required (line 1, col 1)'),
		('arg_and_key', 'a: taml.required(int)', {'a': required(int, 'a')}, 'a: null', 'a is required (line 1, col 4)'),
	])
	def test_raise(self, _name, schema, native, data, msg) -> None:
		'Required errors with the right path and position on a missing key or null.'
		assert_raises2(schema, native, data, RequiredError, msg)
	def test_native_traceback_points_to_definition(self) -> None:
		'A natively built required attaches a traceback pointing at its definition site.'
		schema = {'a': required(int)}; def_line = inspect.currentframe().f_lineno
		try:
			taml.loads('a: null\n', schema)
		except RequiredError as e:
			frames = traceback.extract_tb(e.__traceback__)
			assert any(fr.name == 'test_native_traceback_points_to_definition' and fr.lineno == def_line for fr in frames), \
				f'traceback missing definition site line {def_line}: {[(fr.filename, fr.lineno, fr.name) for fr in frames]}'
		else:
			raise AssertionError('expected RequiredError to be raised')

	# stuff
	def test_nested_required_dict_key(self) -> None:
		'A required key nested in a dict reports its dotted path.'
		assert_raises2(
			s('''
				d:
					a: int
					b: taml.required
			'''),
			{'d': {'a': int, 'b': required(None, 'd.b')}},
			"d: {a: '1'}",
			RequiredError,
			'd.b is required (line 1, col 1)',
		)
	def test_required_list_index(self) -> None:
		'A required item at a list index reports its indexed path.'
		assert_raises2(
			s('''
				lst:
					- int
					- taml.required
			'''),
			{'lst': [int, required(None, 'lst[1]')]},
			"lst: ['1']",
			RequiredError,
			'lst[1] is required (line 1, col 1)',
		)


class Strict(unittest.TestCase):
	'Making sure required works with strict.'

	def test_strict(self) -> None:
		'Required with strict returns a matching value unchanged.'
		assert_equals(
			'a: taml.required(taml.strict(int))',
			{'a': required(strict(int), 'a')},
			'a: 1',
			{'a': 1},
		)
	def test_wrapping_strict_rejects_wrong_type(self) -> None:
		'Required with strict still enforces the strict type check.'
		assert_raises2(
			'a: taml.required(taml.strict(int))',
			{'a': required(strict(int), 'a')},
			'a: "1"',
			StrictError,
			"Expected (int), got '1' (line 1, col 4)",
		)
	def test_wrapping_strict_missing_key(self) -> None:
		'Required with strict still errors on a missing key.'
		assert_raises2(
			'a: taml.required(taml.strict(int))',
			{'a': required(strict(int), 'a')},
			'{}',
			RequiredError,
			'a is required (line 1, col 1)',
		)
	def test_wrapping_strict_null(self) -> None:
		'Required with strict still errors on null.'
		assert_raises2(
			'a: taml.required(taml.strict(int))',
			{'a': required(strict(int), 'a')},
			'a: null',
			RequiredError,
			'a is required (line 1, col 4)',
		)

if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	unittest.TestLoader().loadTestsFromTestCase(Strict).debug()
	print('tests passed')
