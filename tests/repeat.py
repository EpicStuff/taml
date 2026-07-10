import os
import unittest
from pathlib import Path

from epicstuff import s
from taml import taml, RequiredError, SchemaDefinitionError
from utils import assert_raises


os.chdir(Path(__file__).parent)


class TestSchemaRepeat(unittest.TestCase):
	def test_repeat_missing_required_key_reports_data_key(self):
		'''Verify repeat missing required key reports data key.'''
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)

		# 'd' is missing required key 'a', so the error path should include the actual data key
		data = s('''
			a:
				b:
					a: test1
					b: 1
				c:
					a: test2
				d:
					b: 3
		''')
		assert_raises(RequiredError, lambda: taml.loads(data, schema), 'a.d.a is required (line 7, col 2)')

	def test_repeat_all_entries_satisfy_schema(self):
		'''Verify repeat all entries satisfy schema.'''
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)

		# all entries satisfy the repeat schema -> int coercion runs per entry
		out = taml.loads(
			s('''
				a:
					b:
						a: test1
						b: 1
					c:
						a: test2
						b: '2'
					d:
						a: test3
						b: '3'
			'''),
			schema,
		)
		assert out == {'a': {
			'b': {'a': 'test1', 'b': 1},
			'c': {'a': 'test2', 'b': 2},
			'd': {'a': 'test3', 'b': 3},
		}}

	def test_repeat_static_key_alongside_repeat(self):
		'''Verify repeat static key alongside repeat.'''
		# static key alongside taml.repeat(): static wins, repeat covers the rest
		schema = taml.loads(
			s('''
				cfg:
					name: taml.required
					taml.repeat():
						port: int
			'''),
			is_schema=True,
		)
		out = taml.loads(
			s('''
				cfg:
					name: my-service
					primary:
						port: '8080'
					backup:
						port: '8081'
			'''),
			schema,
		)
		assert out == {'cfg': {
			'name': 'my-service',
			'primary': {'port': 8080},
			'backup': {'port': 8081},
		}}

	def test_repeat_int_list_any_length(self):
		'''Verify repeat int list any length.'''
		# taml.repeat(int): list of ints, any length
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads("items: ['1', '2', '3', '4']\n", schema) == {'items': [1, 2, 3, 4]}

	def test_repeat_int_list_empty(self):
		'''Verify repeat int list empty.'''
		# taml.repeat(int): list of ints, any length
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads('items: []\n', schema) == {'items': []}

	def test_repeat_list_static_prefix(self):
		'''Verify repeat list static prefix.'''
		# list with static prefix followed by taml.repeat
		schema = taml.loads(
			s('''
				items:
					- str
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads("items: ['hello', '1', '2', '3']\n", schema) == {'items': ['hello', 1, 2, 3]}

	def test_repeat_list_required(self):
		'''Verify repeat list required.'''
		# list repeat with required: each repeated item must be non-null
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(taml.required(int))
			'''),
			is_schema=True,
		)
		try:
			taml.loads("items: ['1', null, '3']\n", schema)
		except RequiredError as e:
			assert str(e) == 'items[1] is required (line 1, col 14)', str(e)

	def test_repeat_key_cannot_take_schema_argument(self):
		'''Verify repeat key cannot take schema argument.'''
		# taml.repeat as a key cannot take a schema argument (positional)
		# but always=False is allowed as a kwarg
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(
				s('''
					a:
						taml.repeat(int):
							x: taml.required
				'''),
				is_schema=True,
			),
			'taml.repeat used as a key cannot take a schema argument at a[*] (line 2, col 2)',
		)

	def test_repeat_bare_value_list_of_anything(self):
		'''Verify repeat bare value list of anything.'''
		# bare taml.repeat (no schema arg) as a value means "list of anything"; null coerces to []
		schema = taml.loads('items: taml.repeat()\n', is_schema=True)
		assert taml.loads('items:\n', schema) == {'items': []}
		assert taml.loads("items: [1, 'a', null]\n", schema) == {'items': [1, 'a', None]}

	def test_repeat_bare_as_list_element(self):
		'''Verify repeat bare as list element.'''
		# same when used as a list element
		schema = taml.loads(
			s('''
				items:
					- taml.repeat
			'''),
			is_schema=True,
		)
		assert taml.loads('items:\n', schema) == {'items': []}
		assert taml.loads("items: [1, 'a']\n", schema) == {'items': [1, 'a']}

	def test_repeat_bare_key_requires_nested_schema(self):
		'''Verify repeat bare key requires nested schema.'''
		# taml.repeat as a key requires a nested schema (not null/empty value)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(
				s('''
					a:
						taml.repeat:
				'''),
				is_schema=True,
			),
			'taml.repeat used as a key requires a nested schema at a[*] (line 2, col 2)',
		)

	def test_repeat_call_key_requires_nested_schema(self):
		'''Verify repeat call key requires nested schema.'''
		# taml.repeat as a key requires a nested schema (not null/empty value)
		assert_raises(
			SchemaDefinitionError,
			lambda: taml.loads(
				s('''
					a:
						taml.repeat(): null
				'''),
				is_schema=True,
			),
			'taml.repeat used as a key requires a nested schema at a[*] (line 2, col 2)',
		)

	def test_repeat_bare_key_no_parens_reports_missing_required(self):
		'''Verify repeat bare key without parentheses reports missing required.'''
		# bare taml.repeat (no parens) as a key works like taml.repeat()
		schema = taml.loads(
			s('''
				a:
					taml.repeat:
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		assert_raises(
			RequiredError,
			lambda: taml.loads('a:\n\tb:\n\t\tc: x\n', schema),
			'a.b.a is required (line 2, col 2)',
		)

	def test_repeat_bare_key_no_parens_accepts_matching_entry(self):
		'''Verify repeat bare key without parentheses accepts matching entry.'''
		# bare taml.repeat (no parens) as a key works like taml.repeat()
		schema = taml.loads(
			s('''
				a:
					taml.repeat:
						a: taml.required
						b: int
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n\tb:\n\t\ta: ok\n\t\tb: 1\n', schema) == {'a': {'b': {'a': 'ok', 'b': 1}}}

	def test_repeat_key_coerce_default_null_to_empty(self):
		'''Verify repeat key default coerce null to empty.'''
		# default coerce=True turns null data into the empty collection for repeat-bearing schemas
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n', schema) == {'a': {}}

	def test_repeat_key_coerce_default_empty_dict(self):
		'''Verify repeat key default coerce empty dict.'''
		# default coerce=True turns null data into the empty collection for repeat-bearing schemas
		schema = taml.loads(
			s('''
				a:
					taml.repeat():
						a: taml.required
			'''),
			is_schema=True,
		)
		assert taml.loads('a: {}\n', schema) == {'a': {}}

	def test_repeat_key_coerce_false_preserves_null(self):
		'''Verify repeat key coerce=False preserves null.'''
		# coerce=False on the dict key repeat preserves null
		schema = taml.loads(
			s('''
				a:
					taml.repeat(coerce=False):
						a: taml.required
			'''),
			is_schema=True,
		)
		assert taml.loads('a:\n', schema) == {'a': None}

	def test_repeat_key_coerce_false_allows_empty_dict(self):
		'''Verify repeat key coerce=False allows empty dict.'''
		# coerce=False on the dict key repeat preserves null
		schema = taml.loads(
			s('''
				a:
					taml.repeat(coerce=False):
						a: taml.required
			'''),
			is_schema=True,
		)
		assert taml.loads('a: {}\n', schema) == {'a': {}}

	def test_repeat_value_coerce_default_null_to_empty(self):
		'''Verify repeat value default coerce null to empty.'''
		# default coerce=True on bare repeat-as-value turns null into []
		schema = taml.loads('items: taml.repeat(int)\n', is_schema=True)
		assert taml.loads('items:\n', schema) == {'items': []}

	def test_repeat_value_coerce_default_converts_items(self):
		'''Verify repeat value default coerce converts items.'''
		# default coerce=True on bare repeat-as-value turns null into []
		schema = taml.loads('items: taml.repeat(int)\n', is_schema=True)
		assert taml.loads("items: ['1', '2']\n", schema) == {'items': [1, 2]}

	def test_repeat_value_coerce_false_preserves_null(self):
		'''Verify repeat value coerce=False preserves null.'''
		# coerce=False on bare repeat-as-value preserves null
		schema = taml.loads('items: taml.repeat(int, coerce=False)\n', is_schema=True)
		assert taml.loads('items:\n', schema) == {'items': None}

	def test_repeat_value_coerce_false_converts_items(self):
		'''Verify repeat value coerce=False converts items.'''
		# coerce=False on bare repeat-as-value preserves null
		schema = taml.loads('items: taml.repeat(int, coerce=False)\n', is_schema=True)
		assert taml.loads("items: ['1', '2']\n", schema) == {'items': [1, 2]}

	def test_repeat_list_marker_coerce_default_null_to_empty(self):
		'''Verify repeat list marker default coerce null to empty.'''
		# default coerce=True on list repeat marker turns null into []
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int)
			'''),
			is_schema=True,
		)
		assert taml.loads('items:\n', schema) == {'items': []}

	def test_repeat_list_marker_coerce_false_preserves_null(self):
		'''Verify repeat list marker coerce=False preserves null.'''
		# coerce=False on list repeat marker preserves null
		schema = taml.loads(
			s('''
				items:
					- taml.repeat(int, coerce=False)
			'''),
			is_schema=True,
		)
		assert taml.loads('items:\n', schema) == {'items': None}


if __name__ == '__main__':
	unittest.TestLoader().loadTestsFromTestCase(TestSchemaRepeat).debug()
	print('tests passed')
