import os, unittest
from pathlib import Path

from taml import ConversionValueError, SchemaDefinitionError, always, taml
from utils import assert_equals, assert_raises, assert_raises2

os.chdir(Path(__file__).parent)


class Main(unittest.TestCase):
	def test_works_on_value(self) -> None:
		'Make sure func gets run when theres value.'
		# plain callable skips null; always makes the converter run on it
		assert_equals('a: taml.always(int)', {'a': always(int)}, 'a: "1"', {'a': 1})
	def test_runs_on_null(self) -> None:
		'Make sure func gets run on null.'
		# plain callable skips null; always makes the converter run on it
		assert_equals('a: taml.always(bool)', {'a': always(func=bool)}, 'a: null', {'a': False})
	def test_raises(self) -> None:
		'Make sure proper error is raised.'
		# always wraps a value-error from the converter, pointing at the value
		assert_raises2('a: taml.always(int)', {'a': always(int)}, "a: 'nope'", ConversionValueError, "Cannot convert 'nope' to int (line 1, col 4)")
	def test_does_not_insert_missing_key(self) -> None:
		'Verify always does not insert a missing key.'
		assert_equals('a: taml.always(int)', {'a': always(int)}, '{}', {})
	def test_missing_func(self) -> None:
		'Bare always with no func raises definition error.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.always', is_schema=True),
			'Missing arguments for always at a (line 1, col 4)',
		)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.always()', is_schema=True),
			'Missing arguments for always at a (line 1, col 4)',
		)
		assert_raises(
			TypeError,
			always,
			'tmp'
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(Main).debug()
	print('tests passed')
