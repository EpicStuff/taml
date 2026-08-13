# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001, ANN002

import datetime, operator, unittest
from pathlib import Path

from epicstuff import BoxDict, run_fix_import, wrap  # noqa: F401
from parameterized import parameterized
from taml import SchemaDefinitionError, taml

from .utils import assert_raises, recorded_values, skip


def assert_partial(partial, func, *args, weaker=False, **kwargs) -> None:
	assert isinstance(partial, wrap)
	if weaker:
		assert partial.func == func
	else:
		assert partial.func is func
	assert partial.args == args
	assert partial.keywords == kwargs


class Main(unittest.TestCase):
	'Test string to python objects.'

	def test_builtins(self) -> None:
		'Verify builtins resolve.'
		schema = taml.loads('a: int', is_schema=True)
		assert schema.a is int

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
		schema = taml.loads("file: pathlib.Path('/srv/uploads')", is_schema=True)
		assert_partial(schema.file, Path, '/srv/uploads')
		assert taml.loads('file: invoice.pdf', schema) == {'file': Path('/srv/uploads/invoice.pdf')}
	def test_commas_inside_quoted_args(self) -> None:
		'Verify commas inside quoted call arguments are not treated as argument separators.'
		schema = taml.loads("x: epicstuff.BoxDict(b='1,2')", is_schema=True)
		assert_partial(schema.x, BoxDict, b='1,2')
	def test_complex_schema(self) -> None:
		'Verify a complex schema expression with nested dotted references resolves.'
		schema = taml.loads('ts: datetime.datetime.fromtimestamp(tz=datetime.timezone.utc)', is_schema=True)
		assert_partial(schema.ts, datetime.datetime.fromtimestamp, tz=datetime.UTC, weaker=True)
	@parameterized.expand(('a: utils.record_value', 'a: utils.record_value()', 'a: utils.record_value(a=1)'))
	def test_schema_loading_does_not_execute_converter(self, sch) -> None:
		recorded_values.clear()
		taml.loads(sch, is_schema=True)
		assert recorded_values == []
	@parameterized.expand([
		('attribute', 'a: datetime.UTC', 'datetime.UTC'),
		('number', 'a: math.pi', 'math.pi'),
		('integer', 'a: 1', '1'),
		('boolean', 'a: true', 'True'),
	])
	def test_non_callable_resolution(self, _name, sch, msg) -> None:
		'Resolved objects that cannot convert data are rejected while defining the schema.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(sch, is_schema=True),
			msg + ' at a is not callable (line 1, col 4)',
		)

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
		('binop', 'a: int(1+2)', "Unsupported expression '1+2' at a (line 1, col 8)"),
		('kwarg_unpacking', 'a: int(**foo)', 'Keyword argument must be written as name=value at a (line 1, col 8)'),
	])
	def test_definition_errors(self, _name, schema, msg) -> None:
		'Verify unsupported resolver expressions report source locations.'
		assert_raises(SchemaDefinitionError, lambda: taml.loads(schema, is_schema=True), msg)
	@parameterized.expand([
		('lambda', 'a: int(lambda: 1)', 'mapping values are not allowed here\n  in "<file>", line 1, column 14'),
		('conditional', 'a: int(1 if flag else 2)', "Unsupported expression '1 if flag else 2' at a (line 1, col 8)"),
		('subscript', 'a: int(values[0])', "Unsupported expression 'values[0]' at a (line 1, col 8)"),
		('list_comprehension', 'a: int([x for x in values])', "Unsupported expression '[x for x in values]' at a (line 1, col 8)"),
		('starred_arg', 'a: int(*values)', "Unsupported expression '*values' at a (line 1, col 8)"),
	])
	def test_other_unsupported_expressions(self, _name, schema, msg) -> None:
		assert_raises(
			Exception,
			lambda: taml.loads(schema, is_schema=True),
			msg,
		)
	def test_duplicated_kwargs(self) -> None:
		'Verify duplicate keyword arguments are rejected.'
		assert_raises(SyntaxError, lambda: taml.loads('a: int(base=2, base=8)', is_schema=True), 'keyword argument repeated: base')
	# def test_schema_file_error_includes_path(self) -> None:
	# 	with create_file('a: 1', 'data.taml') as data_path, create_file('a: int(1+2)', 'schema.taml') as schema_path:
	# 		assert_raises(
	# 			SchemaDefinitionError,
	# 			taml.load(data_path, schema_path),
	# 			'tmp',
	# 		)
	def test_dict_arg(self) -> None:
		'Verify a mapping literal resolves as a positional argument.'
		schema = taml.loads("level: \"operator.getitem({'low': 10, 'high': 50})\"", is_schema=True)
		assert_partial(schema.level, operator.getitem, {'low': 10, 'high': 50})
	def test_list_arg(self) -> None:
		schema = taml.loads('d: dict(items=[1, 2])', is_schema=True)
		assert_partial(schema.d, dict, items=[1, 2])
	@parameterized.expand([
		('negative_integer', 'x: dict(value=-1)', -1),
		('float', 'x: dict(value=1.5)', 1.5),
		('true', 'x: dict(value=True)', True),
		('false', 'x: dict(value=False)', False),
		('none', 'x: dict(value=None)', None),
		('tuple', 'x: dict(value=(1, 2))', (1, 2)),
		('nested', 'x: "dict(value={\'a\': [1, 2]})"', {'a': [1, 2]}),
	])
	def test_literal_arguments(self, _name, src, expected) -> None:
		'Python literals are stored as values rather than resolved as dotted names.'
		schema = taml.loads(src, is_schema=True)
		assert_partial(schema.x, dict, value=expected)
	@skip('No plans to implemented unless valid use case is identified.')
	def test_nested_call_expressions_inside_args(self) -> None:
		'Verify a call used as a schema argument is evaluated.'
		schema = taml.loads("a: int(base=len('ab'))", is_schema=True)
		assert_partial(schema.a, int, base=2)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
