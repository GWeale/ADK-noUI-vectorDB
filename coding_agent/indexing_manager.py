
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any
import json
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the parent directory to the path so we can import our tools
sys.path.insert(0, str(Path(__file__).parent.parent))

def setup_environment():
    """Basic environment setup"""
    logging.info("Setting up environment...")
    # Set the project root env variable
    project_root = Path(__file__).parent.parent.absolute()
    os.environ['ADK_PROJECT_ROOT'] = str(project_root)
    # Print a shell command for user convenience
    shell_cmd = f'export ADK_PROJECT_ROOT="{project_root}"'
    logging.info(f"If you want to use the tools in your shell, run: {shell_cmd}")
    logging.info(f"Project root is: {project_root}")
    logging.info("Environment ready for tools.")
    return project_root


def check_dependencies():
    """Quick check for required packages"""
    logging.info("Checking dependencies...")
    required_packages = [
        'chromadb',
        'sentence_transformers', 
        'multilspy',
        'tree_sitter',
        'tree_sitter_python',
        'tree_sitter_javascript',
        'tree_sitter_typescript'
    ]
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            logging.info(f"Found: {package}")
        except ImportError:
            logging.info(f"Missing: {package}")
            missing_packages.append(package)
    if missing_packages:
        logging.info(f"Missing packages: {', '.join(missing_packages)}")
        logging.info("Run: pip install -r requirements.txt")
        return False
    logging.info("All dependencies look good.")
    return True


def run_indexing(project_root: Path, force_reindex: bool = False):
    logging.info("Starting codebase indexing...")
    from coding_agent.tools.indexing_agent import IndexingAgent
    index_dir = project_root / ".adk_index"
    if index_dir.exists() and not force_reindex:
        logging.info(f"Index directory already exists at {index_dir}")
        response = input("Reindex anyway? (y/N): ")
        if response.lower() != 'y':
            logging.info("Skipping indexing.")
            return True
    indexer = IndexingAgent(str(project_root))
    result = indexer.index_codebase()
    logging.info(f"Indexing complete.")
    logging.info(f"Files indexed: {len(result['indexed_files'])}")
    logging.info(f"Code elements: {result['total_elements']}")
    if result['errors']:
        logging.info(f"Errors: {len(result['errors'])}")
        for error in result['errors'][:5]:
            logging.info(f"  - {error}")
        if len(result['errors']) > 5:
            logging.info(f"  ... and {len(result['errors']) - 5} more")
    index_dir.mkdir(exist_ok=True)
    report_file = index_dir / "indexing_report.json"
    with open(report_file, 'w') as f:
        json.dump(result, f, indent=2)
    logging.info(f"Indexing report saved to: {report_file}")
    return True


def test_search_functionality(project_root: Path):
    logging.info("Testing search...")
    from coding_agent.tools.vector_search_tool import VectorSearchTool
    search_tool = VectorSearchTool(str(project_root))
    logging.info("Trying a basic code search...")
    result = search_tool.semantic_search("function definition", max_results=3)
    if "Error" in result:
        logging.info(f"Search failed: {result}")
        return False
    else:
        logging.info("Code search works.")
    logging.info("Trying file search...")
    result = search_tool.find_files_by_content("main agent", max_results=2)
    if "Error" in result:
        logging.info(f"File search failed: {result}")
        return False
    else:
        logging.info("File search works.")
    logging.info("Search functionality is working.")
    return True


def test_lsp_functionality(project_root: Path):
    logging.info("Testing LSP...")
    from coding_agent.tools.lsp_tool import LSPTool
    python_files = list(project_root.rglob("*.py"))
    if not python_files:
        logging.info("No Python files found for LSP test.")
        return True
    test_file = python_files[0]
    relative_path = test_file.relative_to(project_root)
    lsp_tool = LSPTool(str(project_root))
    logging.info(f"Testing diagnostics on {relative_path}...")
    result = lsp_tool.get_diagnostics(str(relative_path))
    if "Error" in result and "No language server available" not in result:
        logging.info(f"Diagnostics failed: {result}")
        return False
    else:
        logging.info("Diagnostics seem to work (or no LSP server available)")
    lsp_tool.cleanup()  # type: ignore
    logging.info("LSP test done.")
    return True


def show_status(project_root: Path):
    """Show some info about the current setup"""
    logging.info("=" * 50)
    index_dir = project_root / ".adk_index"
    if index_dir.exists():
        logging.info(f"Index directory: {index_dir}")
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.Client(Settings(
                persist_directory=str(index_dir),
                anonymized_telemetry=False
            ))
            collections = client.list_collections()
            logging.info(f"Collections: {[c.name for c in collections]}")
            for collection in collections:
                count = collection.count()
                logging.info(f"  - {collection.name}: {count} items")
        except Exception as e:
            logging.info(f"Could not read collections: {e}")
    else:
        logging.info("No index directory found.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="ADK Coding Agent Manager")
    parser.add_argument("command", choices=[
        "setup", "index", "test", "status", "full-setup"
    ], help="Command to run")
    parser.add_argument("--force", action="store_true", 
                       help="Force reindexing even if index exists")
    
    args = parser.parse_args()
    
    project_root = setup_environment()
    
    if args.command == "setup":
        logging.info("Setting up environment...")
        if check_dependencies():
            logging.info("Setup complete! Ready for indexing.")
        else:
            logging.info("Setup incomplete. Install missing dependencies.")
            return 1
    
    elif args.command == "index":
        if not check_dependencies():
            return 1
        if run_indexing(project_root, args.force):
            logging.info("Indexing complete!")
        else:
            logging.info("Indexing failed!")
            return 1
    
    elif args.command == "test":
        if not check_dependencies():
            return 1
        logging.info("Running comprehensive tests...")
        success = True
        success &= test_search_functionality(project_root)
        success &= test_lsp_functionality(project_root)
        
        if success:
            logging.info("All tests passed!")
        else:
            logging.info("Some tests failed!")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())