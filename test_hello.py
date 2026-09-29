import unittest
import io
import sys
from hello import get_hello_world, main

class TestHello(unittest.TestCase):
    """
    Test cases for the hello.py program.
    """

    def test_get_hello_world(self) -> None:
        """
        Test that get_hello_world returns the correct string.
        """
        result = get_hello_world()
        self.assertEqual(result, "hello world")

    def test_main(self) -> None:
        """
        Test that main prints the correct string to standard output.
        """
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            main()
            self.assertEqual(captured_output.getvalue(), "hello world\n")
        finally:
            sys.stdout = sys.__stdout__

if __name__ == "__main__":
    unittest.main()
