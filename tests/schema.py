import datetime, os
import unittest
from pathlib import Path

from taml import taml, RequiredError
from epicstuff import NewDict as Dict, s  # noqa: F401
from utils import assert_raises


os.chdir(Path(__file__).parent)


schema1 = taml.loads(
	s('''
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
	'''),
	is_schema=True,
)
schema2 = {
	'a': {
		'd': tuple,
	},
}


class TestSchema(unittest.TestCase):

	# checking required works
	def test_required(self):
		'''Verify missing nested required values raise the expected RequiredError.'''
		data = s('''
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
		assert_raises(RequiredError, lambda: taml.loads(data, schema1, schema2), 'a.e.f is required (line 1, col 1)')
		# todo: maybe, the 2, 1 is not ideal, but getting ~15, 2 is to much work for now (where the missing key should go instead of parent key)

	# checking schema works
	def test_schema(self):
		'''Verify the base schema fixture converts and validates a complete document.'''
		data = s('''
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
		''')
		out = taml.loads(data, schema1, schema2)
		assert out == {
			'a': {
				'a': 3,
				'b': datetime.datetime(2000, 4, 24, 12, 36, 16, tzinfo=datetime.timezone.utc),
				'c': (1, 2, 3),
				'd': (1.12, 2, {'a': 1, 'b': '1'}, '4'),
				'e': {'f': 'required value'},
				},
			}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchema).debug()
	print('tests passed')
