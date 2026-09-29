def get_hello_world() -> str:
    """
    Returns the hello world message.

    This function takes no parameters. It simply returns the string 'hello world'.

    Returns:
        str: The string 'hello world'.
    """
    return "hello world"

def main() -> None:
    """
    Main function to print the hello world message.

    This function takes no parameters and returns nothing.
    It calls get_hello_world() and prints the result to standard output.
    """
    print(get_hello_world())

if __name__ == "__main__":
    main()
