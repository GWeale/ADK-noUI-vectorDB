from typing import List, Dict, Any, Optional, Union
from google.adk.tools import FunctionTool
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
import os

class VectorSearchTool:
    """Tool for semantic search over the indexed codebase"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB client with persistent storage
        persist_dir = str(self.project_root / ".adk_index")
        if not os.path.exists(persist_dir):
            print(f"Warning: Index directory {persist_dir} does not exist. Run indexing first.")
        
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Get existing collections
        try:
            self.code_collection = self.client.get_collection("code_elements")
            self.file_collection = self.client.get_collection("file_summaries")
        except ValueError:
            # Collections don't exist yet
            self.code_collection = None
            self.file_collection = None
    
    def semantic_search(self, query: str, max_results: int = 5, file_type_filter: Optional[str] = None) -> str:
        if not self.code_collection:
            return "No code index found. Please run indexing first."
        # Create query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        where_filter = None
        if file_type_filter:
            from typing import Any, cast
            where_filter = cast(Any, {"file_type": file_type_filter})
        results = self.code_collection.query(
            query_embeddings=[query_embedding],
            n_results=max_results,
            where=where_filter
        )
        documents = results.get('documents')
        metadatas = results.get('metadatas') 
        distances = results.get('distances')
        if not documents or not documents[0] or not metadatas or not metadatas[0] or not distances or not distances[0]:
            return f"No results found for query: '{query}'"
        doc_list = documents[0]
        meta_list = metadatas[0] 
        dist_list = distances[0]
        if not (doc_list and meta_list and dist_list):
            return f"No results found for query: '{query}'"
        if not (len(doc_list) == len(meta_list) == len(dist_list)):
            return f"Inconsistent result data for query: '{query}'"
        formatted_results = []
        for i, (doc, metadata, distance) in enumerate(zip(doc_list, meta_list, dist_list)):
            if not isinstance(metadata, dict):
                continue
            result_text = f"Result {i+1} (similarity: {1-distance:.3f}):\n"
            result_text += f"  Name: {metadata.get('name', 'unknown')}\n"
            result_text += f"  Type: {metadata.get('element_type', 'unknown')}\n"
            result_text += f"  File: {metadata.get('file_path', 'unknown')}\n"
            result_text += f"  Lines: {metadata.get('start_line', 'unknown')}-{metadata.get('end_line', 'unknown')}\n"
            if metadata.get('docstring'):
                docstring = str(metadata['docstring'])
                if len(docstring) > 100:
                    docstring = docstring[:100] + "..."
                result_text += f"  Docstring: {docstring}\n"
            content = metadata.get('content', '')
            if isinstance(content, str) and len(content) > 300:
                content = content[:300] + "..."
            result_text += f"  Content:\n{content}\n"
            result_text += "-" * 50 + "\n"
            formatted_results.append(result_text)
        return "\n".join(formatted_results)
    
    def find_files_by_content(self, query: str, max_results: int = 5) -> str:
        """
        Find files by content similarity
        
        Args:
            query: Search query for file content
            max_results: Maximum number of files to return
        
        Returns:
            Formatted file search results
        """
        if not self.file_collection:
            return "No file index found. Please run indexing first."
        
        try:
            # Create query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search in file summaries
            results = self.file_collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results
            )
            
            # Safely extract results with proper type checking
            documents = results.get('documents')
            metadatas = results.get('metadatas')
            distances = results.get('distances')
            
            if not documents or not documents[0] or not metadatas or not metadatas[0] or not distances or not distances[0]:
                return f"No files found for query: '{query}'"
            
            # Type assertions to help the type checker
            doc_list = documents[0]
            meta_list = metadatas[0]
            dist_list = distances[0]
            
            # Ensure all lists are valid and same length
            if not (doc_list and meta_list and dist_list):
                return f"No files found for query: '{query}'"
                
            if not (len(doc_list) == len(meta_list) == len(dist_list)):
                return f"Inconsistent file data for query: '{query}'"
            
            formatted_results = []
            for i, (doc, metadata, distance) in enumerate(zip(doc_list, meta_list, dist_list)):
                # Ensure metadata is a dictionary
                if not isinstance(metadata, dict):
                    continue
                    
                result_text = f"File {i+1} (similarity: {1-distance:.3f}):\n"
                result_text += f"  Path: {metadata.get('file_path', 'unknown')}\n"
                result_text += f"  Type: {metadata.get('file_type', 'unknown')}\n"
                result_text += f"  Lines: {metadata.get('line_count', 'unknown')}\n"
                result_text += f"  Elements: {metadata.get('element_count', 'unknown')}\n"
                result_text += f"  Summary: {metadata.get('summary', 'No summary available')}\n"
                
                if metadata.get('elements_by_type_str'):
                    result_text += f"  Contains: {metadata['elements_by_type_str']}\n"
                
                result_text += "-" * 40 + "\n"
                formatted_results.append(result_text)
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"Error finding files: {str(e)}"
    
    def find_elements_by_type(self, element_type: str, max_results: int = 10) -> str:
        """
        Find code elements by type (function, class, method, etc.)
        
        Args:
            element_type: Type of element to find
            max_results: Maximum number of results
        
        Returns:
            Formatted results
        """
        if not self.code_collection:
            return "No code index found. Please run indexing first."
        
        try:
            # Search for elements of specific type
            results = self.code_collection.get(
                where={"element_type": element_type},
                limit=max_results
            )
            
            # Safely check if we have results
            documents = results.get('documents')
            metadatas = results.get('metadatas')
            
            if not documents or not metadatas:
                return f"No {element_type} elements found."
            
            # Ensure both lists exist and are not empty
            if not isinstance(documents, list) or not isinstance(metadatas, list):
                return f"Invalid data format for {element_type} elements."
                
            if len(documents) == 0 or len(metadatas) == 0:
                return f"No {element_type} elements found."
            
            formatted_results = []
            for i, (doc, metadata) in enumerate(zip(documents, metadatas)):
                # Ensure metadata is a dictionary
                if not isinstance(metadata, dict):
                    continue
                    
                result_text = f"{element_type.title()} {i+1}:\n"
                result_text += f"  Name: {metadata.get('name', 'unknown')}\n"
                result_text += f"  File: {metadata.get('file_path', 'unknown')}\n"
                result_text += f"  Lines: {metadata.get('start_line', 'unknown')}-{metadata.get('end_line', 'unknown')}\n"
                result_text += "-" * 30 + "\n"
                
                formatted_results.append(result_text)
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"Error finding {element_type} elements: {str(e)}"
    
    def get_file_structure(self, file_path: str) -> str:
        """
        Get the structure of a specific file
        
        Args:
            file_path: Path to the file
        
        Returns:
            Formatted file structure
        """
        if not self.code_collection:
            return "No code index found. Please run indexing first."
        
        try:
            # Search for elements in the specific file
            results = self.code_collection.get(
                where={"file_path": file_path}
            )
            
            # Safely check results
            metadatas = results.get('metadatas')
            if not metadatas or not isinstance(metadatas, list):
                return f"No structure information found for {file_path}"
            
            file_info = ""
            
            # Try to get file-level information
            if self.file_collection:
                try:
                    file_results = self.file_collection.get(ids=[file_path])
                    file_metadatas = file_results.get('metadatas')
                    if file_metadatas and isinstance(file_metadatas, list) and len(file_metadatas) > 0:
                        metadata = file_metadatas[0]
                        if isinstance(metadata, dict):
                            file_info = f"File: {file_path}\n"
                            file_info += f"Type: {metadata.get('file_type', 'unknown')}\n"
                            file_info += f"Lines: {metadata.get('line_count', 'unknown')}\n"
                            file_info += f"Total elements: {metadata.get('element_count', 'unknown')}\n\n"
                except:
                    pass
            
            # Format elements
            elements_by_type: Dict[str, List[Dict[str, Any]]] = {}
            for metadata in metadatas:
                if not isinstance(metadata, dict):
                    continue
                element_type = metadata.get('element_type', 'unknown')
                if isinstance(element_type, str):
                    if element_type not in elements_by_type:
                        elements_by_type[element_type] = []
                    elements_by_type[element_type].append(metadata)
            
            formatted_results = [file_info]
            
            for element_type, elements in elements_by_type.items():
                formatted_results.append(f"{element_type.upper()}S:")
                for element in elements:
                    name = element.get('name', 'unknown')
                    start_line = element.get('start_line', 'unknown')
                    end_line = element.get('end_line', 'unknown')
                    formatted_results.append(f"  - {name} (lines {start_line}-{end_line})")
                formatted_results.append("")
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"Error getting file structure: {str(e)}"

# Create the ADK tools
def search_code_tool(query: str, max_results: int = 10, element_types: str = "") -> str:
    """Search for code elements using semantic similarity"""
    # Get project root from environment or use default
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    
    # Parse element_types if provided
    types_list = None
    if element_types:
        types_list = [t.strip() for t in element_types.split(',') if t.strip()]
    
    # Since semantic_search expects file_type_filter, not element types, use first type if available
    file_filter = types_list[0] if types_list else None
    return search_tool.semantic_search(query, max_results, file_filter)

def search_files_tool(query: str, max_results: int = 5) -> str:
    """Search for files based on their summaries"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    return search_tool.find_files_by_content(query, max_results)

def get_file_context_tool(file_path: str, max_elements: int = 20) -> str:
    """Get context about a specific file including all its code elements"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    return search_tool.get_file_structure(file_path)

# ADK tool wrappers
search_code_adk_tool = FunctionTool(search_code_tool)
search_files_adk_tool = FunctionTool(search_files_tool)
get_file_context_adk_tool = FunctionTool(get_file_context_tool) 