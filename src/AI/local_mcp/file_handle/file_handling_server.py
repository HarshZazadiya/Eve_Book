from fastmcp import FastMCP
from pathlib import Path
import base64
import os
from datetime import datetime
from pypdf import PdfReader  # Changed from PyPDF2
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

mcp = FastMCP("filesystem")

WORKSPACE = Path("D:/internship_project/eve_book/src/ai/local_mcp/file_handle/workspace")
WORKSPACE.mkdir(exist_ok=True)

def is_base64_encoded(content: str) -> bool:
    """Check if a string appears to be base64 encoded"""
    try:
        if not content or len(content) < 20:
            return False
        
        import re
        if not re.match(r'^[A-Za-z0-9+/=]+$', content):
            return False
        
        decoded = base64.b64decode(content)
        
        try:
            text = decoded.decode('utf-8')
            if any(c.isprintable() for c in text[:100]):
                return True
        except:
            pass
        
        if content.startswith('JVBERi0') or decoded.startswith(b'%PDF'):
            return True
            
    except:
        pass
    return False

def decode_content(content: str, filename: str = "") -> dict:
    """Decode base64 content and return user-readable info"""
    result = {
        "filename": filename,
        "original_size": len(content),
        "was_encoded": False,
        "type": "unknown",
        "readable_content": None
    }
    
    if not is_base64_encoded(content):
        result["type"] = "text"
        result["readable_content"] = content
        return result
    
    try:
        decoded_bytes = base64.b64decode(content)
        result["was_encoded"] = True
        result["decoded_size"] = len(decoded_bytes)
        
        if content.startswith('JVBERi0') or decoded_bytes.startswith(b'%PDF'):
            result["type"] = "pdf"
            try:
                pdf_file = io.BytesIO(decoded_bytes)
                pdf_reader = PdfReader(pdf_file)
                text_content = ""
                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_content += f"\n--- Page {i+1} ---\n{page_text}\n"
                
                if text_content:
                    result["readable_content"] = text_content[:10000]
                    if len(text_content) > 10000:
                        result["readable_content"] += "\n\n[Content truncated for length]"
                else:
                    result["readable_content"] = "[No extractable text in PDF]"
            except Exception as e:
                result["readable_content"] = f"[Error parsing PDF: {e}]"
        
        elif decoded_bytes.startswith(b'\x89PNG') or decoded_bytes.startswith(b'\xff\xd8'):
            result["type"] = "image"
            result["readable_content"] = f"[Image file: {filename} - {len(decoded_bytes)} bytes]"
        
        else:
            try:
                text = decoded_bytes.decode('utf-8')
                if text and any(c.isprintable() for c in text[:100]):
                    result["type"] = "text"
                    result["readable_content"] = text[:10000]
                    if len(text) > 10000:
                        result["readable_content"] += "\n\n[Content truncated for length]"
                else:
                    result["type"] = "binary"
                    result["readable_content"] = f"[Binary file: {filename} - {len(decoded_bytes)} bytes]"
            except:
                result["type"] = "binary"
                result["readable_content"] = f"[Binary file: {filename} - {len(decoded_bytes)} bytes]"
    
    except Exception as e:
        result["readable_content"] = f"[Error decoding file: {e}]"
    
    return result

@mcp.tool()
def current_directory() -> str:
    """Returns the default workspace directory path."""
    return f"Current workspace directory: {WORKSPACE}"

@mcp.tool()
def change_directory(filepath: str) -> str:
    """Change the current workspace directory."""
    global WORKSPACE
    new_path = Path(filepath)
    new_path.mkdir(parents=True, exist_ok=True)
    WORKSPACE = new_path
    return f"✅ Workspace directory changed to: {WORKSPACE}"

@mcp.tool()
def list_files() -> str:
    """List all files and folders in the current workspace."""
    target = WORKSPACE

    if not target.is_dir():
        return f"❌ Error: Path is not a directory: {WORKSPACE}"
    if not target.exists():
        return f"❌ Error: Path does not exist: {WORKSPACE}"
    
    files = list(target.iterdir())
    if not files:
        return f"📁 Current directory ({WORKSPACE}) is empty."
    
    folders = [p for p in files if p.is_dir()]
    regular_files = [p for p in files if p.is_file()]
    
    result = f"📁 Current directory: {WORKSPACE}\n\n"
    
    if folders:
        result += "📂 Folders:\n"
        for f in folders:
            result += f"  📁 {f.name}/\n"
    
    if regular_files:
        result += "\n📄 Files:\n"
        for f in regular_files:
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"
            result += f"  📄 {f.name} ({size_str})\n"
    
    result += f"\nTotal: {len(folders)} folders, {len(regular_files)} files"
    return result

BINARY_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".exe", ".dll", ".so", ".dmg",
    ".pkl", ".pickle", ".joblib",
    ".db", ".sqlite", ".mdb"
}

def is_binary(filename: str) -> bool:
    return Path(filename).suffix.lower() in BINARY_EXTENSIONS

