'Comprehensive line-number tests for schema error messages.'
import os, contextlib
from pathlib import Path

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

# Sanity: baseline parses cleanly
out = taml.loads(DATA_OK, schema)
assert out['config']['port'] == 8080
assert out['config']['nested']['d']['e'] == 'ev'
assert out['config']['nested']['d']['f'] == 7
assert out['items'] == [1, 'r']


# === StrictError at varying depths ===

# depth 2: config.port at line 8
assert_raises(
	StrictError,
	lambda: taml.loads(DATA_OK.replace('port: 8080', "port: '8080'"), schema),
	"Expected int, got str: '8080' (line 8, col 8)",
)

# depth 3: config.nested.b at line 13
assert_raises(
	StrictError,
	lambda: taml.loads(DATA_OK.replace('b: 42', "b: 'x'"), schema),
	"Expected int, got str: 'x' (line 13, col 6)",
)

# depth 4: config.nested.d.f at line 17
assert_raises(
	StrictError,
	lambda: taml.loads(DATA_OK.replace('f: 7', "f: 'q'"), schema),
	"Expected int, got str: 'q' (line 17, col 7)",
)


# === StructureError ===

# depth 3, list expected: config.nested.c at line 14
assert_raises(
	StructureError,
	lambda: taml.loads(DATA_OK.replace('c: [1, 2]', 'c: {z: 1}'), schema),
	"Expected MutableSequence or None, got CommentedMap: {'z': 1} (line 14, col 6)",
)

# depth 1, dict expected: config replaced with a scalar (line 3)
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
	"Expected MutableMapping or None, got str: 'wrong' (line 3, col 9)",
)


# === ConversionError (bare callable schema fails to convert data) ===

# ValueError-style: int('nope') — config.nested.c[0] at line 14
assert_raises(
	ConversionValueError,
	lambda: taml.loads(DATA_OK.replace('c: [1, 2]', "c: ['nope', 2]"), schema),
	"Cannot convert 'nope' to int (line 14, col 7)",
)

# TypeError-style: int([]) — config.nested.c[0] at line 14
assert_raises(
	ConversionTypeError,
	lambda: taml.loads(DATA_OK.replace('c: [1, 2]', 'c: [[], 2]'), schema),
	'Cannot convert [] to int (line 14, col 7)',
)


# === RequiredError at varying depths ===

# depth 4: config.nested.d.e missing; points at parent key d
assert_raises(
	RequiredError,
	lambda: taml.loads(DATA_OK.replace("\t\t\te: 'ev'\n", ''), schema),
	'config.nested.d.e is required (line 15, col 3)',
)

# depth 2: config.host missing; points at parent key config
assert_raises(
	RequiredError,
	lambda: taml.loads(DATA_OK.replace("\thost: 'h'\n", ''), schema),
	'config.host is required (line 6, col 1)',
)

# depth 1 inside list: items[1] missing; points at parent key items
assert_raises(
	RequiredError,
	lambda: taml.loads(DATA_OK.replace("\t- 1\n\t- 'r'", '\t- 1'), schema),
	'items[1] is required (line 20, col 1)',
)


# === SchemaDefinitionError at varying depths ===

# depth 2: bare strict at config.port (line 3)
assert_raises(
	SchemaDefinitionError,
	lambda: taml.loads(SCHEMA_SRC.replace('port: taml.strict(int)', 'port: taml.strict'), is_schema=True),
	'Missing arguments for strict (line 3, col 8)',
)

# depth 3: required inside strict at config.nested.b (line 7)
assert_raises(
	SchemaDefinitionError,
	lambda: taml.loads(SCHEMA_SRC.replace('b: taml.strict(int)', 'b: taml.strict(taml.required)'), is_schema=True),
	'Missing arguments for required inside strict (line 7, col 6)',
)

# depth 4: unsupported expression (BinOp) at config.nested.d.f (line 11)
assert_raises(
	SchemaDefinitionError,
	lambda: taml.loads(SCHEMA_SRC.replace('f: taml.strict(int)', 'f: taml.strict(1+2)'), is_schema=True),
	"Unsupported expression '1+2' (line 11, col 19)",
)

# depth 2: kwarg unpacking rejection at config.port (line 3)
assert_raises(
	SchemaDefinitionError,
	lambda: taml.loads(SCHEMA_SRC.replace('port: taml.strict(int)', 'port: epicstuff.Dict(**foo)'), is_schema=True),
	'Keyword argument must be written as name=value (line 3, col 23)',
)


# === ImportError at varying depths ===

# depth 2: bare missing module at config.port (line 3)
assert_raises(
	ImportError,
	lambda: taml.loads(SCHEMA_SRC.replace('port: taml.strict(int)', 'port: some_nonexistent_module.fn'), is_schema=True),
	"No module named 'some_nonexistent_module' (line 3, col 8)",
)

# depth 3: missing attribute on a real module at config.nested.b (line 7)
assert_raises(
	ImportError,
	lambda: taml.loads(SCHEMA_SRC.replace('b: taml.strict(int)', 'b: os.path.nonexistent_attr'), is_schema=True),
	"No module named 'os.path.nonexistent_attr'; 'os.path' is not a package (line 7, col 6)",
)


print('schema_lines.py: passed')
