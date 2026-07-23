'Comprehensive path and source location tests for schema errors.'
import copy, unittest

from epicstuff import s
from parameterized import parameterized
from taml import ConversionTypeError, ConversionValueError, RequiredError, SchemaDefinitionError, StrictError, StructureError, taml
from utils import assert_raises, create_file


SCHEMA_SRC = s('''
	name: str
	config:
		port: taml.strict(int)
		host: taml.required
		nested:
			a: taml.required
			b: taml.strict(int)
			c: [int]
			d:
				e: taml.required
				f: taml.strict(int)
	items:
		- int
		- taml.required
''')
SCHEMA = taml.loads(SCHEMA_SRC, is_schema=True)

# Extra keys and comments make data locations clearly different from schema locations.
DATA_OK = s('''
	# Top-level YAML comment
	# Second comment line
	name: 'hi'
	# comment between top-level keys
	extra_top: 'unused'
	config:
		# comment inside config
		port: 8080
		host: 'h'
		nested:
			# comment inside nested
			a: 'av'
			b: 42
			c: [1, 2]
			d:
				e: 'ev'
				f: 7
			extra_nested: 'unused'
	# section break comment
	items:
		- 1
		- 'r'
''')


class Main(unittest.TestCase):
	'Test errors at several nesting depths and source locations.'

	def test_baseline_parses(self) -> None:
		'Verify the shared fixture is valid before mutation tests.'
		out = taml.loads(DATA_OK, SCHEMA)
		assert out['config']['port'] == 8080
		assert out['config']['nested']['d']['e'] == 'ev'
		assert out['config']['nested']['d']['f'] == 7
		assert out['items'] == [1, 'r']
	def test_schema_is_not_mutated(self) -> None:
		'Applying the shared schema does not change its conversion behavior.'
		before = copy.deepcopy(SCHEMA)
		taml.loads(DATA_OK, SCHEMA)
		assert SCHEMA == before
	def test_data_file_error_includes_path(self) -> None:
		with create_file(DATA_OK.replace('port: 8080', "port: 'wrong'"), 'data.taml') as data_path:
			try:
				taml.load(data_path, SCHEMA)
			except StrictError as e:
				assert str(data_path) in str(e), str(e)
			else:
				raise AssertionError('expected StrictError to be raised')

	@parameterized.expand([
		('depth2_port', 'port: 8080', "port: '8080'", "Expected (int), got '8080' (line 8, col 8)"),
		('depth3_b', 'b: 42', "b: 'x'", "Expected (int), got 'x' (line 13, col 6)"),
		('depth4_f', 'f: 7', "f: 'q'", "Expected (int), got 'q' (line 17, col 7)"),
	])
	def test_strict_error(self, _name, old, new, expected) -> None:
		'Strict errors report data locations at several nesting depths.'
		assert_raises(StrictError, lambda: taml.loads(DATA_OK.replace(old, new), SCHEMA), expected)

	@parameterized.expand([
		(
			'list',
			DATA_OK.replace('c: [1, 2]', 'c: {z: 1}'),
			"Expected list or None, got dict: {'z': 1} (line 14, col 6)",
		),
		(
			'dict',
			s('''
				# scalar config test
				name: 'hi'
				config: 'wrong'
				items:
					- 1
					- 'r'
			'''),
			"Expected dict or None, got str: 'wrong' (line 3, col 9)",
		),
	])
	def test_structure_error(self, _name, data, expected) -> None:
		'Structure errors report the offending data value location.'
		assert_raises(StructureError, lambda: taml.loads(data, SCHEMA), expected)

	@parameterized.expand([
		('value_error', ConversionValueError, 'c: [1, 2]', "c: ['nope', 2]", "Cannot convert 'nope' to int (line 14, col 7)"),
		('type_error', ConversionTypeError, 'c: [1, 2]', 'c: [[], 2]', 'Cannot convert [] to int (line 14, col 7)'),
	])
	def test_conversion_error(self, _name, error, old, new, expected) -> None:
		'Conversion errors report the offending scalar item location.'
		assert_raises(error, lambda: taml.loads(DATA_OK.replace(old, new), SCHEMA), expected)

	@parameterized.expand([
		('depth4_e', "\t\t\te: 'ev'\n", '', 'config.nested.d.e is required (line 15, col 3)'),
		('depth2_host', "\thost: 'h'\n", '', 'config.host is required (line 6, col 1)'),
		('depth1_items', "\t- 1\n\t- 'r'", '\t- 1', 'items[1] is required (line 20, col 1)'),
	])
	def test_required_error(self, _name, old, new, expected) -> None:
		'Required errors report parent locations at several nesting depths.'
		assert_raises(RequiredError, lambda: taml.loads(DATA_OK.replace(old, new), SCHEMA), expected)

	@parameterized.expand([
		(
			'depth2_bare_strict',
			'port: taml.strict(int)',
			'port: taml.strict',
			'Missing arguments for strict at config.port (line 3, col 8)',
		),
		(
			'depth3_required_in_strict',
			'b: taml.strict(int)',
			'b: taml.strict(taml.required)',
			'Missing arguments for required inside strict at config.nested.b (line 7, col 6)',
		),
	])
	def test_schema_definition_error(self, _name, old, new, expected) -> None:
		'Schema definition errors include schema paths and locations.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(SCHEMA_SRC.replace(old, new), is_schema=True),
			expected,
		)

	@parameterized.expand([
		(
			'depth2_module',
			'port: taml.strict(int)',
			'port: some_nonexistent_module.fn',
			"No module named 'some_nonexistent_module' at config.port (line 3, col 8)",
		),
		(
			'depth3_attr',
			'b: taml.strict(int)',
			'b: os.path.nonexistent_attr',
			"No module named 'os.path.nonexistent_attr'; 'os.path' is not a package at config.nested.b (line 7, col 6)",
		),
	])
	def test_import_error(self, _name, old, new, expected) -> None:
		'Schema import errors include schema paths and locations.'
		assert_raises(ImportError, lambda: taml.loads(SCHEMA_SRC.replace(old, new), is_schema=True), expected)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')