from google.adk.tools import FunctionTool
import os
from pathlib import Path

def index_codebase_tool() -> str:
    project_root = Path(os.environ.get('ADK_PROJECT_ROOT', os.getcwd()))
    from coding_agent.tools.indexing_agent import IndexingAgent
    indexer = IndexingAgent(str(project_root))
    result = indexer.index_codebase()
    status_msg = f"Indexing complete!\n"
    status_msg += f"Files indexed: {len(result['indexed_files'])}\n"
    status_msg += f"Code elements found: {result['total_elements']}\n"
    if result['errors']:
        status_msg += f"Errors: {len(result['errors'])}\n"
        for error in result['errors'][:3]:
            status_msg += f"  - {error}\n"
    status_msg += "\nYou can now search the codebase using semantic queries!"
    return status_msg

# Create ADK tool
index_codebase_adk_tool = FunctionTool(index_codebase_tool) 