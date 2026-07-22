import contextlib, tempfile, unittest
from collections import UserDict
from io import StringIO
from pathlib import Path

from epicstuff import open, s
from parameterized import parameterized
from ruamel.yaml import CommentedMap
from taml import TAML, taml
from taml.main import Dict
from utils import test_taml_path, assert_raises


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
		assert out == {'a': {'b': 1, 'c': [2]}, 'z': {'x': {'y':{}}}}
		# make sure conversion is working
		assert type(out) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.a) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		assert type(out.z.x.y) is Dict._childclass_cache[CommentedMap]  # pylint=disable: unidiomatic-typecheck
		# make sure no create i guess
		assert_raises(AttributeError, lambda: out.b)
		assert_raises(AttributeError, lambda: out.a.d)
	def test_loads_basic_2(self) -> None:
		'Basic checks 1.'
		assert taml.loads('a:\n\tb: 1\n') == {'a': {'b': 1}}
		assert taml.loads('a:\n\tb:\n\t\tc: 1\n') == {'a': {'b': {'c': 1}}}
		assert taml.loads('a:\n\t- 1\n\t- 2\n') == {'a': [1, 2]}
	def test_loads_preserves_literal_tabs(self) -> None:
		'Verify indentation normalizes without changing tabs in scalar values.'
		assert taml.loads('a:\n\tb: "first\tsecond"\n') == {'a': {'b': 'first\tsecond'}}

	# load(s) checks
	@parameterized.expand([
		('str', lambda: taml.load(str(test_taml_path))),
		('path', lambda: taml.load(test_taml_path)),
		('open', None),
		('stringio', None),
	])
	def test_load_sources(self, name, load) -> None:
		'Make sure each source type works.'
		if name == 'open':
			def load():
				with open(test_taml_path) as f:
					return taml.load(f)
		elif name == 'stringio':
			def load():
				with open(test_taml_path) as f:
					text = f.read()
				return taml.load(StringIO(text))

		assert load() == {'a': {'a': 3, 'b': 956579776, 'c': [1, 2, 3], 'd': [1.12345, 2, {'a': 1}, 4]}}
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
	@parameterized.expand([
		# raw YAML passed as the stream path
		('stream_path', lambda: taml.load('a: test')),
		# raw YAML passed as the schema path
		('schema_path', lambda: taml.load(test_taml_path, 'a: int')),
	])
	def test_load_missing_path(self, _name, load) -> None:
		'load() must raise FileNotFoundError for missing paths.'
		assert_raises(FileNotFoundError, load)

	# dump(s)
	def test_dumps(self) -> None:
		'Make sure dumps work.'
		assert taml.dumps({'a': {'b': [1, {'c': 2}]}}) == 'a:\n\tb:\n\t\t- 1\n\t\t- c: 2\n'
	def test_dumps_mapping_types(self) -> None:
		'Verify dumps accepts loaded mappings and UserDicts.'
		expected = 'a:\n\tb: 1\n'
		assert taml.dumps(taml.loads('a:\n\tb: 1\n')) == expected  # make sure works with newdict
		assert taml.dumps(UserDict(a={'b': 1})) == expected # make sure works with userdict
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
	@parameterized.expand([
		('str', lambda path: str(path)),
		('path', lambda path: Path(path)),
		('open', lambda path: open(path, 'w')),
		('stringio', lambda _: StringIO()),
	])
	def test_dump_targets(self, name, target) -> None:
		'Make sure each dump target type works.'
		data = {'a': {'b': [1, {'c': 2}]}}

		with tempfile.TemporaryDirectory() as tmp_dir:
			file = target(Path(tmp_dir) / 'tmp.taml')
			taml.dump(data, file)

			if name == 'open':
				file.close()
			if name == 'stringio':
				out = file.getvalue()
			else:
				with open(Path(tmp_dir) / 'tmp.taml') as f:
					out = f.read()

		assert out == 'a:\n\tb:\n\t\t- 1\n\t\t- c: 2\n'
	def test_dump_beartype(self) -> None:
		'Verify dump raises TypeError when the stream is neither a path nor a file-like object.'
		assert_raises(TypeError, lambda: taml.dump({'a': 1}, 123))


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
