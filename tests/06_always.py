# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001

import inspect, traceback, unittest

from epicstuff import run_fix_import  # noqa: F401
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, SchemaDefinitionError, always, required, taml

from .utils import assert_equals, assert_raises, assert_raises2, raise_runtime_error, recorded_values, record_value, return_none, return_value, skip


class Main(unittest.TestCase):
	def test_runs_on_null(self) -> None:
		'Make sure func gets run on null.'
		assert_equals('a: taml.always(bool)', {'a': always(func=bool)}, 'a: null', {'a': False})
	def test_works_on_value(self) -> None:
		'Make sure func gets run when theres value.'
		assert_equals('a: taml.always(int)', {'a': always(int)}, 'a: "1"', {'a': 1})

	def test_not_equal(self) -> None:
		assert always(int) != required(int)
		assert always(int) != always(str)

	@parameterized.expand([
		('null', 'a: null'),
		('zero', 'a: 0'),
		('false', 'a: false'),
		('empty_string', "a: ''", ''),
		('empty_list', 'a: []'),
		('empty_dict', 'a: {}'),
	])
	def test_runs_for_falsy_value(self, _name, data) -> None:
		assert_equals(
			'a: always(utils.return_value)',
			{'a': always(return_value)},
			data,
			{'a': 'test'},
		)
	def test_value_error(self) -> None:
		'Always wraps a ValueError from the converter, pointing at the value.'
		assert_raises2('a: taml.always(int)', {'a': always(int)}, "a: 'nope'", ConversionValueError, "Cannot convert 'nope' to int (line 1, col 4)")
	def test_type_error(self) -> None:
		'Always wraps a TypeError from the converter, pointing at the value.'
		assert_raises2('a: taml.always(int)', {'a': always(int)}, 'a: []', ConversionTypeError, 'Cannot convert [] to int (line 1, col 4)')
	def test_unrelated_error_propagates(self) -> None:
		'Errors other than TypeError and ValueError are not disguised as conversion failures.'
		assert_raises(RuntimeError, lambda: taml.loads('a: value\n', {'a': always(raise_runtime_error)}), 'runtime failure')
	def test_converter_can_return_none(self) -> None:
		assert taml.loads('a: value\n', {'a': always(return_none)}) == {'a': None}
	def test_does_not_insert_missing_key(self) -> None:
		'Verify always does not insert a missing key.'
		assert_equals('a: taml.always(tests.utils.return_value)', {'a': always(return_value)}, '{}', {})

	@skip('Right now always always runs, maybe ill change this later')  # todo: maybe
	def test_nested_null_runs_but_missing_key_does_not(self) -> None:
		schema = {'outer': {'a': always(record_value)}}
		recorded_values.clear()
		assert taml.loads('outer: {a: null}\n', schema) == {'outer': {'a': None}}
		assert recorded_values == [(None, None)]
		recorded_values.clear()
		assert taml.loads('outer: {}\n', schema) == {'outer': {}}
		assert recorded_values == []
	@parameterized.expand([
		('empty_document', '', None),
		('missing_parent', '{}', {}),
		('null_parent', 'outer: null', {'outer': None}),
	])
	def test_nested_parent_missing_or_null_does_not_run(self, _name, data, expected) -> None:
		schema = {'outer': {'a': always(record_value)}}
		recorded_values.clear()
		assert taml.loads(data, schema) == expected
		assert recorded_values == []
	def test_list_null_runs_but_missing_index_does_not(self) -> None:
		schema = {'items': [always(record_value)]}
		recorded_values.clear()
		assert taml.loads('items: [null]\n', schema) == {'items': [None]}
		assert recorded_values == [(None, None)]
		recorded_values.clear()
		assert taml.loads('items: []\n', schema) == {'items': []}
		assert recorded_values == []
	@parameterized.expand([
		('empty_document', '', None),
		('missing_parent', '{}', {}),
		('null_parent', 'items: null', {'items': None}),
	])
	def test_list_parent_missing_or_null_does_not_run(self, _name, data, expected) -> None:
		schema = {'items': [always(record_value)]}
		recorded_values.clear()
		assert taml.loads(data, schema) == expected
		assert recorded_values == []
	@parameterized.expand([
		('integer', 'a: taml.always(1)'),
		('none', 'a: taml.always(None)'),
	])
	def test_rejects_non_callable_in_taml(self, _name, schema) -> None:
		assert_raises(SchemaDefinitionError, lambda: taml.loads(schema, is_schema=True))
	@parameterized.expand([
		('integer', lambda: always(1)),
		('none', lambda: always(None)),
	])
	def test_rejects_non_callable_natively(self, _name, make) -> None:
		assert_raises(TypeError, make)
	def test_native_traceback_points_to_definition(self) -> None:
		'A native always conversion error includes the schema definition site.'
		schema = {'a': always(int)}; def_line = inspect.currentframe().f_lineno
		try:
			taml.loads("a: 'wrong'\n", schema)
		except ConversionValueError as e:
			frames = traceback.extract_tb(e.__traceback__)
			assert any(fr.name == 'test_native_traceback_points_to_definition' and fr.lineno == def_line for fr in frames), \
				f'traceback missing definition site line {def_line}: {[(fr.filename, fr.lineno, fr.name) for fr in frames]}'
		else:
			raise AssertionError('expected ConversionValueError to be raised')
	def test_missing_func(self) -> None:
		'Bare always with no func raises definition error.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.always', is_schema=True),
			'Missing arguments for always at a (line 1, col 4)',
		)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.always()', is_schema=True),
			'Missing arguments for always at a (line 1, col 4)',
		)
		assert_raises(TypeError, always)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
