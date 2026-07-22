import unittest

from taml import SchemaDefinitionError, StrictError, strict, taml
from utils import assert_equals, assert_raises, assert_raises2


class TestSchemaStrict(unittest.TestCase):
	'Testing the taml.strict object.'

	def test_basic(self) -> None:
		'Basic test with int.'
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: 1',
			{'a': 1},
		)
	def test_preserves_null(self) -> None:
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: null',
			{'a': None},
		)
	def test_allows_missing_key(self) -> None:
		assert_equals(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'{}',
			{},
		)
	def test_rejects_wrong_type(self) -> None:
		'Reject a wrong type instead of converting.'
		assert_raises2(
			'a: taml.strict(int)',
			{'a': strict(int)},
			'a: "1"',
			StrictError,
			"Expected (int), got '1' (line 1, col 4)",
		)
	def test_multiple_types_accepts(self) -> None:
		'Test multiple types work.'
		assert_equals(
			'a: taml.strict(int, str)',
			{'a': strict(int, str)},
			'a: 1',
			{'a': 1},
		)
	def test_multiple_types_rejects(self) -> None:
		'Test multiple types raises properly.'
		assert_raises2(
			'a: taml.strict(int, float)',
			{'a': strict(int, float)},
			'a: "1"',
			StrictError,
			"Expected (int | float), got '1' (line 1, col 4)",
		)
	def test_missing_func(self) -> None:
		'Strict with no type argument raises definition error.'
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict', is_schema=True),
			'Missing arguments for strict at a (line 1, col 4)',
		)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads('a: taml.strict()', is_schema=True),
			'Missing arguments for strict at a (line 1, col 4)',
		)
		assert_raises(
			TypeError,
			strict,
		)


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaStrict).debug()
	print('tests passed')
