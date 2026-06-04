
import os
import tempfile
from io import StringIO
from pathlib import Path

from epicstuff import Dict, JDict, run_install_trace  # noqa: F401
from taml import taml

from utils import assert_raises


os.chdir(Path(__file__).parent)


# --- loads() basic parsing ---

yaml_text = '''
a:
	b: 1
	c:
		- 2
z:
	x:
		y: {}
'''
out = taml.loads(yaml_text)
assert out == {'a': {'b': 1, 'c': [2]}, 'z': {'x': {'y':{}}}}
assert type(out) in (Dict, JDict)
assert type(out.a) in (Dict, JDict)
assert type(out.z.x.y) in (Dict, JDict)
assert_raises(AttributeError, lambda: out.b)
assert_raises(AttributeError, lambda: out.a.d)


# --- load() from path ---

out_file = taml.load('test.taml')
assert out_file == {'a': {'a': 3, 'b': 956579776, 'c': [1, 2, 3], 'd': [1.12345, 2, {'a': 1}, 4]}}

out_file_path = taml.load(Path('test.taml'))
assert out_file_path == out_file

with open('test.taml') as f:
	out_file_handle = taml.load(f)
assert out_file_handle == out_file

with open('test.taml') as f:
	out_file_text = f.read()
out_file_stringio = taml.load(StringIO(out_file_text))
assert out_file_stringio == out_file


# --- dumps() uses tabs and round-trips ---

data = {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
dumped = taml.dumps(data)
assert '\t' in dumped
assert taml.loads(dumped) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}


# --- dump() writes to path and round-trips ---

tmp_path = Path(tempfile.gettempdir()) / 'taml_dump_test.taml'
taml.dump(data, tmp_path)

on_disk = tmp_path.read_text()
assert on_disk == dumped
assert '\t' in on_disk
assert taml.load(tmp_path) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}

# dump() also accepts str path
tmp_path_str = str(Path(tempfile.gettempdir()) / 'taml_dump_test_str.taml')
taml.dump(data, tmp_path_str)
assert taml.load(tmp_path_str) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
Path(tmp_path_str).unlink(missing_ok=True)

# dump() to file-like object
tmp_stringio = StringIO()
taml.dump(data, tmp_stringio)
assert tmp_stringio.getvalue() == dumped

tmp_path_fileobj = Path(tempfile.gettempdir()) / 'taml_dump_test_fileobj.taml'
with open(tmp_path_fileobj, 'w') as f:
	taml.dump(data, f)
assert taml.load(tmp_path_fileobj) == {'a': {'b': [1, 2, 3], 'c': {'d': 4}}}
tmp_path_fileobj.unlink(missing_ok=True)

tmp_path.unlink(missing_ok=True)


# --- load() must raise FileNotFoundError for missing paths, not silently treat str args as YAML/Sequence ---

# raw YAML passed as the stream path
assert_raises(FileNotFoundError, lambda: taml.load('a: test'))

# raw YAML passed as the schema path
assert_raises(FileNotFoundError, lambda: taml.load('test.taml', 'a: int'))


print('main.py: passed')