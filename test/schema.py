import datetime, os
from pathlib import Path

from taml import taml
from taml.schema import tmp_error
from epicstuff import Dict, run_install_trace, s


os.chdir(Path(__file__).parent)


schema1 = taml.loads('''
a:
	b: datetime.datetime.fromtimestamp(tz=datetime.timezone.utc)
	c: tuple
	d:
		- round(ndigits=2)
		- null
		- epicstuff.Dict(b='1') # make sure b stays str during resolve
		- str
	e:
		f: taml.required
''', is_schema=True)
schema2 = {
	'a': {
		'd': tuple,
	},
}
data = '''
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
'''


try:
	out = taml.loads(data, schema1, schema2)
except tmp_error as e:
	assert str(e) == 'tmp, value is required'

data = '''
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
	e:
		f: 'required value'
'''

out = taml.loads(data, schema1, schema2)
assert out == Dict({
	'a': Dict({'a': 3,
		'b': datetime.datetime(2000, 4, 24, 12, 36, 16, tzinfo=datetime.timezone.utc),
		'c': (1, 2, 3),
		'd': (1.12, 2, Dict({'a': 1, 'b': '1'}), '4'),
		'e': Dict({'f': 'required value'}),
		}),
	})

print(out)