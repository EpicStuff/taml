# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001

import inspect, traceback, unittest
from itertools import product

from epicstuff import run_fix_import, s  # noqa: F401
from parameterized import parameterized
from taml import ConversionValueError, RequiredError, StructureError, repeat, required, taml

from .utils import assert_equals, assert_raises2, raise_runtime_error


class Dicts(unittest.TestCase):
	'Test taml.repeat used for dictionary entries.'

	def test_basic(self) -> None:
		'Every matching dictionary entry is converted with the repeated schema.'
		assert_equals(
			s('''
				a:
					taml.repeat():
						b: int
			'''),
			{'a': {repeat(): {'b': int}}},
			s('''
				a:
					b:
						a: '1'
						b: 1
					c:
						a: '2'
						b: '2'
			'''),
			{
				'a': {
					'b': {'a': '1', 'b': 1},
					'c': {'a': '2', 'b': 2},
				},
			},
		)
	def test_static_key_alongside_repeat(self) -> None:
		'A static key takes precedence while repeat covers the other entries.'
		assert_equals(
			s('''
				cfg:
					one:
					taml.repeat():
						value: int
			'''),
			{'cfg': {'one': None, repeat(): {'value': int}}},
			s('''
				cfg:
					one:
						value: '1'
					two:
						value: '2'
					three:
						value: '3'
			'''),
			{
				'cfg': {
					'one': {'value': '1'},
					'two': {'value': 2},
					'three': {'value': 3},
				},
			},
		)
	def test_bare_equals(self) -> None:
		'Bare repeat is the same as with brackets.'
		assert taml.loads('repeat:\n a: int', is_schema=True) == taml.loads('repeat():\n a: int', is_schema=True) == {repeat(): {'a': int}}

	@parameterized.expand([
		('default_null', 'taml.repeat()', repeat(), 'a:', {'a': {}}),
		('default_empty', 'taml.repeat()', repeat(), 'a: {}', {'a': {}}),
		('false_null', 'taml.repeat(coerce=False)', repeat(coerce=False), 'a:', {'a': None}),
	])
	def test_key_coerce(self, _name, marker, native_marker, data, expected) -> None:
		'Coerce controls whether null repeated dictionaries become empty dictionaries.'
		assert_equals(
			s(f'''
				a:
					{marker}:
						value: int
			'''),
			{'a': {native_marker: {'value': int}}},
			data,
			expected,
		)

	def test_missing_repeat_parent_is_not_inserted(self) -> None:
		'A missing parent does not create an empty repeated dictionary.'
		assert_equals(
			s('''
				cfg:
					taml.repeat():
						port: int
			'''),
			{'cfg': {repeat(): {'port': int}}},
			'{}',
			{},
		)

	@parameterized.expand([
		('list', 'cfg: []', 'Expected dict or None, got [] (line 1, col 6)'),
		('scalar', 'cfg: 1', 'Expected dict or None, got 1 (line 1, col 6)'),
	])
	def test_repeat_dictionary_rejects_wrong_structure(self, _name, data, msg) -> None:
		assert_raises2(
			s('''
				cfg:
					taml.repeat():
						port: int
			'''),
			{'cfg': {repeat(): {'port': int}}},
			data,
			StructureError,
			msg,
		)

