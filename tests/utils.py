import re
from epicstuff import s
from collections.abc import Callable
from pathlib import Path
from typing import Any


# Absolute path to the shared test fixture, so tests don't depend on the process CWD.
TEST_TAML = Path(__file__).parent / 'test.taml'


def assert_raises( exc_type: type[BaseException], fn: Callable[[], Any], msg: str | None = None, strict: bool = True) -> None:
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
