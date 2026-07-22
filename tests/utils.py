import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from epicstuff import s, NewDict
from taml import taml

# Absolute path to the shared test fixture, so tests don't depend on the process CWD.
test_taml_path = Path(__file__).parent / 'test.taml'
test_schame_path = Path(__file__).parent / 'schema.taml'

def assert_equals(schema: str, native: dict, data: str, expected: Any) -> None:  # pyright: ignore[reportRedeclaration]
	'Test schema parsing, then data parsing with both native and parsed schema.'
	schema: NewDict = taml.loads(schema, is_schema=True)
	assert schema == native
	assert taml.loads(data, schema) == expected
	assert taml.loads(data, native) == expected
def assert_raises2(schema: str, native: dict, data: str, expected: type[Exception], msg: str | None = None) -> None:  # pyright: ignore[reportRedeclaration]
	'Parse schema text and assert it equals native, then drive data through both the parsed schema and the native schema, expecting the same result (or, if expected is an exception type, the same error).'
	schema: NewDict = taml.loads(schema, is_schema=True)
	assert schema == native
	assert_raises(expected, lambda: taml.loads(data, schema), msg)
	assert_raises(expected, lambda: taml.loads(data, native), msg)
def assert_raises(exc_type: type[BaseException] | tuple[type[BaseException], ...], fn: Callable, msg: str | None = None, strict: bool = True) -> None:
	try:
		fn()
	except exc_type as e:
		if msg is None:
			return

		actual = str(e)
		if actual == msg:
			return

		if not strict:
			location_pattern = r'(?s)^(.*) \(line \d+, col \d+\)$'
			expected_match = re.fullmatch(location_pattern, msg)
			actual_match = re.fullmatch(location_pattern, actual)

			if expected_match is not None and actual_match is not None and expected_match.group(1) == actual_match.group(1):
				print(s(f'''
					Exception location mismatch:
						Expected: {msg}
						Actual:   {actual}
				'''))
				return

		error = AssertionError(s(f'''
			Exception message mismatch:
				Expected: {msg}
				Actual:   {actual}
		'''))
		raise error.with_traceback(e.__traceback__) from e
	raise AssertionError(f'Expected {exc_type.__name__} to be raised')
