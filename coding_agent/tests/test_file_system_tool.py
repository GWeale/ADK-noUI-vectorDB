import unittest
import os
import tempfile
import shutil
from coding_agent.tools.file_system_tool import read_file, write_file, _is_path_safe, PROJECT_ROOT


class TestFileSystemTool(unittest.TestCase):
    """Unit tests for the FileSystemTool functions."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_content = "This is test content for unit testing."
        self.test_file_path = "coding_agent/tests/temp_test.txt"
        self.full_test_path = os.path.join(PROJECT_ROOT, self.test_file_path)
        
        os.makedirs(os.path.dirname(self.full_test_path), exist_ok=True)
        
        with open(self.full_test_path, 'w') as f:
            f.write(self.test_content)
    
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        if os.path.exists(self.full_test_path):
            os.remove(self.full_test_path)
    
    def test_is_path_safe_valid_paths(self):
        """Test that valid paths within the project root are considered safe."""
        valid_paths = [
            "coding_agent/tests/test_file.txt",
            "coding_agent/agent.py",
            "coding_agent/tools/file_system_tool.py",
            "example_code.py",
            "sample_html.html",
            "requirements.txt",
            "subfolder/file.txt"  # Even if it doesn't exist
        ]
        
        for path in valid_paths:
            with self.subTest(path=path):
                self.assertTrue(_is_path_safe(path), f"Path '{path}' should be considered safe")
    
    def test_is_path_safe_invalid_paths(self):
        """Test that paths outside the project root are considered unsafe."""
        unsafe_paths = [
            "../outside_project.txt",
            "../../etc/passwd",
            "/etc/passwd",
            "tests/../../../sensitive_file.txt"
        ]
        
        for path in unsafe_paths:
            with self.subTest(path=path):
                self.assertFalse(_is_path_safe(path), f"Path '{path}' should be considered unsafe")
    
    def test_read_file_success(self):
        """Test successfully reading a file within the project directory."""
        result = read_file(self.test_file_path)
        self.assertEqual(result, self.test_content)
    
    def test_read_file_not_found(self):
        """Test reading a non-existent file within the project directory."""
        result = read_file("coding_agent/tests/nonexistent_file.txt")
        self.assertIn("Error: File not found", result)
        self.assertIn("nonexistent_file.txt", result)
    
    def test_read_file_unsafe_path(self):
        """Test reading a file outside the project directory."""
        result = read_file("../outside_project.txt")
        self.assertIn("Error: Path", result)
        self.assertIn("outside the allowed project directory", result)
    
    def test_write_file_success(self):
        """Test successfully writing to a file within the project directory."""
        new_content = "This is new test content."
        new_file_path = "coding_agent/tests/new_test_file.txt"
        
        result = write_file(new_file_path, new_content)
        self.assertIn("Successfully wrote to", result)
        self.assertIn(new_file_path, result)
        
        # check if it was actually written content was actually written
        full_path = os.path.join(PROJECT_ROOT, new_file_path)
        self.assertTrue(os.path.exists(full_path))
        
        with open(full_path, 'r') as f:
            written_content = f.read()
        self.assertEqual(written_content, new_content)
        
        # back sure back path is seen and removed
        os.remove(full_path)
    
    def test_write_file_create_directory(self):
        """Test writing to a file in a new subdirectory (should create the directory)."""
        new_content = "Content in new directory."
        new_file_path = "coding_agent/tests/new_subdir/test_file.txt"
        
        result = write_file(new_file_path, new_content)
        self.assertIn("Successfully wrote to", result)
        
        # find the directory and file were created
        full_path = os.path.join(PROJECT_ROOT, new_file_path)
        self.assertTrue(os.path.exists(full_path))
        
        with open(full_path, 'r') as f:
            written_content = f.read()
        self.assertEqual(written_content, new_content)
        
        # Clean up
        shutil.rmtree(os.path.join(PROJECT_ROOT, "coding_agent/tests/new_subdir"))
    
    def test_write_file_unsafe_path(self):
        """Test writing to a file outside the project directory."""
        result = write_file("../outside_project.txt", "malicious content")
        self.assertIn("Error: Path", result)
        self.assertIn("outside the allowed project directory", result)
    
    def test_write_file_overwrite_existing(self):
        """Test overwriting an existing file."""
        new_content = "Overwritten content."
        
        result = write_file(self.test_file_path, new_content)
        self.assertIn("Successfully wrote to", result)
        
        # make sure the content was overwritten
        with open(self.full_test_path, 'r') as f:
            written_content = f.read()
        self.assertEqual(written_content, new_content)


if __name__ == '__main__':
    unittest.main() 