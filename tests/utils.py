import contextlib, re, tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from epicstuff import NewDict, s
from taml import taml


recorded_values: list[Any] = []

@contextlib.contextmanager
def create_file(text: str, name: str = 'test.taml') -> Iterator[Path]:
	'Create a temporary text file and remove it after the test.'
	with tempfile.TemporaryDirectory() as tmp_dir:
		path = Path(tmp_dir) / name
		path.write_text(text)
		yield path

def recording_converter(value: Any, *, marker: Any = None) -> Any:
	recorded_values.append((value, marker))
	return value

def record_then_raise_on_bad(value: Any) -> Any:
	recorded_values.append((value, None))
	if value == 'bad':
		raise RuntimeError('runtime failure')
	return value

def reset_recorded_values() -> None:
	recorded_values.clear()

def return_none(_value: Any) -> None:
	return None

def raise_runtime_error(_value: Any) -> None:
	raise RuntimeError('runtime failure')

def assert_equals(schema: str, native: Any, data: str, expected: Any) -> None:  # pyright: ignore[reportRedeclaration]
	'Test schema parsing, then data parsing with both native and parsed schema.'
	schema: NewDict = taml.loads(schema, is_schema=True)
	assert schema == native
	assert taml.loads(data, schema) == expected
	assert taml.loads(data, native) == expected

def assert_raises2(schema: str, native: Any, data: str, expected: type[Exception], msg: str | None = None) -> None:  # pyright: ignore[reportRedeclaration]
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
	name = (
		' | '.join(error.__name__ for error in exc_type)
		if isinstance(exc_type, tuple)
		else exc_type.__name__
	)
	raise AssertionError(f'Expected {name} to be raised')