@mcp.tool()
def read_file(filename: str) -> str:
    """Read the contents of a file and automatically decode if needed."""
    path = WORKSPACE / filename
    
    if not path.exists():
        return f"❌ Error: File '{filename}' not found in {WORKSPACE}"
    
    try:
        file_bytes = path.read_bytes()
        
        try:
            content = file_bytes.decode('utf-8')
            if is_base64_encoded(content):
                decoded = decode_content(content, filename)
                return decoded.get('readable_content', content)
            else:
                if len(content) > 5000:
                    return f"{content[:5000]}\n\n...[Content truncated, showing first 5000 chars]"
                else:
                    return content
        except UnicodeDecodeError:
            content = base64.b64encode(file_bytes).decode('utf-8')
            decoded = decode_content(content, filename)
            return decoded.get('readable_content', f"Binary file: {filename}")
    
    except Exception as e:
        return f"❌ Error reading file: {e}"

@mcp.tool()
def create_pdf(filename: str, content: str) -> str:
    """
    Creates a PDF file with the given content inside the WORKSPACE directory.

    Args:
        filename: Name of the PDF file (with or without .pdf extension)
        content: Text content to write into the PDF

    Returns:
        Full path to the created PDF file
    """
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    output_path = os.path.join(WORKSPACE, filename)

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    for line in content.split("\n"):
        if line.strip():
            story.append(Paragraph(line, styles["Normal"]))
        else:
            story.append(Spacer(1, 12))

    doc.build(story)
    return output_path
      
@mcp.tool()
def create_text_file(filename: str, content: str) -> str:
    """Create a normal file with the given"""
    
    filepath = WORKSPACE / filename
    filepath.write_text(content, encoding='utf-8')
    
    return f"""✅ TEXT FILE CREATED: {filename}
                📁 Location: {filepath}
                📊 Size: {len(content)} bytes
                📝 Content: {content[:200]}
            """


@mcp.tool()
def update_file(filename: str, content: str, is_base64: bool = False) -> str:
    """Overwrite an existing file."""
    try:
        path = WORKSPACE / filename
        
        if not str(path.resolve()).startswith(str(WORKSPACE.resolve())):
            return "❌ Error: Access denied - file outside workspace"
        
        if not path.exists():
            return f"❌ Error: File '{filename}' not found"
        
        # Handle boolean properly
        should_decode = is_base64
        if isinstance(should_decode, str):
            should_decode = should_decode.lower() == "true"
        
        if should_decode or is_base64_encoded(content):
            try:
                decoded = base64.b64decode(content)
                path.write_bytes(decoded)
                return f"✅ File updated: {filename}\nNew size: {len(decoded)} bytes"
            except Exception as e:
                return f"❌ Failed to decode base64: {e}"
        else:
            if not isinstance(content, str):
                content = str(content)
            path.write_text(content, encoding="utf-8")
            return f"✅ File updated: {filename}\nNew size: {len(content)} characters"
            
    except Exception as e:
        return f"❌ Error updating file: {e}"

@mcp.tool()
def delete_file(filename: str) -> str:
    """Delete a file from the workspace."""
    try:
        path = WORKSPACE / filename
        
        if not str(path.resolve()).startswith(str(WORKSPACE.resolve())):
            return "❌ Error: Access denied - file outside workspace"
        
        if not path.exists():
            return f"❌ Error: File '{filename}' not found"
        
        if path.is_file():
            path.unlink()
            return f"✅ File deleted: {filename}"
        else:
            return f"❌ Error: '{filename}' is a directory, not a file"
    
    except Exception as e:
        return f"❌ Error deleting file: {e}"

@mcp.tool()
def file_info(filename: str) -> str:
    """Get detailed information about a file."""
    try:
        path = WORKSPACE / filename
        
        if not str(path.resolve()).startswith(str(WORKSPACE.resolve())):
            return "❌ Error: Access denied - file outside workspace"
        
        if not path.exists():
            return f"❌ Error: File '{filename}' not found"
        
        stat = path.stat()
        
        result = f"📄 File Information: {filename}\n"
        result += "=" * 40 + "\n"
        result += f"📁 Location: {path.relative_to(WORKSPACE)}\n"
        result += f"📊 Size: {stat.st_size:,} bytes"
        
        if stat.st_size < 1024:
            pass
        elif stat.st_size < 1024 * 1024:
            result += f" ({stat.st_size/1024:.1f} KB)"
        else:
            result += f" ({stat.st_size/(1024*1024):.1f} MB)"
        result += "\n"
        
        result += f"📅 Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"🔄 Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"📌 Type: {'Directory' if path.is_dir() else 'File'}\n"
        
        if path.is_file():
            ext = path.suffix.lower()
            result += f"🔤 Extension: {ext if ext else 'No extension'}\n"
            
            if ext == '.pdf':
                try:
                    pdf_reader = PdfReader(path)
                    result += f"📖 Pages: {len(pdf_reader.pages)}\n"
                except:
                    pass
            
            if not is_binary(filename):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        preview = f.read(500)
                    result += f"\n📝 Preview (first 500 chars):\n{preview}"
                    if len(preview) == 500:
                        result += "..."
                except:
                    pass
        
        return result
        
    except Exception as e:
        return f"❌ Error getting file info: {e}"

if __name__ == "__main__":
    print("🚀 File System MCP Server Starting...")
    print(f"📁 Workspace: {WORKSPACE}")
    print("🌐 Listening on http://127.0.0.1:8001/sse")
    mcp.run(transport="sse", host="127.0.0.1", port=8001)


    