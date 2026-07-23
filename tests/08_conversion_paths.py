import unittest

from epicstuff import s
from taml import ConversionValueError, taml


def assert_conversion_path(schema: str, data: str, path: str) -> None:
	parsed = taml.loads(schema, is_schema=True)
	try:
		taml.loads(data, parsed)
	except ConversionValueError as e:
		message = str(e)
		assert path in message, message
		assert '(line ' in message and ', col ' in message, message
	else:
		raise AssertionError('expected ConversionValueError to be raised')


class Main(unittest.TestCase):
	'Test logical paths on conversion failures.'

	def test_repeat_list_conversion_path(self) -> None:
		'A repeated list conversion failure reports the actual item index.'
		assert_conversion_path(
			'items: taml.repeat(int)\n',
			"items: ['1', '2', bad]\n",
			'items[2]',
		)
	def test_repeat_dictionary_conversion_path(self) -> None:
		'A conversion failure inside dictionary repeat reports the selected data key.'
		assert_conversion_path(
			s('''
				cfg:
					taml.repeat():
						port: int
			'''),
			s('''
				cfg:
					primary:
						port: '8080'
					backup:
						port: bad
			'''),
			'cfg.backup.port',
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')