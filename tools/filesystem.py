"""
File system navigation and operations tool
"""
import os
import pathlib
import shutil
import json
from typing import ClassVar, Literal, Optional
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult, ToolError


class FileSystemTool(BaseAnthropicTool):
    """
    A tool for file system navigation and operations.
    """
    name: ClassVar[Literal["filesystem"]] = "filesystem"
    api_type: ClassVar[Literal["filesystem_20241022"]] = "filesystem_20241022"

    async def __call__(
        self,
        *,
        action: Literal[
            "list_directory",
            "get_current_directory", 
            "change_directory",
            "create_directory",
            "remove_directory",
            "copy_file",
            "move_file",
            "delete_file",
            "get_file_info",
            "find_files",
            "get_file_permissions",
            "set_file_permissions"
        ],
        path: Optional[str] = None,
        destination: Optional[str] = None,
        pattern: Optional[str] = None,
        permissions: Optional[str] = None,
        recursive: bool = False,
        **kwargs
    ) -> ToolResult:
        """Execute file system operations"""
        
        try:
            if action == "list_directory":
                if not path:
                    path = os.getcwd()
                
                if not os.path.exists(path):
                    return ToolResult(error=f"Directory does not exist: {path}")
                
                if not os.path.isdir(path):
                    return ToolResult(error=f"Path is not a directory: {path}")
                
                items = []
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    is_dir = os.path.isdir(item_path)
                    size = os.path.getsize(item_path) if not is_dir else 0
                    items.append({
                        "name": item,
                        "type": "directory" if is_dir else "file",
                        "size": size,
                        "path": item_path
                    })
                
                return ToolResult(output=json.dumps(items, indent=2))
            
            elif action == "get_current_directory":
                return ToolResult(output=os.getcwd())
            
            elif action == "change_directory":
                if not path:
                    return ToolResult(error="Path is required for change_directory")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"Directory does not exist: {path}")
                
                if not os.path.isdir(path):
                    return ToolResult(error=f"Path is not a directory: {path}")
                
                os.chdir(path)
                return ToolResult(output=f"Changed directory to: {os.getcwd()}")
            
            elif action == "create_directory":
                if not path:
                    return ToolResult(error="Path is required for create_directory")
                
                try:
                    if recursive:
                        os.makedirs(path, exist_ok=True)
                    else:
                        os.mkdir(path)
                    return ToolResult(output=f"Created directory: {path}")
                except FileExistsError:
                    return ToolResult(error=f"Directory already exists: {path}")
                except OSError as e:
                    return ToolResult(error=f"Failed to create directory: {e}")
            
            elif action == "remove_directory":
                if not path:
                    return ToolResult(error="Path is required for remove_directory")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"Directory does not exist: {path}")
                
                if not os.path.isdir(path):
                    return ToolResult(error=f"Path is not a directory: {path}")
                
                try:
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        os.rmdir(path)
                    return ToolResult(output=f"Removed directory: {path}")
                except OSError as e:
                    return ToolResult(error=f"Failed to remove directory: {e}")
            
            elif action == "copy_file":
                if not path or not destination:
                    return ToolResult(error="Both path and destination are required for copy_file")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"Source file does not exist: {path}")
                
                try:
                    shutil.copy2(path, destination)
                    return ToolResult(output=f"Copied {path} to {destination}")
                except OSError as e:
                    return ToolResult(error=f"Failed to copy file: {e}")
            
            elif action == "move_file":
                if not path or not destination:
                    return ToolResult(error="Both path and destination are required for move_file")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"Source file does not exist: {path}")
                
                try:
                    shutil.move(path, destination)
                    return ToolResult(output=f"Moved {path} to {destination}")
                except OSError as e:
                    return ToolResult(error=f"Failed to move file: {e}")
            
            elif action == "delete_file":
                if not path:
                    return ToolResult(error="Path is required for delete_file")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"File does not exist: {path}")
                
                if os.path.isdir(path):
                    return ToolResult(error=f"Path is a directory, use remove_directory instead: {path}")
                
                try:
                    os.remove(path)
                    return ToolResult(output=f"Deleted file: {path}")
                except OSError as e:
                    return ToolResult(error=f"Failed to delete file: {e}")
            
            elif action == "get_file_info":
                if not path:
                    return ToolResult(error="Path is required for get_file_info")
                
                if not os.path.exists(path):
                    return ToolResult(error=f"File does not exist: {path}")
                
                stat = os.stat(path)
                info = {
                    "path": path,
                    "type": "directory" if os.path.isdir(path) else "file",
                    "size": stat.st_size,
                    "permissions": oct(stat.st_mode)[-3:],
                    "modified": stat.st_mtime,
                    "created": stat.st_ctime
                }
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "find_files":
                if not path:
                    path = os.getcwd()
                
                if not pattern:
                    return ToolResult(error="Pattern is required for find_files")
                
                import glob
                search_pattern = os.path.join(path, "**", pattern) if recursive else os.path.join(path, pattern)
                matches = glob.glob(search_pattern, recursive=recursive)
                
                results = [{"path": match, "type": "directory" if os.path.isdir(match) else "file"} for match in matches]
                return ToolResult(output=json.dumps(results, indent=2))
            
            else:
                return ToolResult(error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(error=f"File system operation failed: {str(e)}")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }