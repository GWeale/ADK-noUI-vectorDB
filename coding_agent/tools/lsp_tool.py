from typing import List, Dict, Any, Optional, Union
from google.adk.tools import FunctionTool
from pathlib import Path
import logging
import os
import tempfile
import json
import subprocess
import asyncio


from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
MULTILSPY_AVAILABLE = True

#https://github.com/microsoft/multilspy/archive/main.zip
#this code was mainly pulled from the multilspy repo and https://sky.cs.berkeley.edu/project/multilspy/
class Position:
    """Simple position class for line/column coordinates"""
    def __init__(self, line: int, character: int):
        self.line = line
        self.character = character

class LSPTool:
    """Tool for integrating with Language Server Protocol servers"""
    
    def __init__(self, project_root: str):
        
        self.project_root = Path(project_root).resolve()
        self.logger = self._setup_logger()
        self.language_servers: Dict[str, SyncLanguageServer] = {}
        
        # Language server configurations
        self.server_configs = {
            '.py': {
                'language_id': 'python',
                'code_language': 'python'
            },
            '.java': {
                'language_id': 'java', 
                'code_language': 'java'
            },
            '.js': {
                'language_id': 'javascript',
                'code_language': 'javascript'
            },
            '.ts': {
                'language_id': 'typescript',
                'code_language': 'javascript'  # multilspy uses 'javascript' for both JS and TS
            },
            '.rs': {
                'language_id': 'rust',
                'code_language': 'rust'
            },
            '.cs': {
                'language_id': 'csharp',
                'code_language': 'csharp'
            }
        }
    
    def _setup_logger(self) -> MultilspyLogger:
        """Setup MultilspyLogger for language servers"""
        return MultilspyLogger()
    
    def _get_or_create_server(self, file_ext: str) -> Optional[SyncLanguageServer]:
        """Get or create a language server for the given file extension"""
        if file_ext not in self.server_configs:
            print(f"No language server configuration for {file_ext}")
            return None
        
        server_name = f"server_{file_ext}"
        
        # Return existing server if available
        if server_name in self.language_servers:
            return self.language_servers[server_name]
        
        try:
            # Create configuration for the language server
            config_dict = {"code_language": self.server_configs[file_ext]['code_language']}
            config = MultilspyConfig.from_dict(config_dict)
            
            # Create new language server with the correct three parameters
            language_server = SyncLanguageServer.create(
                config, 
                self.logger, 
                str(self.project_root)
            )
            
            self.language_servers[server_name] = language_server
            return language_server
            
        except Exception as e:
            print(f"Failed to create language server for {file_ext}: {e}")
            return None
    
    def get_diagnostics(self, file_path: str, content: Optional[str] = None) -> str:
        """
        Get diagnostics (errors, warnings) for a file.
        
        Args:
            file_path: Path to the file to analyze
            content: Optional file content (if not provided, reads from file)
            
        Returns:
            Formatted string with diagnostic information
        """
        abs_file_path = self.project_root / file_path
        if content is None:
            if not abs_file_path.exists():
                return f"Error: File {file_path} does not exist"
            with open(abs_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        file_ext = Path(file_path).suffix.lower()
        if file_ext == '.py':
            return self._get_python_diagnostics(file_path, content)
        elif file_ext in ['.js', '.ts', '.tsx', '.jsx']:
            return self._get_js_ts_diagnostics(file_path, content)
        else:
            return self._get_generic_diagnostics(file_path, content)
    
    def _get_python_diagnostics(self, file_path: str, content: str) -> str:
        """Get Python-specific diagnostics using AST and basic checks"""
        import ast
        import tempfile
        import subprocess
        
        diagnostics = []
        error_count = 0
        warning_count = 0
        
        # Check syntax with AST
        try:
            ast.parse(content)
            diagnostics.append("Syntax: No syntax errors found")
        except SyntaxError as e:
            error_count += 1
            diagnostics.append(f"Syntax Error (line {e.lineno}): {e.msg}")
        
        # Check for basic issues
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Check for obvious issues
            if line_stripped.startswith('import ') and ' as ' not in line_stripped and '*' in line_stripped:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Wildcard import detected")
            
            if 'print(' in line and not line_stripped.startswith('#'):
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): print() statement found (consider logging)")
            
            if len(line) > 120:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Line too long ({len(line)} chars)")
        
        # wanted to try pyflakes, but seemed to sometimes work and sometimes not will
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                
                result = subprocess.run(['python', '-m', 'pyflakes', tmp_file.name], 
                                      capture_output=True, text=True, timeout=5)
                
                if result.stdout:
                    pyflakes_issues = result.stdout.strip().split('\n')
                    for issue in pyflakes_issues:
                        if issue.strip():
                            warning_count += 1
                            # Clean up the file path in the message
                            clean_issue = issue.replace(tmp_file.name, file_path)
                            diagnostics.append(f"Pyflakes: {clean_issue}")
                
                import os
                os.unlink(tmp_file.name)
        except:
            # pyflakes not available or failed
            pass
        
        # Format result
        result = f"Diagnostics for {file_path}:\n"
        result += f"Summary: {error_count} errors, {warning_count} warnings\n\n"
        
        if diagnostics:
            result += "\n".join(diagnostics)
        else:
            result += "No issues found!"
        
        return result
    
    def _get_js_ts_diagnostics(self, file_path: str, content: str) -> str:
        """Get JavaScript/TypeScript basic diagnostics"""
        diagnostics = []
        error_count = 0
        warning_count = 0
        
        lines = content.split('\n')
        
        # Basic syntax and style checks
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Check for common issues
            if 'console.log(' in line and not line_stripped.startswith('//'):
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): console.log() found")
            
            if line_stripped.endswith(';') and line_stripped.count(';') > 1:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Multiple statements on one line")
            
            if len(line) > 120:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Line too long ({len(line)} chars)")
            
            # Check for missing semicolons (basic check)
            if (line_stripped and 
                not line_stripped.startswith('//') and 
                not line_stripped.startswith('/*') and
                not line_stripped.endswith(';') and
                not line_stripped.endswith('{') and
                not line_stripped.endswith('}') and
                not line_stripped.endswith(',') and
                'if (' not in line_stripped and
                'for (' not in line_stripped and
                'while (' not in line_stripped):
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Missing semicolon?")
        
        # Format result
        result = f"🔍 Diagnostics for {file_path}:\n"
        result += f"📊 Summary: {error_count} errors, {warning_count} warnings\n\n"
        
        if diagnostics:
            result += "\n".join(diagnostics)
        else:
            result += "No issues found!"
        
        return result
    
    def _get_generic_diagnostics(self, file_path: str, content: str) -> str:
        """Get basic diagnostics for any file type"""
        diagnostics = []
        warning_count = 0
        
        lines = content.split('\n')
        
        # Basic checks
        for i, line in enumerate(lines, 1):
            if len(line) > 200:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Very long line ({len(line)} chars)")
            
            if line.rstrip() != line:
                warning_count += 1
                diagnostics.append(f"Warning (line {i}): Trailing whitespace")
        
        # File-level checks
        if not content.strip():
            warning_count += 1
            diagnostics.append("Warning: File is empty")
        
        if not content.endswith('\n'):
            warning_count += 1
            diagnostics.append("Warning: File doesn't end with newline")
        
        # Format result
        result = f"🔍 Diagnostics for {file_path}:\n"
        result += f"📊 Summary: 0 errors, {warning_count} warnings\n\n"
        
        if diagnostics:
            result += "\n".join(diagnostics)
        else:
            result += "No issues found!"
        
        return result

    def get_definition(self, file_path: str, line: int, character: int) -> str:
        """
        Get definition location for symbol at given position.
        
        Args:
            file_path: Path to the file
            line: Line number (0-based)
            character: Character position (0-based)
            
        Returns:
            Definition location information
        """
        abs_file_path = self.project_root / file_path
        if not abs_file_path.exists():
            return f"Error: File {file_path} does not exist"
        language_server = self._get_or_create_server(Path(file_path).suffix)
        if not language_server:
            return f"No language server available for {Path(file_path).suffix} files"
        with language_server.start_server():
            try:
                result = language_server.request_definition(
                    file_path,  # relative path to file
                    line,       # line number
                    character   # column number
                )
                if result:
                    return f"Definition found: {result}"
                else:
                    return f"No definition found at {file_path}:{line}:{character}"
            except AttributeError:
                return f"Definition lookup not supported for {Path(file_path).suffix} files"

    def get_references(self, file_path: str, line: int, character: int) -> str:
        """
        Get references to symbol at given position.
        
        Args:
            file_path: Path to the file
            line: Line number (0-based)
            character: Character position (0-based)
            
        Returns:
            List of reference locations
        """
        abs_file_path = self.project_root / file_path
        if not abs_file_path.exists():
            return f"Error: File {file_path} does not exist"
        language_server = self._get_or_create_server(Path(file_path).suffix)
        if not language_server:
            return f"No language server available for {Path(file_path).suffix} files"
        with language_server.start_server():
            try:
                result = language_server.request_references(
                    file_path,  # relative path to file
                    line,       # line number  
                    character   # column number
                )
                if result:
                    return f"References found: {result}"
                else:
                    return f"No references found at {file_path}:{line}:{character}"
            except AttributeError:
                return f"References lookup not supported for {Path(file_path).suffix} files"
    
    def validate_code_in_shadow_workspace(self, file_path: str, new_content: str) -> Dict[str, Any]:
        """
        Validate code changes in a temporary shadow workspace.
        
        Args:
            file_path: Path to the file being modified
            new_content: New content to validate
            
        Returns:
            Dictionary with validation results
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_workspace = Path(temp_dir)
            self._copy_workspace_context(temp_workspace, file_path)
            temp_file = temp_workspace / file_path
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            shadow_lsp = LSPTool(str(temp_workspace))
            diagnostics_result = shadow_lsp.get_diagnostics(file_path, new_content)
            has_errors = "ERROR" in diagnostics_result
            error_count = diagnostics_result.count("ERROR")
            warning_count = diagnostics_result.count("WARNING")
            return {
                "valid": not has_errors,
                "error_count": error_count,
                "warning_count": warning_count,
                "diagnostics": diagnostics_result,
                "temp_workspace": str(temp_workspace)
            }
    
    def _copy_workspace_context(self, temp_workspace: Path, target_file: str):
        """Copy relevant workspace files for context"""
        try:
            import shutil
            
            # For now, just copy the target file and basic project structure
            # In a full implementation, you'd analyze dependencies and copy related files
            
            # Copy the target file if it exists
            source_file = self.project_root / target_file
            if source_file.exists():
                dest_file = temp_workspace / target_file
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, dest_file)
            
            # Copy common config files
            config_files = [
                'pyproject.toml', 'setup.py', 'requirements.txt',
                'package.json', 'tsconfig.json', '.pylintrc'
            ]
            
            for config_file in config_files:
                source_config = self.project_root / config_file
                if source_config.exists():
                    dest_config = temp_workspace / config_file
                    shutil.copy2(source_config, dest_config)
                    
        except Exception as e:
            print(f"Could not copy full workspace context: {e}")
    
    def cleanup(self):
        """Cleanup language server resources"""
        for server in self.language_servers.values():
            try:
                # For multilspy, we don't need explicit shutdown
                # The context manager handles this
                pass
            except Exception as e:
                print(f"Error shutting down language server: {e}")
        self.language_servers.clear()

# ADK tool functions
def get_diagnostics_tool(file_path: str, content: str = "") -> str:
    """Get diagnostics (errors, warnings) for a file"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    lsp_tool = LSPTool(project_root)
    try:
        content_arg = content if content else None
        return lsp_tool.get_diagnostics(file_path, content_arg)
    finally:
        lsp_tool.cleanup()

def go_to_definition_tool(file_path: str, line: int, character: int) -> str:
    """Get definition location for symbol at given position"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    lsp_tool = LSPTool(project_root)
    try:
        return lsp_tool.get_definition(file_path, line, character)
    finally:
        lsp_tool.cleanup()

def find_references_tool(file_path: str, line: int, character: int) -> str:
    """Find all references to symbol at given position"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    lsp_tool = LSPTool(project_root)
    try:
        return lsp_tool.get_references(file_path, line, character)
    finally:
        lsp_tool.cleanup()

def validate_code_tool(file_path: str, new_content: str) -> str:
    """Validate code changes in a shadow workspace"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    lsp_tool = LSPTool(project_root)
    try:
        result = lsp_tool.validate_code_in_shadow_workspace(file_path, new_content)
        
        if result.get("valid", False):
            return f"✅ Code validation passed! No errors found.\nWarnings: {result.get('warning_count', 0)}"
        else:
            error_info = result.get("error", "")
            diagnostics = result.get("diagnostics", "")
            return f"❌ Code validation failed!\nErrors: {result.get('error_count', 0)}\nWarnings: {result.get('warning_count', 0)}\n\n{diagnostics}\n{error_info}"
    finally:
        lsp_tool.cleanup()

# ADK tool wrappers
get_diagnostics_adk_tool = FunctionTool(get_diagnostics_tool)
go_to_definition_adk_tool = FunctionTool(go_to_definition_tool)
find_references_adk_tool = FunctionTool(find_references_tool)
validate_code_adk_tool = FunctionTool(validate_code_tool) 