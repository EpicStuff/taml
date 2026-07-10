import os
import unittest
from pathlib import Path

from epicstuff import s
from taml import taml, RequiredError, StructureError
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaLists(unittest.TestCase):
	def test_list_does_not_append_missing_indices(self):
		'''Verify list does not append missing indices.'''
		schema = taml.loads(
			s('''
				lst:
					- int
					- int
					- str
			'''),
			is_schema=True,
		)

		assert taml.loads("lst: ['1', '2']\n", schema) == {'lst': [1, 2]}  # does not append missing indices

	def test_list_missing_indices_no_error(self):
		'''Verify list missing indices no error.'''
		schema_strict_missing_idx = taml.loads(
			s('''
				lst:
					- int
					- int
					- int
			'''),
			is_schema=True,
		)

		assert taml.loads("lst: ['1', '2']\n", schema_strict_missing_idx) == {'lst': [1, 2]}  # missing indices should not error unless required

	def test_list_required_index(self):
		'''Verify list required index.'''
		schema_required_idx = taml.loads(
			s('''
				lst:
					- int
					- taml.required
			'''),
			is_schema=True,
		)

		assert_raises(RequiredError, lambda: taml.loads("lst: ['1']\n", schema_required_idx), 'lst[1] is required (line 1, col 1)')

	def test_type_mismatch_list_expected_gets_dict(self):
		'''Verify type mismatch list expected gets dict.'''
		schema_list = taml.loads('x: [int]\n', is_schema=True)
		assert_raises(StructureError, lambda: taml.loads('x: {a: 1}\n', schema_list), "Expected list or None, got CommentedMap: {'a': 1} (line 1, col 4)")

	def test_type_mismatch_dict_expected_gets_list(self):
		'''Verify type mismatch dict expected gets list.'''
		schema_dict = taml.loads(
			s('''
				x:
					a: int
			'''),
			is_schema=True,
		)
		assert_raises(StructureError, lambda: taml.loads('x: [1]\n', schema_dict), 'Expected dict or None, got CommentedSeq: [1] (line 1, col 4)')

	def test_type_mismatch_dict_expected_gets_scalar(self):
		'''Verify type mismatch dict expected gets scalar.'''
		schema_dict = taml.loads(
			s('''
				x:
					a: int
			'''),
			is_schema=True,
		)
		assert_raises(StructureError, lambda: taml.loads('x: 1\n', schema_dict), 'Expected dict or None, got int: 1 (line 1, col 4)')


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaLists).debug()
	print('tests passed')
