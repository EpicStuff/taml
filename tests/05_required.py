import inspect, traceback, unittest

from epicstuff import s
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, RequiredError, StrictError, required, strict, taml
from utils import assert_equals, assert_raises, assert_raises2, raise_runtime_error


def assert_required_path(data: str, schema, path: str) -> None:
	try:
		taml.loads(data, schema)
	except RequiredError as e:
		message = str(e)
		assert message.startswith(f'{path} is required '), message
		assert '(line 1, col ' in message, message
	else:
		raise AssertionError('expected RequiredError to be raised')


class Main(unittest.TestCase):
	'Testing the taml.required object.'

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
	@parameterized.expand([
		('zero', 'a: 0', {'a': 0}),
		('false', 'a: false', {'a': False}),
		('empty_string', "a: ''", {'a': ''}),
		('empty_list', 'a: []', {'a': []}),
		('empty_dict', 'a: {}', {'a': {}}),
	])
	def test_present_falsy_values(self, _name, data, expected) -> None:
		'Required rejects only missing values and null.'
		assert_equals('a: taml.required', {'a': required(None, 'a')}, data, expected)

	@parameterized.expand([
		('no_arg_and_no_key', 'a: taml.required', {'a': required(None, 'a')}, '{}', 'a is required (line 1, col 1)'),
		('no_arg_and_key', 'a: taml.required', {'a': required(None, 'a')}, 'a: null', 'a is required (line 1, col 4)'),
		('arg_and_no_key', 'a: taml.required(int)', {'a': required(int, 'a')}, '{}', 'a is required (line 1, col 1)'),
		('arg_and_key', 'a: taml.required(int)', {'a': required(int, 'a')}, 'a: null', 'a is required (line 1, col 4)'),
	])
	def test_raise(self, _name, schema, native, data, msg) -> None:
		'Required errors with the right path and position on a missing key or null.'
		assert_raises2(schema, native, data, RequiredError, msg)
	def test_empty_document_still_checks_required(self) -> None:
		'An empty document is missing every required root key.'
		parsed = taml.loads('a: taml.required(int)\n', is_schema=True)
		native = {'a': required(int, 'a')}
		assert_required_path('', parsed, 'a')
		assert_required_path('', native, 'a')
	@parameterized.expand([
		('missing_parent', '{}'),
		('null_parent', 'd: null'),
		('empty_parent', 'd: {}'),
	])
	def test_nested_required_under_parent_states(self, _name, data) -> None:
		'Nested required keys fail whether their parent is absent, null, or empty.'
		parsed = taml.loads('d: {b: taml.required}\n', is_schema=True)
		native = {'d': {'b': required(None, 'd.b')}}
		assert_required_path(data, parsed, 'd.b')
		assert_required_path(data, native, 'd.b')
	@parameterized.expand([
		('missing_parent', '{}'),
		('null_parent', 'items: null'),
		('empty_parent', 'items: []'),
	])
	def test_required_list_item_under_parent_states(self, _name, data) -> None:
		'A required list item fails when its parent is absent, null, or too short.'
		parsed = taml.loads('items: [int, taml.required]\n', is_schema=True)
		native = {'items': [int, required(None, 'items[1]')]}
		assert_required_path(data, parsed, 'items[1]')
		assert_required_path(data, native, 'items[1]')
	def test_reused_required_uses_actual_path(self) -> None:
		'A shared native required object reports the location where it is applied.'
		item = required(int)
		schema = {'a': item, 'b': item}
		assert_required_path("a: '1'\n", schema, 'b')
	def test_yaml_alias_uses_actual_path(self) -> None:
		'A shared parsed required alias reports the location where it is applied.'
		schema = taml.loads('a: &rule taml.required(int)\nb: *rule\n', is_schema=True)
		assert_required_path("a: '1'\n", schema, 'b')
	def test_conversion_type_error(self) -> None:
		assert_raises2(
			'a: taml.required(int)',
			{'a': required(int, 'a')},
			'a: []',
			ConversionTypeError,
			'Cannot convert [] to int (line 1, col 4)',
		)
	def test_conversion_value_error(self) -> None:
		assert_raises2(
			'a: taml.required(int)',
			{'a': required(int, 'a')},
			"a: 'nope'",
			ConversionValueError,
			"Cannot convert 'nope' to int (line 1, col 4)",
		)
	def test_unrelated_error_propagates(self) -> None:
		assert_raises(
			RuntimeError,
			lambda: taml.loads('a: value\n', {'a': required(raise_runtime_error, 'a')}),
			'runtime failure',
		)
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
	def test_nested_strict_order_does_not_affect_equality(self) -> None:
		'Required inherits semantic strict equality recursively.'
		assert_equals(
			'a: taml.required(taml.strict(int, str))',
			{'a': required(strict(str, int), 'a')},
			'a: value',
			{'a': 'value'},
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