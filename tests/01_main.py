import contextlib, unittest
from collections import UserDict
from io import StringIO
from itertools import product

from epicstuff import s
from parameterized import parameterized
from ruamel.yaml import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString
from taml import TAML, taml
from taml.main import Dict
from utils import assert_raises, create_file


LOAD_SOURCES = ('string', 'stringio', 'str_path', 'path', 'open')
EMPTY_DOCUMENTS = ('', '# comment\n')
DUMP_TARGETS = ('string', 'stringio', 'str_path', 'path', 'open')


def load_text(text: str, source: str):
	if source == 'string':
		return taml.loads(text)
	if source == 'stringio':
		stream = StringIO(text)
		out = taml.load(stream)
		assert not stream.closed
		return out

	with create_file(text) as path:
		if source == 'str_path':
			return taml.load(str(path))
		if source == 'path':
			return taml.load(path)
		with path.open() as file:
			out = taml.load(file)
			assert not file.closed
			return out


def dump_data(data, target: str) -> str:
	if target == 'string':
		return taml.dumps(data)
	if target == 'stringio':
		stream = StringIO()
		taml.dump(data, stream)
		assert not stream.closed
		return stream.getvalue()

	with create_file('') as path:
		if target == 'str_path':
			taml.dump(data, str(path))
		elif target == 'path':
			taml.dump(data, path)
		else:
			with path.open('w') as file:
				taml.dump(data, file)
				assert not file.closed
		return path.read_text()


