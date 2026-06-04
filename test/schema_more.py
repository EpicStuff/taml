import datetime, os
from pathlib import Path

from epicstuff import Dict, run_install_trace, s  # noqa: F401
from taml import taml, required, strict, RequiredError, StrictError, StructureError, SchemaDefinitionError, ConversionTypeError, ConversionValueError
from utils import assert_raises

os.chdir(Path(__file__).parent)

# --- schema resolution (is_schema=True) ---

schema = taml.loads('a: int', is_schema=True)
assert schema['a'] is int

assert_raises(
	ImportError,
	lambda: taml.loads('a: some_nonexistent_module.fn', is_schema=True),
	"No module named 'some_nonexistent_module' (line 1, col 4)",
)
assert_raises(
	ImportError,
	lambda: taml.loads('a: os.path.nonexistent_attr', is_schema=True),
	"No module named 'os.path.nonexistent_attr'; 'os.path' is not a package (line 1, col 4)",
)


# --- regression: commas inside quoted args ---

schema = taml.loads("x: epicstuff.BoxDict(b='1,2')\n", is_schema=True)
assert taml.loads('x: {a: 1}\n', schema) == {'x': {'a': 1, 'b': '1,2'}}


# --- builtins resolution with args/kwargs ---

schema = taml.loads(
	'''
	a: int(base=2)
	b: int(base=16)
	''',
	is_schema=True,
)

assert taml.loads(
	'''
	a: '101'
	b: 'ff'
	''',
	schema,
) == {'a': 5, 'b': 255}


# --- module resolution ---

schema = taml.loads(
	'''
	d: datetime.date.fromisoformat
	p: pathlib.Path
	''',
	is_schema=True,
)

out = taml.loads(
	'''
	d: '2020-01-02'
	p: 'foo/bar'
	''',
	schema,
)
assert out['d'] == datetime.date(2020, 1, 2)
assert out['p'] == Path('foo/bar')


# --- required semantics ---

schema = taml.loads( 'a: taml.required', is_schema=True)

assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')
assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

schema = taml.loads( 'a: taml.required(int)', is_schema=True)

assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')
assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

schema = taml.loads('a: taml.required(int)', is_schema=True)

assert taml.loads('a: "1"\n', schema) == {'a': 1}
assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')
assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')


# --- strict semantics ---

schema = taml.loads('a: taml.strict(int)\n', is_schema=True)
assert taml.loads('a: 1\n', schema) == {'a': 1}
assert taml.loads('a: null\n', schema) == {'a': None}
assert taml.loads('{}\n', schema) == {}
assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema), "Expected int, got str: '1' (line 1, col 4)")

schema = taml.loads('a: taml.strict(taml.required(int))\n', is_schema=True)
assert taml.loads('a: 1\n', schema) == {'a': 1}
assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema), "Expected int, got str: '1' (line 1, col 4)")
assert_raises(RequiredError, lambda: taml.loads('{}\n', schema), 'a is required (line 1, col 1)')
assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema), 'a is required (line 1, col 4)')

assert_raises(
	SchemaDefinitionError,
	lambda: taml.loads('a: taml.strict(taml.required)\n', is_schema=True),
	'Missing arguments for required inside strict (line 1, col 4)',
)


# --- missing keys: safe callable vs strict callable ---

schema_safe = taml.loads('a: str\n', is_schema=True)
out = taml.loads('{}\n', schema_safe)
assert 'a' not in out  # schema should not insert keys

schema_strict = taml.loads('a: int\n', is_schema=True)
out = taml.loads('{}\n', schema_strict)
assert 'a' not in out  # missing keys should not error unless required

# explicit null should also not error unless required
out = taml.loads('a: null\n', schema_strict)
assert out['a'] is None

# but present non null values should still be validated
assert_raises(ConversionTypeError, lambda: taml.loads('a: []\n', schema_strict), 'Cannot convert [] to int (line 1, col 4)')
assert_raises(ConversionValueError, lambda: taml.loads("a: 'nope'\n", schema_strict), "Cannot convert 'nope' to int (line 1, col 4)")