class Lists(unittest.TestCase):
	'Test taml.repeat used for lists.'

	def test_basic(self) -> None:
		'A repeated list schema converts every item regardless of length.'
		assert_equals(
			'items: taml.repeat(int)',
			{'items': repeat(int)},
			"items: ['1', '2', 3, '4']",
			{'items': [1, 2, 3, 4]},
		)
	def test_empty(self) -> None:
		'A repeated list schema accepts an empty list.'
		assert_equals(
			'items: taml.repeat(int)',
			{'items': repeat(int)},
			'items: []',
			{'items': []},
		)

	@parameterized.expand(product(
		['items: taml.repeat()', 'items: taml.repeat'],
		[('items:', {'items': []}), ("items: [1, 'a', null]", {'items': [1, 'a', None]})],
	))
	def test_bare_and_no_args(self, repeat_str, in_and_out) -> None:
		'Bare repeat as a value accepts any list item and coerces null to an empty list.'
		data, out = in_and_out
		assert_equals(repeat_str, {'items': repeat()}, data, out)

	def test_other_then_repeat(self) -> None:
		'Static list entries are applied before the repeated suffix.'
		assert_equals(
			s('''
				items:
					- str
					- taml.repeat(int)
			'''),
			{'items': [str, repeat(int)]},
			"items: [0, '1', 2, '3']",
			{'items': ['0', 1, 2, 3]},
		)
	def test_repeat_then_other(self) -> None:
		'Repeat before another list schema describes one nested list value.'
		assert_equals(
			s('''
				items:
					- taml.repeat(int)
					- str
			'''),
			{'items': [repeat(int), str]},
			"items: [1, '2', 3]",
			{'items': [1, 2, '3']},
		)
	def test_multiple_repeat(self) -> None:
		'Multiple repeat entries each describe their own nested list value.'
		assert_equals(
			s('''
				items:
					- taml.repeat(int)
					- taml.repeat(str)
			'''),
			{'items': [repeat(int), repeat(str)]},
			"items: [['1', '2'], [3, 4]]",
			{'items': [[1, 2], ['3', '4']]},
		)

	@parameterized.expand([
		('default_null', 'taml.repeat(int)', {'items': repeat(int)}, 'items:', {'items': []}),
		('false_null', 'taml.repeat(int, coerce=False)', {'items': repeat(int, coerce=False)}, 'items:', {'items': None}),
		('false_values', 'taml.repeat(int, coerce=False)', {'items': repeat(int, coerce=False)}, "items: ['1', '2']", {'items': [1, 2]}),
	])
	def test_value_coerce(self, _name, marker, native, data, expected) -> None:
		'Coerce controls whether a null repeated list value becomes an empty list.'
		assert_equals(f'items: {marker}', native, data, expected)

	def test_repeat_coerce_affects_equality(self) -> None:
		assert repeat(coerce=True) != repeat(coerce=False)

	def test_missing_value_parent_is_not_inserted(self) -> None:
		assert_equals('items: taml.repeat(int)', {'items': repeat(int)}, '{}', {})
	def test_missing_marker_parent_is_not_inserted(self) -> None:
		assert_equals('items: [taml.repeat(int)]', {'items': [repeat(int)]}, '{}', {})

	@parameterized.expand([
		('dict', 'lst: {a: 1}', 'Expected list or None, got dict at lst (line 1, col 6)'),
		('scalar', 'lst: 1', 'Expected list or None, got int (line 1, col 6)'),
	])
	def test_value_rejects_wrong_structure(self, _name, data, msg) -> None:
		assert_raises2('lst: taml.repeat(int)', {'lst': repeat(int)}, data, StructureError, msg)

	def test_unrelated_error_propagates(self) -> None:
		'Errors other than TypeError and ValueError are not disguised as conversion failures.'
		assert_raises2(
			'items: taml.repeat(utils.raise_runtime_error)',
			{'items': repeat(raise_runtime_error)},
			'items: [value]',
			RuntimeError,
			'runtime failure',
		)
	def test_native_traceback_points_to_definition(self) -> None:
		'A native repeat conversion error includes the schema definition site.'
		schema = {'items': repeat(int)}; def_line = inspect.currentframe().f_lineno
		try:
			taml.loads("items: ['wrong']", schema)
		except ConversionValueError as e:
			frames = traceback.extract_tb(e.__traceback__)
			assert any(fr.name == 'test_native_traceback_points_to_definition' and fr.lineno == def_line for fr in frames), \
				f'traceback missing definition site line {def_line}: {[(fr.filename, fr.lineno, fr.name) for fr in frames]}'
		else:
			raise AssertionError('expected ConversionValueError to be raised')

class Required(unittest.TestCase):
	def test_required(self) -> None:
		'Required inside a repeated list schema rejects null items.'
		assert_raises2(
			s('''
				items:
					- taml.repeat(taml.required(int))
			'''),
			{'items': [repeat(required(int))]},
			"items: ['1', null, '3']",
			RequiredError,
			'items[1] is required (line 1, col 14)',
		)
	def test_required_path_reports_repeated_index(self) -> None:
		'Required inside repeat reports the actual repeated list index.'
		assert_raises2(
			'items: taml.repeat(taml.required(int))',
			{'items': repeat(required(int))},
			"items: ['1', '2', null]",
			RequiredError,
			'items[2] is required (line 1, col 19)',
		)
	def test_nested_required_path_reports_repeated_key(self) -> None:
		'A required error inside dictionary repeat includes the selected data key.'
		assert_raises2(
			s('''
				cfg:
					taml.repeat():
						port: taml.required(int)
			'''),
			{'cfg': {repeat(): {'port': required(int)}}},
			s('''
				cfg:
					primary:
						port: '8080'
					backup: {}
			'''),
			RequiredError,
			'cfg.backup.port is required (line 4, col 2)',
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Dicts).debug()
	unittest.TestLoader().loadTestsFromTestCase(Lists).debug()
	print('tests passed')
