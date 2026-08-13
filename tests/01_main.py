# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# ruff: noqa: ANN001

import contextlib, unittest
from collections import UserDict
from io import StringIO
from itertools import product
from typing import Literal

from epicstuff import run_fix_import, s  # noqa: F401
from parameterized import parameterized
from ruamel.yaml import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString
from taml import TAML, taml
from taml.main import Dict

from .utils import assert_raises, create_file, skip


type source_types = Literal['string', 'stringio', 'str', 'path', 'open']
sources = ('string', 'stringio', 'str', 'path', 'open')

def load_text(text: str, source: source_types) -> Dict:
	if source == 'string':
		return taml.loads(text)
	if source == 'stringio':
		stream = StringIO(text)
		out = taml.load(stream)
		assert not stream.closed, 'taml should not close not it opened streams'
		return out
	# else
	with create_file(text) as path:
		if source == 'str':
			return taml.load(str(path))
		if source == 'path':
			return taml.load(path)
		# if open
		with path.open() as file:
			out = taml.load(file)
			assert not file.closed, 'taml should not close not it opened streams'
			return out
def dump_data(data: Dict, target: source_types) -> str:
	if target == 'string':
		return taml.dumps(data)
	if target == 'stringio':
		stream = StringIO()
		taml.dump(data, stream)
		assert not stream.closed
		return stream.getvalue()
	# else
	with create_file('') as path:
		if target == 'str':
			taml.dump(data, str(path))
		elif target == 'path':
			taml.dump(data, path)
		else:  # if open
			with path.open('w') as file:
				taml.dump(data, file)
				assert not file.closed, 'taml should not close not it opened streams'
		return path.read_text()


class Main(unittest.TestCase):
	'Tests core TAML load/dump parsing, path/stream handling, and tab formatting.'

	# basic yaml checks
	@parameterized.expand([
		('null', None, 'null\n...\n'),
		('scalar', 42, '42\n...\n'),
		('list', ['a', 2], '\t- a\n\t- 2\n'),
		('empty_dict', {}, '{}\n'),
		('empty_list', [], '[]\n'),
	])
	def test_non_mapping_roots(self, _name, value, dumped) -> None:
		self.assertEqual(taml.dumps(value), dumped)
		self.assertEqual(taml.loads(dumped), value)
	@parameterized.expand(product(('# comment', 'null'), sources))
	def test_extra_non_mapping_roots(self, src, source) -> None:
		'Every supported text source agrees for documents that parse as None.'
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
		# make sure data is correct
		self.assertEqual(out, {'a': {'b': 1, 'c': [2]}, 'z': {'x': {'y':{}}}})
		# make sure conversion is working
		assert type(out) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.a) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.z.x.y) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		# make sure no create i guess
		assert_raises(AttributeError, lambda: out.b)
		assert_raises(AttributeError, lambda: out.a.d)

	# load(s) checks
	@parameterized.expand(product(sources))
	def test_load_sources(self, source) -> None:
		'Every supported text source loads a normal document.'
		text = s('''
			a:
			# this is another comment
				c:
					- {'a': 1}
					- 3  # this is a comment
		''')
		self.assertEqual(load_text(text, source), {'a': {'c': [{'a': 1}, 3]}})
	@parameterized.expand([
		('double_quoted', 'a:\n\tb: "first\tsecond"'),
		('single_quoted', "a:\n\tb: 'first\tsecond'"),
	])
	def test_loads_preserves_inline_tabs(self, _name, src) -> None:
		'Verify indentation normalizes without changing tabs in quoted scalar values.'
		self.assertEqual(taml.loads(src), {'a': {'b': 'first\tsecond'}})
	@skip('I cant be bothered to implement this')
	def test_loads_preserves_tab_inside_literal_block(self) -> None:
		'Only the first tab on a block scalar line is indentation.'
		self.assertEqual(taml.loads('message: |\n\tfirst\n\t\tsecond'), {'message': 'first\n\tsecond'})
	def test_loads_folded_block(self) -> None:
		'Folded block scalar lines are joined with spaces.'
		self.assertEqual(taml.loads('message: >\n\tfirst\n\tsecond'), {'message': 'first second'})
	def test_loads_warns_space_indentation(self) -> None:
		'TAML warns when spaces are used for structural indentation.'
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			self.assertEqual(taml.loads('a:\n\t b: 1'), {'a': {'b': 1}})
		assert 'warning: you have mixed indentation' in buf.getvalue()
	@skip('Cant be bothered to support block scalar at the moment')
	def test_loads_does_not_warn_for_block_scalar_content_spaces(self) -> None:
		'Spaces after structural tab indentation are scalar content, not TAML indentation.'
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			self.assertEqual(taml.loads('message: |\n\tfirst\n\t second'), {'message': 'first\n second'})
		assert 'warning' not in buf.getvalue()
	def test_load_beartype(self) -> None:
		'Verify load raises TypeError when the stream is neither a path nor a file-like object.'
		assert_raises(TypeError, lambda: taml.load(123))
	def test_loads_warns_settings_change(self) -> None:
		'Load is supposed to print warning if taml settings are changed.'
		off_indent = TAML()
		off_indent.indent(mapping=2, sequence=2, offset=0)
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			off_indent.loads('a:\n\tb: 1')
		assert 'warning: changing indentation may cause this to not work' in buf.getvalue()
	def test_load_missing_path(self) -> None:
		'load() must raise FileNotFoundError for missing data and schema paths.'
		assert_raises(FileNotFoundError, lambda: taml.load('a: test'))

	# dump(s)
	@parameterized.expand(product(sources))
	def test_dump_targets(self, target) -> None:
		'Every supported dump target produces the same text.'
		data = {'a': {'b': [1, {'c': 2}]}}
		self.assertEqual(dump_data(data, target), 'a:\n\tb:\n\t\t- 1\n\t\t- c: 2\n')
	def test_dumps_preserves_spaces_inside_literal_block(self) -> None:
		value = LiteralScalarString('first\n second\n')
		out = taml.loads(taml.dumps({'message': value}))
		self.assertEqual(out, {'message': 'first\n second\n'})
	def test_dumps_mapping_types(self) -> None:
		'Verify dumps accepts loaded mappings and UserDicts.'
		expected = 'a:\n\tb: 1\n'
		self.assertEqual(taml.dumps(taml.loads('a:\n\tb: 1\n')), expected)
		self.assertEqual(taml.dumps(UserDict(a={'b': 1})), expected)
	def test_dumps_transform(self) -> None:
		'Verify dumps forwards transforms to ruamel.'
		self.assertEqual(taml.dumps({'a': 1}, transform=lambda value: value.replace('a:', 'b:')), 'b: 1\n')
	def test_dumps_warns_settings_change(self) -> None:
		'Dump is supposed to print warning if taml settings are changed.'
		off_indent = TAML()
		off_indent.indent(mapping=2, sequence=2, offset=0)
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			off_indent.dumps({'a': {'b': 1}})
		assert 'warning: changing indentation may cause this to not work' in buf.getvalue().lower()
	def test_dump_beartype(self) -> None:
		'Verify dump raises TypeError when the stream is neither a path nor a file-like object.'
		assert_raises(TypeError, lambda: taml.dump({'a': 1}, 123))


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
