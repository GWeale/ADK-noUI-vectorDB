#!/usr/bin/env python3
from tools.file_system_tool import read_file, write_file, read_file_tool, write_file_tool


def demo_file_operations():
    print("=== FileSystemTool Demo ===\n")
    
    # Read existing file
    print("1. Reading existing test file:")
    result = read_file("coding_agent/tests/test_file.txt")
    print(f"Result: {result}\n")
    
    # Write a new file
    print("2. Writing a new demo file:")
    demo_content = "This is demo content created by the FileSystemTool.\nIt demonstrates secure file writing within the project directory."
    result = write_file("coding_agent/tests/demo_output.txt", demo_content)
    print(f"Result: {result}\n")
    
    # Read the newly created file
    print("3. Reading the newly created file:")
    result = read_file("coding_agent/tests/demo_output.txt")
    print(f"Result: {result}\n")
    
    # Read files from workspace root
    print("4. Reading example_code.py from workspace root:")
    result = read_file("example_code.py")
    print(f"Result: {result}\n")
    
    # try to access file outside project (should fail)
    print("5. Attempting to read file outside project (security test):")
    result = read_file("../../../etc/passwd")
    print(f"Result: {result}\n")
    
    # try to write file outside project (should fail)
    print("6. Attempting to write file outside project (security test):")
    result = write_file("../malicious_file.txt", "This should not be created")
    print(f"Result: {result}\n")
    
    # show that the tools are ready for ADK integration
    print("7. ADK Tool objects are ready:")
    print(f"Read tool: {read_file_tool}")
    print(f"Write tool: {write_file_tool}")
    print("These can be integrated into an ADK agent's tools list.")


if __name__ == "__main__":
    demo_file_operations()

print("hello world")