# nested case: missing nested keys should not be inserted or error
schema_nested = taml.loads(
	'''
	a:
		b: int
	''',
	is_schema=True,
)

assert taml.loads('a: {}\n', schema_nested) == {'a': {}}

assert taml.loads('a:\n', schema_nested) == {'a': None}

assert taml.loads('a: {b: null}\n', schema_nested) == {'a': {'b': None}}

assert taml.loads('a:\n\tb:\n', schema_nested) == {'a': {'b': None}}

# --- nested call expressions inside args ---

# TODO: Add support for nested functions
# schema_nested_call = taml.loads("a: int(base=len('ab'))\n", is_schema=True)
# assert taml.loads("a: '11'\n", schema_nested_call) == Dict({'a': 3})


# --- sequence formatting behavior ---

schema = taml.loads('''
	lst:
		- int
		- int
		- str
	''', is_schema=True,
)

assert taml.loads("lst: ['1', '2']\n", schema) == {'lst': [1, 2]}  # does not append missing indices

schema_strict_missing_idx = taml.loads('''
	lst:
		- int
		- int
		- int
	''', is_schema=True,
)

assert taml.loads("lst: ['1', '2']\n", schema_strict_missing_idx) == {'lst': [1, 2]}  # missing indices should not error unless required

schema_required_idx = taml.loads('''
	lst:
		- int
		- taml.required
	''', is_schema=True,
)

assert_raises(RequiredError, lambda: taml.loads("lst: ['1']\n", schema_required_idx), 'lst[1] is required (line 1, col 1)')


# --- type mismatch errors ---

schema_list = taml.loads('x: [int]\n', is_schema=True)
assert_raises(StructureError, lambda: taml.loads('x: {a: 1}\n', schema_list), "Expected MutableSequence or None, got CommentedMap: {'a': 1} (line 1, col 4)")

schema_dict = taml.loads(
	'''
	x:
		a: int
	''',
	is_schema=True,
)
assert_raises(StructureError, lambda: taml.loads('x: [1]\n', schema_dict), 'Expected MutableMapping or None, got CommentedSeq: [1] (line 1, col 4)')

assert_raises(StructureError, lambda: taml.loads('x: 1\n', schema_dict), 'Expected MutableMapping or None, got int: 1 (line 1, col 4)')


# --- Python dict schemas (constructed directly, not parsed from YAML) ---

# bare builtin converts value
schema_py = {'a': int}
assert taml.loads('a: "1"\n', schema_py) == {'a': 1}

# wrong-type non-null value still errors
assert_raises((TypeError, ValueError), lambda: taml.loads("a: 'nope'\n", schema_py))
assert_raises((TypeError, ValueError), lambda: taml.loads('a: []\n', schema_py))

# missing key not inserted, explicit null preserved
assert 'a' not in taml.loads('{}\n', schema_py)
assert taml.loads('a: null\n', schema_py)['a'] is None

# nested dict schema
schema_nested_py = {'a': {'b': int}}
assert taml.loads('a: {b: "5"}\n', schema_nested_py) == {'a': {'b': 5}}
assert taml.loads('a:\n', schema_nested_py) == {'a': None}
assert taml.loads('a: {}\n', schema_nested_py) == {'a': {}}

# list inside dict schema, plus structure mismatches
schema_list_py = {'lst': [int]}
assert taml.loads("lst: ['1', '2']\n", schema_list_py) == {'lst': [1, '2']}
assert_raises(StructureError, lambda: taml.loads('lst: {a: 1}\n', schema_list_py))
assert_raises(StructureError, lambda: taml.loads('lst: 1\n', schema_list_py))

# required and strict instances used directly
schema_req_py = {'a': required('a', 0, 0)}
assert_raises(RequiredError, lambda: taml.loads('{}\n', schema_req_py))
assert_raises(RequiredError, lambda: taml.loads('a: null\n', schema_req_py))
assert taml.loads("a: 'present'\n", schema_req_py) == {'a': 'present'}

schema_strict_py = {'a': strict('a', 0, 0, int)}
assert taml.loads('a: 1\n', schema_strict_py) == {'a': 1}
assert_raises(StrictError, lambda: taml.loads('a: "1"\n', schema_strict_py))


print('schema_more.py: passed')
