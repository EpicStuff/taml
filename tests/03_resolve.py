import datetime, operator, os, unittest, contextlib
from pathlib import Path

from epicstuff import s, wrap, BoxDict
from parameterized import parameterized
from taml import SchemaDefinitionError, taml
from utils import assert_raises


def assert_partial(value, func, *args, weaker=False, **kwargs) -> None:
	assert isinstance(value, wrap)
	if weaker:
		assert value.func == func
	else:
		assert value.func is func
	assert value.args == args
	assert value.keywords == kwargs


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
		'Verify dotted module callables resolve.'
		schema = taml.loads('d: datetime.date.fromisoformat', is_schema=True)
		assert schema.d == datetime.date.fromisoformat
	def test_kwarg(self) -> None:
		'Verify keyword arguments work.'
		schema = taml.loads('b: int(base=16)', is_schema=True)
		assert_partial(schema.b, int, base=16)
	def test_pos_arg(self) -> None:
		'Verify positional arguments work.'
		schema = taml.loads("file: pathlib.Path('/srv/uploads')\n", is_schema=True)
		assert_partial(schema.file, Path, '/srv/uploads')
		assert taml.loads('file: invoice.pdf\n', schema) == {'file': Path('/srv/uploads/invoice.pdf')}
	def test_commas_inside_quoted_args(self) -> None:
		'Verify commas inside quoted call arguments are not treated as argument separators.'
		schema = taml.loads("x: epicstuff.BoxDict(b='1,2')\n", is_schema=True)
		assert_partial(schema.x, BoxDict, b='1,2')
	def test_complex_schema(self) -> None:
		'Verify a complex schema expression with nested dotted references resolves.'
		schema = taml.loads('ts: datetime.datetime.fromtimestamp(tz=datetime.timezone.utc)\n', is_schema=True)
		assert_partial(schema.ts, datetime.datetime.fromtimestamp, tz=datetime.timezone.utc, weaker=True)

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
	def test_duplicated_kwargs(self) -> None:
		'Verify duplicate keyword arguments are rejected.'
		assert_raises(SyntaxError, lambda: taml.loads('a: int(base=2, base=8)\n', is_schema=True), 'keyword argument repeated: base')

	def test_dict_arg(self) -> None:
		'Verify a mapping literal resolves as a positional argument.'
		schema = taml.loads("level: \"operator.getitem({'low': 10, 'high': 50})\"\n", is_schema=True)
		assert_partial(schema.level, operator.getitem, {'low': 10, 'high': 50})
	def test_list_arg(self) -> None:
		schema = taml.loads('d: dict(items=[1, 2])\n', is_schema=True)
		assert_partial(schema.d, dict, items=[1, 2])
	@unittest.skip('No plans to implemented unless valid use case is identified.')
	def test_nested_call_expressions_inside_args(self) -> None:
		'Verify a call used as a schema argument is evaluated.'
		schema = taml.loads("a: int(base=len('ab'))\n", is_schema=True)
		assert_partial(schema.a, int, base=2)


if __name__ == '__main__':
	with contextlib.suppress(unittest.SkipTest):
		unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
