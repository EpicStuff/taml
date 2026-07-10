
import contextlib
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from epicstuff import NewDict as Dict, open, s
from parameterized import parameterized
from ruamel.yaml import CommentedMap
from taml import taml, TAML

from utils import assert_raises, TEST_TAML


def _load_from_handle():
	with open(TEST_TAML) as f:
		return taml.load(f)


def _load_from_stringio():
	with open(TEST_TAML) as f:
		text = f.read()
	return taml.load(StringIO(text))


class TestMain(unittest.TestCase):

	# --- loads() basic parsing ---

	def test_loads_basic_parsing(self):
		'''Verify loads parses nested TAML into attribute-accessible mappings.'''
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
		assert type(out) is Dict._childclass_cache[CommentedMap]
		assert type(out.a) is Dict._childclass_cache[CommentedMap]
		assert type(out.z.x.y) is Dict._childclass_cache[CommentedMap]
		assert_raises(AttributeError, lambda: out.b)
		assert_raises(AttributeError, lambda: out.a.d)

	def test_loads_empty_document_is_none(self):
		'''Verify empty YAML documents preserve the YAML None root value.'''
		assert taml.loads('') is None

	def test_loads_comments_only_document_is_none(self):
		'''Verify comments-only YAML documents preserve the YAML None root value.'''
		assert taml.loads('# comment\n') is None

	def test_loads_null_root_is_none(self):
		'''Verify an explicit null YAML root remains None.'''
		assert taml.loads('null\n') is None

	def test_loads_tab_indented_mapping(self):
		'''Verify tab-indented mappings are accepted as TAML input.'''
		assert taml.loads('a:\n\tb: 1\n') == {'a': {'b': 1}}

	def test_loads_deep_tab_indentation(self):
		'''Verify multi-level tab indentation, including tabbed lists, normalizes correctly.'''
		assert taml.loads('a:\n\tb:\n\t\tc: 1\n') == {'a': {'b': {'c': 1}}}
		assert taml.loads('a:\n\t- 1\n\t- 2\n') == {'a': [1, 2]}

	# --- load() from path ---

	@parameterized.expand([
		('str_path', lambda: taml.load(str(TEST_TAML))),
		('pathlib_path', lambda: taml.load(TEST_TAML)),
		('file_handle', _load_from_handle),
		('stringio', _load_from_stringio),
	])
	def test_load_sources_match(self, _name, load):
		'''Verify load accepts each supported stream and path source type.'''
		out_file = {'a': {'a': 3, 'b': 956579776, 'c': [1, 2, 3], 'd': [1.12345, 2, {'a': 1}, 4]}}
		assert load() == out_file

	# --- dumps() uses tabs and round-trips ---

	def test_dumps_uses_tabs_and_round_trips(self):
		'''Verify dumps emits tabs for indentation and round-trips through loads.'''
		data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
		dumped = taml.dumps(data)
		assert '\t' in dumped
		assert taml.loads(dumped) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}

	def test_dumps_nested_format(self):
		'''Verify dumps uses the expected exact nested tab-indented layout.'''
		assert taml.dumps({'a': {'b': [1, {'c': 2}]}}) == 'a:\n\tb:\n\t\t- 1\n\t\t- {c: 2}\n'

	def test_dumps_warns_on_changed_indentation(self):
		'''Verify dumps warns when indentation is changed away from the tab-compatible default.'''
		off_indent = TAML()
		off_indent.indent(mapping=2, sequence=2, offset=0)
		buf = StringIO()
		with contextlib.redirect_stdout(buf):
			off_indent.dumps({'a': {'b': 1}})
		assert 'warning' in buf.getvalue().lower()

	# --- dump() writes to path and round-trips ---

	def test_dump_to_path(self):
		'''Verify dump writes to a Path and the result round-trips.'''
		data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
		dumped = taml.dumps(data)

		tmp_path = Path(tempfile.gettempdir()) / 'taml_dump_test.taml'
		taml.dump(data, tmp_path)

		on_disk = tmp_path.read_text()
		assert on_disk == dumped
		assert '\t' in on_disk
		assert taml.load(tmp_path) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}

		tmp_path.unlink(missing_ok=True)

	# dump() also accepts str path
	def test_dump_to_str_path(self):
		'''Verify dump writes to a string path and the result round-trips.'''
		data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}

		tmp_path_str = str(Path(tempfile.gettempdir()) / 'taml_dump_test_str.taml')
		taml.dump(data, tmp_path_str)
		assert taml.load(tmp_path_str) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
		Path(tmp_path_str).unlink(missing_ok=True)

	# dump() to file-like object
	def test_dump_to_stringio(self):
		'''Verify dump writes the same text to a StringIO stream.'''
		data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
		dumped = taml.dumps(data)

		tmp_stringio = StringIO()
		taml.dump(data, tmp_stringio)
		assert tmp_stringio.getvalue() == dumped

	def test_dump_to_file_object(self):
		'''Verify dump writes to an open file object and the result round-trips.'''
		data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}

		tmp_path_fileobj = Path(tempfile.gettempdir()) / 'taml_dump_test_fileobj.taml'
		with open(tmp_path_fileobj, 'w') as f:
			taml.dump(data, f)
		assert taml.load(tmp_path_fileobj) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
		tmp_path_fileobj.unlink(missing_ok=True)

	def test_dump_rejects_unsupported_stream_type(self):
		'''Verify dump raises TypeError when the stream is neither a path nor a file-like object.'''
		assert_raises(TypeError, lambda: taml.dump({'a': 1}, 123))

	# --- load() must raise FileNotFoundError for missing paths, not silently treat str args as YAML/Sequence ---

	@parameterized.expand([
		# raw YAML passed as the stream path
		('yaml_as_stream_path', lambda: taml.load('a: test')),
		# raw YAML passed as the schema path
		('yaml_as_schema_path', lambda: taml.load(TEST_TAML, 'a: int')),
	])
	def test_load_missing_path_raises(self, _name, load):
		'''Verify raw YAML-like strings passed to load are treated as missing paths.'''
		assert_raises(FileNotFoundError, load)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestMain).debug()
	print('tests passed')
