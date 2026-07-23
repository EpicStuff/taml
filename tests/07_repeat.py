import inspect, traceback, unittest

from epicstuff import s
from parameterized import parameterized
from taml import ConversionValueError, RequiredError, SchemaDefinitionError, StructureError, repeat, taml
from utils import assert_equals, assert_raises, assert_raises2, record_then_raise_on_bad, recorded_values, reset_recorded_values


class Dicts(unittest.TestCase):
	'Test taml.repeat used for dictionary entries.'

	def test_missing_required_key_reports_data_key(self) -> None:
		'A required error under repeat reports the actual data key.'
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		data = s('''
			a:
				b:
					a: test1
					b: 1
				c:
					a: test2
				d:
					b: 3
		''')
		assert_raises(RequiredError, lambda: taml.loads(data, schema), 'a.d.a is required (line 7, col 2)')
	def test_nested_required_path_reports_repeated_key(self) -> None:
		'A required error inside dictionary repeat includes the selected data key.'
		schema = taml.loads(
			s('''
				cfg:
					taml.repeat():
						port: taml.required(int)
			'''),
			is_schema=True,
		)
		data = s('''
			cfg:
				primary:
					port: '8080'
				backup: {}
		''')
		assert_raises(RequiredError, lambda: taml.loads(data, schema), 'cfg.backup.port is required (line 4, col 2)')
	def test_all_entries_satisfy_schema(self) -> None:
		'Every matching dictionary entry is converted with the repeated schema.'
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		out = taml.loads(
			s('''
				a:
					b:
						a: test1
						b: 1
					c:
						a: test2
						b: '2'
					d:
						a: test3
						b: '3'
			'''),
			schema,
		)
		assert out == {'a': {
			'b': {'a': 'test1', 'b': 1},
			'c': {'a': 'test2', 'b': 2},
			'd': {'a': 'test3', 'b': 3},
		}}
	def test_static_key_alongside_repeat(self) -> None:
		'A static key takes precedence while repeat covers the other entries.'
		schema = taml.loads(
			s('''
				cfg:
					name: taml.required
					taml.repeat():
						port: int
			'''),
			is_schema=True,
		)
		out = taml.loads(
			s('''
				cfg:
					name: my-service
					primary:
						port: '8080'
					backup:
						port: '8081'
			'''),
			schema,
		)
		assert out == {'cfg': {
			'name': 'my-service',
			'primary': {'port': 8080},
			'backup': {'port': 8081},
		}}
	def test_missing_repeat_parent_is_not_inserted(self) -> None:
		schema = taml.loads(
			s('''
				cfg:
					taml.repeat():
						port: int
			'''),
			is_schema=True,
		)
		assert taml.loads('{}\n', schema) == {}
	@parameterized.expand([
		('list', 'cfg: []\n'),
		('scalar', 'cfg: 1\n'),
	])
	def test_repeat_dictionary_rejects_wrong_structure(self, _name, data) -> None:
		schema = taml.loads(
			s('''
				cfg:
					taml.repeat():
						port: int
			'''),
			is_schema=True,
		)
		assert_raises(StructureError, lambda: taml.loads(data, schema))
	def test_key_cannot_take_schema_argument(self) -> None:
		'Repeat used as a dictionary key cannot take a positional schema argument.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(
				s('''
					a:
						taml.repeat(int):
							x: taml.required
				'''),
				is_schema=True,
			),
			'taml.repeat used as a key cannot take a schema argument at a[*] (line 2, col 2)',
		)
	@parameterized.expand([
		('bare', 'taml.repeat:'),
		('call', 'taml.repeat(): null'),
	])
	def test_key_requires_nested_schema(self, _name, marker) -> None:
		'Repeat used as a dictionary key requires a nested schema.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(
				s(f'''
					a:
						{marker}
				'''),
				is_schema=True,
			),
			'taml.repeat used as a key requires a nested schema at a[*] (line 2, col 2)',
		)
	def test_bare_key_reports_missing_required(self) -> None:
		'Bare repeat used as a key behaves like taml.repeat().'
		schema = taml.loads(
			s('''
				a:
					taml.repeat:
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		assert_raises(
			RequiredError,
			lambda: taml.loads('a:\n\tb:\n\t\tc: x\n', schema),
			'a.b.a is required (line 2, col 2)',
		)
	def test_bare_key_accepts_matching_entry(self) -> None:
		'Bare repeat used as a key accepts and converts a matching entry.'
		schema = taml.loads(
			s('''
				a:
					taml.repeat:
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n\tb:\n\t\ta: ok\n\t\tb: 1\n', schema) == {'a': {'b': {'a': 'ok', 'b': 1}}}
	@parameterized.expand([
		('default_null', 'taml.repeat()', 'a:\n', {'a': {}}),
		('default_empty', 'taml.repeat()', 'a: {}\n', {'a': {}}),
		('false_null', 'taml.repeat(coerce=False)', 'a:\n', {'a': None}),
		('false_empty', 'taml.repeat(coerce=False)', 'a: {}\n', {'a': {}}),
	])
	def test_key_coerce(self, _name, marker, data, expected) -> None:
		'Coerce controls whether null repeated dictionaries become empty dictionaries.'
		schema = taml.loads(
			s(f'''
				a:
					{marker}:
						a: taml.required
			'''),
			is_schema=True,
		)
		assert taml.loads(data, schema) == expected


class Lists(unittest.TestCase):
	'Test taml.repeat used for lists.'

	def test_any_length(self) -> None:
		'A repeated list schema converts every item regardless of length.'
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads("items: ['1', '2', '3', '4']\n", schema) == {'items': [1, 2, 3, 4]}
	def test_empty(self) -> None:
		'A repeated list schema accepts an empty list.'
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads('items: []\n', schema) == {'items': []}
	def test_static_prefix(self) -> None:
		'Static list entries are applied before the repeated suffix.'
		schema = taml.loads(
			s('''
				items:
					- str
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads("items: ['hello', '1', '2', '3']\n", schema) == {'items': ['hello', 1, 2, 3]}
	def test_repeat_value_before_static_item(self) -> None:
		'Repeat before another list schema describes one nested list value.'
		assert_equals(
			s('''
				items:
					- taml.repeat(int)
					- str
			'''),
			{'items': [repeat(int), str]},
			"items: [['1', '2'], value]\n",
			{'items': [[1, 2], 'value']},
		)
	def test_multiple_repeat_values(self) -> None:
		'Multiple repeat entries each describe their own nested list value.'
		assert_equals(
			s('''
				items:
					- taml.repeat(int)
					- taml.repeat(str)
			'''),
			{'items': [repeat(int), repeat(str)]},
			"items: [['1', '2'], [3, 4]]\n",
			{'items': [[1, 2], ['3', '4']]},
		)
	def test_required(self) -> None:
		'Required inside a repeated list schema rejects null items.'
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(taml.required(int))
			'''),
			is_schema=True,
		)
		assert_raises(
			RequiredError,
			lambda: taml.loads("items: ['1', null, '3']\n", schema),
			'items[1] is required (line 1, col 14)',
		)
	def test_required_path_reports_repeated_index(self) -> None:
		'Required inside repeat reports the actual repeated list index.'
		schema = taml.loads('items: taml.repeat(taml.required(int))\n', is_schema=True)
		assert_raises(
			RequiredError,
			lambda: taml.loads("items: ['1', '2', null]\n", schema),
			'items[2] is required (line 1, col 19)',
		)
	def test_bare_value_list_of_anything(self) -> None:
		'Bare repeat as a value accepts any list item and coerces null to an empty list.'
		schema = taml.loads('items: taml.repeat()\n', is_schema=True)
		assert taml.loads('items:\n', schema) == {'items': []}
		assert taml.loads("items: [1, 'a', null]\n", schema) == {'items': [1, 'a', None]}
	def test_bare_as_list_element(self) -> None:
		'Bare repeat as a list element behaves like taml.repeat().'
		schema = taml.loads(
			s('''
				items:
					- taml.repeat
			'''),
			is_schema=True,
		)
		assert taml.loads('items:\n', schema) == {'items': []}
		assert taml.loads("items: [1, 'a']\n", schema) == {'items': [1, 'a']}
	@parameterized.expand([
		('default_null', 'taml.repeat(int)', 'items:\n', {'items': []}),
		('default_values', 'taml.repeat(int)', "items: ['1', '2']\n", {'items': [1, 2]}),
		('false_null', 'taml.repeat(int, coerce=False)', 'items:\n', {'items': None}),
		('false_values', 'taml.repeat(int, coerce=False)', "items: ['1', '2']\n", {'items': [1, 2]}),
	])
	def test_value_coerce(self, _name, marker, data, expected) -> None:
		'Coerce controls whether a null repeated list value becomes an empty list.'
		schema = taml.loads(f'items: {marker}\n', is_schema=True)
		assert taml.loads(data, schema) == expected
	@parameterized.expand([
		('default', 'taml.repeat(int)', {'items': []}),
		('false', 'taml.repeat(int, coerce=False)', {'items': None}),
	])
	def test_marker_coerce(self, _name, marker, expected) -> None:
		'Coerce behaves the same when repeat is a list marker.'
		schema = taml.loads(
			s(f'''
				items:
					- {marker}
			'''),
			is_schema=True,
		)
		assert taml.loads('items:\n', schema) == expected
	def test_missing_value_parent_is_not_inserted(self) -> None:
		assert_equals('items: taml.repeat(int)\n', {'items': repeat(int)}, '{}\n', {})
	def test_missing_marker_parent_is_not_inserted(self) -> None:
		assert_equals('items: [taml.repeat(int)]\n', {'items': [repeat(int)]}, '{}\n', {})
	def test_native_list_marker_converts_items(self) -> None:
		'A native repeat list marker converts every list item.'
		schema = {'lst': [repeat(int)]}
		assert taml.loads("lst: ['1', '2']\n", schema) == {'lst': [1, 2]}
	def test_native_value_converts_items(self) -> None:
		'A native repeat value converts every list item.'
		schema = {'lst': repeat(int)}
		assert taml.loads("lst: ['1', '2']\n", schema) == {'lst': [1, 2]}
	@parameterized.expand([
		('dict', 'lst: {a: 1}\n'),
		('scalar', 'lst: 1\n'),
	])
	def test_value_rejects_wrong_structure(self, _name, data) -> None:
		assert_raises2('lst: taml.repeat(int)\n', {'lst': repeat(int)}, data, StructureError)
	@parameterized.expand([
		('dict', 'lst: {a: 1}\n'),
		('scalar', 'lst: 1\n'),
	])
	def test_marker_rejects_wrong_structure(self, _name, data) -> None:
		assert_raises2('lst: [taml.repeat(int)]\n', {'lst': [repeat(int)]}, data, StructureError)
	def test_unrelated_error_propagates_after_successful_item(self) -> None:
		reset_recorded_values()
		assert_raises(
			RuntimeError,
			lambda: taml.loads("items: [ok, bad]\n", {'items': repeat(record_then_raise_on_bad)}),
			'runtime failure',
		)
		assert recorded_values == [('ok', None), ('bad', None)]
	def test_native_traceback_points_to_definition(self) -> None:
		'A native repeat conversion error includes the schema definition site.'
		schema = {'items': repeat(int)}; def_line = inspect.currentframe().f_lineno
		try:
			taml.loads("items: ['wrong']\n", schema)
		except ConversionValueError as e:
			frames = traceback.extract_tb(e.__traceback__)
			assert any(fr.name == 'test_native_traceback_points_to_definition' and fr.lineno == def_line for fr in frames), \
				f'traceback missing definition site line {def_line}: {[(fr.filename, fr.lineno, fr.name) for fr in frames]}'
		else:
			raise AssertionError('expected ConversionValueError to be raised')


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Dicts).debug()
	unittest.TestLoader().loadTestsFromTestCase(Lists).debug()
	print('tests passed')