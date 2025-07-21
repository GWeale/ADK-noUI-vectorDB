import os
from google.adk.tools import FunctionTool

# this should point to the workspace root (parent of coding_agent folder)
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def _is_path_safe(path: str) -> bool:
    """Checks if the provided path is within the project root."""
    abs_path = os.path.abspath(os.path.join(PROJECT_ROOT, path))
    return abs_path.startswith(PROJECT_ROOT)

def read_file(file_path: str) -> str:
    """Reads the full content of a file if it is within the safe project directory."""
    if not _is_path_safe(file_path):
        return f"Error: Path '{file_path}' is outside the allowed project directory."
    try:
        with open(os.path.join(PROJECT_ROOT, file_path), 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{file_path}'."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def write_file(file_path: str, content: str) -> str:
    """Writes content to a file if it is within the safe project directory."""
    if not _is_path_safe(file_path):
        return f"Error: Path '{file_path}' is outside the allowed project directory."
    try:
        full_path = os.path.join(PROJECT_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}."
    except Exception as e:
        return f"An unexpected error occurred while writing: {e}"

read_file_tool = FunctionTool(read_file)
write_file_tool = FunctionTool(write_file) 