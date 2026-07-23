import contextlib, datetime, operator, unittest
from pathlib import Path

from epicstuff import BoxDict, s, wrap
from parameterized import parameterized
from taml import SchemaDefinitionError, taml
from utils import assert_raises, create_file, recorded_values, recording_converter, reset_recorded_values


def assert_partial(value, func, *args, weaker=False, **kwargs) -> None:
	assert isinstance(value, wrap)
	if weaker:
		assert value.func == func
	else:
		assert value.func is func
	assert value.args == args
	assert value.keywords == kwargs


def assert_definition_error_with_location(src: str, text: str) -> None:
	try:
		taml.loads(src, is_schema=True)
	except SchemaDefinitionError as e:
		message = str(e)
		assert text in message, message
		assert '(line 1, col ' in message, message
	else:
		raise AssertionError('expected SchemaDefinitionError to be raised')


class Main(unittest.TestCase):
	'Test string to python objects.'

	def test_builtins(self) -> None:
		'Verify builtins resolve.'
		schema = taml.loads('a: int', is_schema=True)
		assert schema.a is int
	def test_inline_dict(self) -> None:
		'Verify a callable resolves when nested inside an inline dict.'
		schema = taml.loads('d: {a: int}\n', is_schema=True)
		assert schema.d.a is int
	def test_inline_list(self) -> None:
		'Verify a callable resolves when nested inside an inline list.'
		schema = taml.loads('l: [int]\n', is_schema=True)
		assert schema.l[0] is int

	def test_module(self) -> None:
		'Verify dotted module callables resolve and convert.'
		schema = taml.loads('d: datetime.date.fromisoformat', is_schema=True)
		assert schema.d == datetime.date.fromisoformat
		assert taml.loads("d: '2026-07-22'\n", schema) == {'d': datetime.date(2026, 7, 22)}
	def test_kwarg(self) -> None:
		'Verify keyword arguments work and are used during conversion.'
		schema = taml.loads('b: int(base=16)', is_schema=True)
		assert_partial(schema.b, int, base=16)
		assert taml.loads("b: 'ff'\n", schema) == {'b': 255}
	def test_pos_arg(self) -> None:
		'Verify positional arguments work.'
		schema = taml.loads("file: pathlib.Path('/srv/uploads')\n", is_schema=True)
		assert_partial(schema.file, Path, '/srv/uploads')
		assert taml.loads('file: invoice.pdf\n', schema) == {'file': Path('/srv/uploads/invoice.pdf')}
	def test_commas_inside_quoted_args(self) -> None:
		'Verify commas inside quoted call arguments are not treated as argument separators.'
		schema = taml.loads("x: epicstuff.BoxDict(b='1,2')\n", is_schema=True)
		assert_partial(schema.x, BoxDict, b='1,2')
		assert taml.loads('x: {a: 1}\n', schema) == {'x': {'a': 1, 'b': '1,2'}}
	def test_complex_schema(self) -> None:
		'Verify a complex schema expression with nested dotted references resolves and converts.'
		schema = taml.loads('ts: datetime.datetime.fromtimestamp(tz=datetime.timezone.utc)\n', is_schema=True)
		assert_partial(schema.ts, datetime.datetime.fromtimestamp, tz=datetime.timezone.utc, weaker=True)
		assert taml.loads('ts: 0\n', schema) == {'ts': datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)}
	def test_schema_loading_does_not_execute_converter(self) -> None:
		reset_recorded_values()
		schema = taml.loads('a: utils.recording_converter(marker=1)\n', is_schema=True)
		assert recorded_values == []
		assert taml.loads('a: value\n', schema) == {'a': 'value'}
		assert recorded_values == [('value', 1)]
	@parameterized.expand([
		('attribute', 'a: datetime.timezone.utc\n', 'datetime.timezone.utc'),
		('number', 'a: math.pi\n', 'math.pi'),
	])
	def test_non_callable_resolution(self, _name, schema, text) -> None:
		'Resolved objects that cannot convert data are rejected while defining the schema.'
		assert_definition_error_with_location(schema, text)
	@parameterized.expand([
		('integer', 'a: 1\n'),
		('boolean', 'a: true\n'),
	])
	def test_non_callable_literal_schema(self, _name, schema) -> None:
		'Literal schema values that cannot convert data are rejected with a location.'
		assert_definition_error_with_location(schema, '')

	@parameterized.expand([
		(
			'nonexistent_module',
			'a: some_nonexistent_module.fn',
			"No module named 'some_nonexistent_module' at a (line 1, col 4)",
		),
		(
			'nonexistent_attr',
			'a: os.path.nonexistent_attr',
			"No module named 'os.path.nonexistent_attr'; 'os.path' is not a package at a (line 1, col 4)",
		),
	])
	def test_errors(self, _name, schema, msg) -> None:
		'Verify schema resolution reports missing modules and attributes with source locations.'
		assert_raises(ImportError, lambda: taml.loads(schema, is_schema=True), msg)
	@parameterized.expand([
		('binop', 'a: int(1+2)\n', "Unsupported expression '1+2' at a (line 1, col 8)"),
		('kwarg_unpacking', 'a: int(**foo)\n', 'Keyword argument must be written as name=value at a (line 1, col 8)'),
	])
	def test_definition_errors(self, _name, schema, msg) -> None:
		'Verify unsupported resolver expressions report source locations.'
		assert_raises(SchemaDefinitionError, lambda: taml.loads(schema, is_schema=True), msg)
	@parameterized.expand([
		('lambda', 'a: int(lambda: 1)\n', 'lambda'),
		('conditional', 'a: int(1 if flag else 2)\n', '1 if flag else 2'),
		('subscript', 'a: int(values[0])\n', 'values[0]'),
		('list_comprehension', 'a: int([x for x in values])\n', '[x for x in values]'),
		('starred_arg', 'a: int(*values)\n', '*values'),
	])
	def test_other_unsupported_expressions(self, _name, schema, text) -> None:
		assert_definition_error_with_location(schema, text)
	def test_duplicated_kwargs(self) -> None:
		'Invalid Python syntax in a schema is reported as a located schema definition error.'
		assert_definition_error_with_location('a: int(base=2, base=8)\n', 'keyword argument repeated: base')
	def test_schema_file_error_includes_path(self) -> None:
		with create_file('a: 1\n', 'data.taml') as data_path, create_file('a: int(1+2)\n', 'schema.taml') as schema_path:
			try:
				taml.load(data_path, schema_path)
			except SchemaDefinitionError as e:
				assert str(schema_path) in str(e), str(e)
			else:
				raise AssertionError('expected SchemaDefinitionError to be raised')

	def test_dict_arg(self) -> None:
		'Verify a mapping literal resolves as a positional argument.'
		schema = taml.loads("level: \"operator.getitem({'low': 10, 'high': 50})\"\n", is_schema=True)
		assert_partial(schema.level, operator.getitem, {'low': 10, 'high': 50})
	def test_list_arg(self) -> None:
		schema = taml.loads('d: dict(items=[1, 2])\n', is_schema=True)
		assert_partial(schema.d, dict, items=[1, 2])
	@parameterized.expand([
		('negative_integer', 'x: dict(value=-1)\n', -1),
		('float', 'x: dict(value=1.5)\n', 1.5),
		('true', 'x: dict(value=True)\n', True),
		('false', 'x: dict(value=False)\n', False),
		('none', 'x: dict(value=None)\n', None),
		('tuple', 'x: dict(value=(1, 2))\n', (1, 2)),
		('nested', 'x: "dict(value={\'a\': [1, 2]})"\n', {'a': [1, 2]}),
	])
	def test_literal_arguments(self, _name, src, expected) -> None:
		'Python literals are stored as values rather than resolved as dotted names.'
		schema = taml.loads(src, is_schema=True)
		assert_partial(schema.x, dict, value=expected)
	@unittest.skip('No plans to implemented unless valid use case is identified.')
	def test_nested_call_expressions_inside_args(self) -> None:
		'Verify a call used as a schema argument is evaluated.'
		schema = taml.loads("a: int(base=len('ab'))\n", is_schema=True)
		assert_partial(schema.a, int, base=2)


if __name__ == '__main__':
	with contextlib.suppress(unittest.SkipTest):
		unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')