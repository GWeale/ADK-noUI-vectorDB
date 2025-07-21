import os
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import json
import tiktoken

class CodeElement:
    """Represents a single element of code (function, class, variable, etc.)"""
    def __init__(self, name: str, element_type: str, file_path: str, 
                 start_line: int, end_line: int, content: str, docstring: str = ""):
        self.name = name
        self.element_type = element_type  # 'function', 'class', 'variable', 'import', etc.
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.docstring = docstring or ""
        self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute hash of the code element for change detection"""
        content_str = f"{self.name}:{self.element_type}:{self.content}"
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "element_type": self.element_type,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "docstring": self.docstring,
            "hash": self.hash
        }

class IndexingAgent:
    """Agent responsible for indexing and maintaining codebase knowledge"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB with persistent storage
        persist_dir = str(self.project_root / ".adk_index")
        os.makedirs(persist_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=persist_dir)
        
        # Get or create collections
        try:
            self.code_collection = self.chroma_client.get_collection("code_elements")
        except:
            self.code_collection = self.chroma_client.create_collection(
                name="code_elements",
                metadata={"description": "Code elements from the project"}
            )
        
        try:
            self.file_collection = self.chroma_client.get_collection("file_summaries")
        except:
            self.file_collection = self.chroma_client.create_collection(
                name="file_summaries", 
                metadata={"description": "File-level summaries"}
            )
        
        # Initialize tree-sitter parsers
        self.parsers = self._init_parsers()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def _init_parsers(self) -> Dict[str, tree_sitter.Parser]: #boilerplate code form https://www.youtube.com/watch?v=bP0zl4K_LY8
        """Initialize tree-sitter parsers for different languages"""
        parsers = {}
        
        # Python parser
        python_parser = tree_sitter.Parser()
        python_parser.language = tree_sitter.Language(tspython.language())
        parsers['.py'] = python_parser
        
        # JavaScript parser
        js_parser = tree_sitter.Parser()
        js_parser.language = tree_sitter.Language(tsjavascript.language())
        parsers['.js'] = js_parser
        
        # TypeScript parser
        ts_parser = tree_sitter.Parser()
        ts_parser.language = tree_sitter.Language(tstypescript.language_typescript())
        parsers['.ts'] = ts_parser
        
        # TSX parser
        tsx_parser = tree_sitter.Parser()
        tsx_parser.language = tree_sitter.Language(tstypescript.language_tsx())
        parsers['.tsx'] = tsx_parser
        
        return parsers
    
    def index_codebase(self) -> Dict[str, Any]:
        print("Starting codebase indexing...")
        indexed_files = []
        code_elements = []
        errors = []
        code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.md'}
        code_files = []
        for ext in code_extensions:
            code_files.extend(self.project_root.rglob(f"*{ext}"))
        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.adk_index'}
        code_files = [f for f in code_files if not any(ignore_dir in f.parts for ignore_dir in ignore_dirs)]
        for file_path in code_files:
            result = self._index_file(file_path)
            indexed_files.append(str(file_path.relative_to(self.project_root)))
            code_elements.extend(result['elements'])
        self._store_elements(code_elements)
        return {
            "indexed_files": indexed_files,
            "total_elements": len(code_elements),
            "errors": errors
        }
    
    def _index_file(self, file_path: Path) -> Dict[str, Any]:
        """Index a single file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        file_ext = file_path.suffix
        elements = []
        
        if file_ext in self.parsers:
            # Use tree-sitter for structured parsing
            elements = self._parse_with_tree_sitter(file_path, content, file_ext)
        elif file_ext == '.md':
            # Special handling for markdown files
            elements = self._parse_markdown(file_path, content)
        else:
            # Fallback to simple text chunking
            elements = self._simple_text_chunks(file_path, content)
        
        # Create file summary
        file_summary = self._create_file_summary(file_path, content, elements)
        self._store_file_summary(file_summary)
        
        return {"elements": elements, "summary": file_summary}
    
    def _parse_with_tree_sitter(self, file_path: Path, content: str, file_ext: str) -> List[CodeElement]:
        """Parse file using tree-sitter to extract code elements"""
        parser = self.parsers[file_ext]
        tree = parser.parse(content.encode())
        elements = []
        
        lines = content.split('\n')
        
        def traverse_node(node, depth=0):
            if file_ext == '.py':
                if node.type in ['function_def', 'class_definition', 'import_statement', 'import_from_statement']:
                    element = self._extract_python_element(node, lines, file_path)
                    if element:
                        elements.append(element)
            elif file_ext in ['.js', '.ts', '.tsx']:
                if node.type in ['function_declaration', 'method_definition', 'class_declaration', 'import_statement']:
                    element = self._extract_js_ts_element(node, lines, file_path)
                    if element:
                        elements.append(element)
            
            for child in node.children:
                traverse_node(child, depth + 1)
        
        traverse_node(tree.root_node)
        return elements
    
    def _extract_python_element(self, node, lines: List[str], file_path: Path) -> Optional[CodeElement]:
        """Extract Python code element from tree-sitter node"""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        # Get the element content
        element_lines = lines[start_line-1:end_line]
        content = '\n'.join(element_lines)
        
        if node.type == 'function_def':
            name_node = node.child_by_field_name('name')
            name = lines[name_node.start_point[0]][name_node.start_point[1]:name_node.end_point[1]]
            docstring = self._extract_python_docstring(node, lines) or ""
            return CodeElement(name, 'function', str(file_path), start_line, end_line, content, docstring)
        
        elif node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            name = lines[name_node.start_point[0]][name_node.start_point[1]:name_node.end_point[1]]
            docstring = self._extract_python_docstring(node, lines) or ""
            return CodeElement(name, 'class', str(file_path), start_line, end_line, content, docstring)
        
        elif node.type in ['import_statement', 'import_from_statement']:
            return CodeElement('import', 'import', str(file_path), start_line, end_line, content)
        
        return None
    
    def _extract_js_ts_element(self, node, lines: List[str], file_path: Path) -> Optional[CodeElement]:
        """Extract JavaScript/TypeScript code element from tree-sitter node"""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        element_lines = lines[start_line-1:end_line]
        content = '\n'.join(element_lines)
        
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = lines[name_node.start_point[0]][name_node.start_point[1]:name_node.end_point[1]]
                return CodeElement(name, 'function', str(file_path), start_line, end_line, content)
        
        elif node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = lines[name_node.start_point[0]][name_node.start_point[1]:name_node.end_point[1]]
                return CodeElement(name, 'class', str(file_path), start_line, end_line, content)
        
        elif node.type == 'import_statement':
            return CodeElement('import', 'import', str(file_path), start_line, end_line, content)
        
        return None
    
    def _extract_python_docstring(self, node, lines: List[str]) -> Optional[str]:
        """Extract docstring from Python function or class"""
        # Look for the first string literal in the body
        for child in node.children:
            if child.type == 'block':
                for stmt in child.children:
                    if stmt.type == 'expression_statement':
                        for expr_child in stmt.children:
                            if expr_child.type == 'string':
                                start_line = expr_child.start_point[0]
                                end_line = expr_child.end_point[0]
                                docstring_lines = lines[start_line:end_line+1]
                                return '\n'.join(docstring_lines).strip().strip('"""').strip("'''").strip()
        return None
    
    def _parse_markdown(self, file_path: Path, content: str) -> List[CodeElement]:
        """Parse markdown file into meaningful sections"""
        lines = content.split('\n')
        elements = []
        current_section = []
        current_section_start = 1
        current_heading = "Introduction"
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Check if line is a heading
            if line.strip().startswith('#'):
                # Save previous section if it has content
                if current_section and any(l.strip() for l in current_section):
                    section_content = '\n'.join(current_section)
                    element = CodeElement(
                        name=current_heading,
                        element_type='markdown_section',
                        file_path=str(file_path),
                        start_line=current_section_start,
                        end_line=line_num - 1,
                        content=section_content.strip()
                    )
                    elements.append(element)
                
                # Start new section
                current_heading = line.strip('#').strip()
                current_section = []
                current_section_start = line_num + 1
            else:
                current_section.append(line)
        
        # Add final section
        if current_section and any(l.strip() for l in current_section):
            section_content = '\n'.join(current_section)
            element = CodeElement(
                name=current_heading,
                element_type='markdown_section',
                file_path=str(file_path),
                start_line=current_section_start,
                end_line=len(lines),
                content=section_content.strip()
            )
            elements.append(element)
        
        return elements
    
    def _simple_text_chunks(self, file_path: Path, content: str) -> List[CodeElement]:
        """Fallback chunking for unsupported file types"""
        lines = content.split('\n')
        chunks = []
        
        # Simple chunking by a pre picked size(this could change later on to be dynamic)
        chunk_size = 50  # this worked the best
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i+chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            
            if chunk_content.strip():
                element = CodeElement(
                    name=f"chunk_{i//chunk_size}",
                    element_type='text_chunk',
                    file_path=str(file_path),
                    start_line=i+1,
                    end_line=min(i+chunk_size, len(lines)),
                    content=chunk_content
                )
                chunks.append(element)
        
        return chunks
    
    def _create_file_summary(self, file_path: Path, content: str, elements: List[CodeElement]) -> Dict[str, Any]:
        """Create a summary of the file"""
        # Convert elements_by_type to a string for ChromaDB compatibility
        elements_by_type = {
            element_type: len([e for e in elements if e.element_type == element_type])
            for element_type in set(e.element_type for e in elements)
        }
        elements_by_type_str = ", ".join([f"{k}: {v}" for k, v in elements_by_type.items()]) if elements_by_type else "none"
        
        return {
            "file_path": str(file_path.relative_to(self.project_root)),
            "file_type": file_path.suffix,
            "line_count": len(content.split('\n')),
            "element_count": len(elements),
            "elements_by_type_str": elements_by_type_str,
            "summary": f"File {file_path.name} contains {len(elements)} code elements"
        }
    
    def _store_elements(self, elements: List[CodeElement]):
        """Store code elements in vector database"""
        if not elements:
            return
        
        # Prepare data -> ChromaDB
        documents = []
        metadatas = []
        ids = []
        
        for element in elements:
            # Create searchable text combining name, type, content, and *docstring*
            searchable_text = f"{element.name} {element.element_type}\n{element.content}"
            if element.docstring:
                searchable_text += f"\n{element.docstring}"
            
            documents.append(searchable_text)
            metadatas.append(element.to_dict())
            ids.append(f"{element.file_path}:{element.start_line}:{element.hash}")
        
        # create embeddings
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # Store in ChromaDB
        self.code_collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def _store_file_summary(self, summary: Dict[str, Any]):
        """Store file summary in vector database"""
        document = summary["summary"]
        embedding = self.embedding_model.encode([document])[0].tolist()
        
        self.file_collection.upsert(
            documents=[document],
            embeddings=[embedding],
            metadatas=[summary],
            ids=[summary["file_path"]]
        )