class Main(unittest.TestCase):
	'Tests core TAML load/dump parsing, path/stream handling, and tab formatting.'

	# basic yaml checks
	def test_yaml_1(self) -> None:
		assert taml.loads('') is None
	def test_yaml_2(self) -> None:
		assert taml.loads('# comment\n') is None
	def test_yaml_3(self) -> None:
		assert taml.loads('null\n') is None
	@parameterized.expand([
		('list', '- a\n', ['a']),
		('scalar', '42\n', 42),
	])
	def test_yaml_non_mapping_root(self, _name, src, parsed) -> None:
		assert taml.loads(src) == parsed
	@parameterized.expand(product(EMPTY_DOCUMENTS, LOAD_SOURCES))
	def test_load_empty_documents(self, src, source) -> None:
		'Every supported text source agrees for documents with no value.'
		assert load_text(src, source) is None

	# basic taml checks
	def test_loads_basic_1(self) -> None:
		'Basic checks 1.'
		yaml_text = s('''
			a:
				b: 1
				c:
					- 2
			z:
				x:
					y: {}
		''')
		out = taml.loads(yaml_text)
		assert out == {'a': {'b': 1, 'c': [2]}, 'z': {'x': {'y':{}}}}
		assert type(out) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.a) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.z.x.y) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert_raises(AttributeError, lambda: out.b)
		assert_raises(AttributeError, lambda: out.a.d)
	def test_loads_basic_2(self) -> None:
		'Basic checks 1.'
		assert taml.loads('a:\n\tb: 1\n') == {'a': {'b': 1}}
		assert taml.loads('a:\n\tb:\n\t\tc: 1\n') == {'a': {'b': {'c': 1}}}
		assert taml.loads('a:\n\t- 1\n\t- 2\n') == {'a': [1, 2]}
	@parameterized.expand([
		('double_quoted', 'a:\n\tb: "first\tsecond"\n'),
		('single_quoted', "a:\n\tb: 'first\tsecond'\n"),
	])
	def test_loads_preserves_inline_tabs(self, _name, src) -> None:
		'Verify indentation normalizes without changing tabs in quoted scalar values.'
		assert taml.loads(src) == {'a': {'b': 'first\tsecond'}}
	def test_loads_preserves_tab_inside_literal_block(self) -> None:
		'Only the first tab on a block scalar line is indentation.'
		assert taml.loads('message: |\n\tfirst\n\t\tsecond\n') == {'message': 'first\n\tsecond\n'}
	def test_loads_folded_block(self) -> None:
		'Folded block scalar lines are joined with spaces.'
		assert taml.loads('message: >\n\tfirst\n\tsecond\n') == {'message': 'first second\n'}
	def test_loads_warns_space_indentation(self) -> None:
		'TAML warns when spaces are used for structural indentation.'
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			assert taml.loads('a:\n b: 1\n') == {'a': {'b': 1}}
		warning = buf.getvalue().lower()
		assert 'warning' in warning
		assert 'space' in warning
	def test_loads_does_not_warn_for_block_scalar_content_spaces(self) -> None:
		'Spaces after structural tab indentation are scalar content, not TAML indentation.'
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			assert taml.loads('message: |\n\tfirst\n\t second\n') == {'message': 'first\n second\n'}
		assert 'warning' not in buf.getvalue().lower()

	# load(s) checks
	@parameterized.expand(product(LOAD_SOURCES))
	def test_load_sources(self, source) -> None:
		'Every supported text source loads a normal document.'
		text = s('''
			a:
				a: 3
				b: 956579776
				c:
					- 1
					- 2
					- 3  # this is a comment
			# this is another comment
				d:
					- 1.12345
					- 2
					- {'a': 1}
					- 4
		''')
		expected = {'a': {'a': 3, 'b': 956579776, 'c': [1, 2, 3], 'd': [1.12345, 2, {'a': 1}, 4]}}
		assert load_text(text, source) == expected
	def test_load_does_not_close_stream(self) -> None:
		stream = StringIO('a: 1\n')
		assert taml.load(stream) == {'a': 1}
		assert not stream.closed
	def test_load_beartype(self) -> None:
		'Verify load raises TypeError when the stream is neither a path nor a file-like object.'
		assert_raises(TypeError, lambda: taml.load(123))
	def test_loads_warns_settings_change(self) -> None:
		'Load is supposed to print warning if taml settings are changed.'
		off_indent = TAML()
		off_indent.indent(mapping=2, sequence=2, offset=0)
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			off_indent.loads('a:\n\tb: 1\n')
		assert 'warning: changing indentation may cause this to not work' in buf.getvalue()
	def test_load_missing_path(self) -> None:
		'load() must raise FileNotFoundError for missing data and schema paths.'
		assert_raises(FileNotFoundError, lambda: taml.load('a: test'))
		with create_file('a: 1\n') as path:
			assert_raises(FileNotFoundError, lambda: taml.load(path, path.with_name('missing-schema.taml')))

	# dump(s)
	@parameterized.expand(product(DUMP_TARGETS))
	def test_dump_targets(self, target) -> None:
		'Every supported dump target produces the same text.'
		data = {'a': {'b': [1, {'c': 2}]}}
		assert dump_data(data, target) == 'a:\n\tb:\n\t\t- 1\n\t\t- c: 2\n'
	@parameterized.expand([
		('null', None),
		('scalar', 42),
		('list', ['a', 2]),
		('empty_dict', {}),
		('empty_list', []),
	])
	def test_dumps_non_mapping_roots_round_trip(self, _name, value) -> None:
		assert taml.loads(taml.dumps(value)) == value
	def test_dumps_preserves_spaces_inside_literal_block(self) -> None:
		value = LiteralScalarString('first\n second\n')
		out = taml.loads(taml.dumps({'message': value}))
		assert out == {'message': 'first\n second\n'}
	def test_dumps_mapping_types(self) -> None:
		'Verify dumps accepts loaded mappings and UserDicts.'
		expected = 'a:\n\tb: 1\n'
		assert taml.dumps(taml.loads('a:\n\tb: 1\n')) == expected
		assert taml.dumps(UserDict(a={'b': 1})) == expected
	def test_dumps_transform(self) -> None:
		'Verify dumps forwards transforms to ruamel.'
		assert taml.dumps({'a': 1}, transform=lambda value: value.replace('a:', 'b:')) == 'b: 1\n'
	def test_dumps_warns_settings_change(self) -> None:
		'Dump is supposed to print warning if taml settings are changed.'
		off_indent = TAML()
		off_indent.indent(mapping=2, sequence=2, offset=0)
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			off_indent.dumps({'a': {'b': 1}})
		assert 'warning: changing indentation may cause this to not work' in buf.getvalue().lower()
	def test_dump_does_not_close_stream(self) -> None:
		stream = StringIO()
		taml.dump({'a': 1}, stream)
		assert stream.getvalue() == 'a: 1\n'
		assert not stream.closed
	def test_dump_beartype(self) -> None:
		'Verify dump raises TypeError when the stream is neither a path nor a file-like object.'
		assert_raises(TypeError, lambda: taml.dump({'a': 1}, 123))


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
