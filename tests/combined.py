'Comprehensive line-number tests for schema error messages.'
import os
import unittest
from pathlib import Path

from parameterized import parameterized

from epicstuff import s
from taml import taml, RequiredError, StrictError, StructureError, SchemaDefinitionError, ConversionTypeError, ConversionValueError
from utils import assert_raises


os.chdir(Path(__file__).parent)


# Schema (depth 4, multiple keys per level):
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
schema = taml.loads(SCHEMA_SRC, is_schema=True)

# Baseline valid data with extra lines/keys/comments so its line layout
# differs from the schema's, making data-vs-schema position obvious:
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


class TestSchemaLines(unittest.TestCase):

	# Sanity: baseline parses cleanly
	def test_baseline_parses(self):
		'''Verify the shared line-number fixture parses successfully before mutation tests.'''
		out = taml.loads(DATA_OK, schema)
		assert out['config']['port'] == 8080
		assert out['config']['nested']['d']['e'] == 'ev'
		assert out['config']['nested']['d']['f'] == 7
		assert out['items'] == [1, 'r']

	# === StrictError at varying depths ===

	@parameterized.expand([
		# depth 2: config.port at line 8
		('depth2_port', 'port: 8080', "port: '8080'", "Expected int, got str: '8080' (line 8, col 8)"),
		# depth 3: config.nested.b at line 13
		('depth3_b', 'b: 42', "b: 'x'", "Expected int, got str: 'x' (line 13, col 6)"),
		# depth 4: config.nested.d.f at line 17
		('depth4_f', 'f: 7', "f: 'q'", "Expected int, got str: 'q' (line 17, col 7)"),
	])
	def test_strict_error(self, label, old, new, expected):
		'''Verify strict errors report data source locations at multiple nesting depths.'''
		assert_raises(
			StrictError,
			lambda: taml.loads(DATA_OK.replace(old, new), schema),
			expected,
		)

	# === StructureError ===

	# depth 3, list expected: config.nested.c at line 14
	def test_structure_error_list(self):
		'''Verify list structure errors report the offending data value location.'''
		assert_raises(
			StructureError,
			lambda: taml.loads(DATA_OK.replace('c: [1, 2]', 'c: {z: 1}'), schema),
			"Expected list or None, got CommentedMap: {'z': 1} (line 14, col 6)",
		)

	# depth 1, dict expected: config replaced with a scalar (line 3)
	def test_structure_error_dict(self):
		'''Verify dict structure errors report the offending data value location.'''
		data = s('''
			# scalar config test
			name: 'hi'
			config: 'wrong'
			items:
				- 1
				- 'r'
		''')
		assert_raises(
			StructureError,
			lambda: taml.loads(data, schema),
			"Expected dict or None, got str: 'wrong' (line 3, col 9)",
		)

	# === ConversionError (bare callable schema fails to convert data) ===

	@parameterized.expand([
		# ValueError-style: int('nope') — config.nested.c[0] at line 14
		('value_error', ConversionValueError, 'c: [1, 2]', "c: ['nope', 2]", "Cannot convert 'nope' to int (line 14, col 7)"),
		# TypeError-style: int([]) — config.nested.c[0] at line 14
		('type_error', ConversionTypeError, 'c: [1, 2]', 'c: [[], 2]', 'Cannot convert [] to int (line 14, col 7)'),
	])
	def test_conversion_error(self, label, exc, old, new, expected):
		'''Verify conversion errors report the offending scalar item location.'''
		assert_raises(
			exc,
			lambda: taml.loads(DATA_OK.replace(old, new), schema),
			expected,
		)

	# === RequiredError at varying depths ===

	@parameterized.expand([
		# depth 4: config.nested.d.e missing; points at parent key d
		('depth4_e', "\t\t\te: 'ev'\n", '', 'config.nested.d.e is required (line 15, col 3)'),
		# depth 2: config.host missing; points at parent key config
		('depth2_host', "\thost: 'h'\n", '', 'config.host is required (line 6, col 1)'),
		# depth 1 inside list: items[1] missing; points at parent key items
		('depth1_items', "\t- 1\n\t- 'r'", '\t- 1', 'items[1] is required (line 20, col 1)'),
	])
	def test_required_error(self, label, old, new, expected):
		'''Verify required errors report parent locations at multiple nesting depths.'''
		assert_raises(
			RequiredError,
			lambda: taml.loads(DATA_OK.replace(old, new), schema),
			expected,
		)

	# === SchemaDefinitionError at varying depths ===

	@parameterized.expand([
		# depth 2: bare strict at config.port (line 3)
		('depth2_bare_strict', 'port: taml.strict(int)', 'port: taml.strict', 'Missing arguments for strict at config.port (line 3, col 8)'),
		# depth 3: required inside strict at config.nested.b (line 7)
		('depth3_required_in_strict', 'b: taml.strict(int)', 'b: taml.strict(taml.required)', 'Missing arguments for required inside strict at config.nested.b (line 7, col 6)'),
		# depth 4: unsupported expression (BinOp) at config.nested.d.f (line 11)
		('depth4_binop', 'f: taml.strict(int)', 'f: taml.strict(1+2)', "Unsupported expression '1+2' at config.nested.d.f (line 11, col 19)"),
		# depth 2: kwarg unpacking rejection at config.port (line 3)
		('depth2_kwarg', 'port: taml.strict(int)', 'port: epicstuff.Dict(**foo)', 'Keyword argument must be written as name=value at config.port (line 3, col 23)'),
	])
	def test_schema_definition_error(self, label, old, new, expected):
		'''Verify schema definition errors include schema paths and source locations.'''
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(SCHEMA_SRC.replace(old, new), is_schema=True),
			expected,
		)

	# === ImportError at varying depths ===

	@parameterized.expand([
		# depth 2: bare missing module at config.port (line 3)
		('depth2_module', 'port: taml.strict(int)', 'port: some_nonexistent_module.fn', "No module named 'some_nonexistent_module' at config.port (line 3, col 8)"),
		# depth 3: missing attribute on a real module at config.nested.b (line 7)
		('depth3_attr', 'b: taml.strict(int)', 'b: os.path.nonexistent_attr', "No module named 'os.path.nonexistent_attr'; 'os.path' is not a package at config.nested.b (line 7, col 6)"),
	])
	def test_import_error(self, label, old, new, expected):
		'''Verify schema import errors include schema paths and source locations.'''
		assert_raises(
			ImportError,
			lambda: taml.loads(SCHEMA_SRC.replace(old, new), is_schema=True),
			expected,
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaLines).debug()
	print('tests passed')
