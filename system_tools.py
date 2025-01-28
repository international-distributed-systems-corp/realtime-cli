import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SystemTools:
    """Provides safe access to common system operations"""
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        
    def run_command(self, command: Union[str, List[str]], 
                   capture_output: bool = True,
                   check: bool = True,
                   shell: bool = False) -> subprocess.CompletedProcess:
        """Run a system command safely"""
        try:
            if isinstance(command, str) and not shell:
                command = command.split()
            
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                check=check,
                shell=shell,
                cwd=self.working_dir
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.cmd}")
            logger.error(f"Output: {e.output}")
            raise
            
    def list_directory(self, path: Optional[str] = None) -> List[str]:
        """List contents of directory"""
        target = Path(path) if path else self.working_dir
        return os.listdir(target)
        
    def read_file(self, path: str) -> str:
        """Read contents of a file"""
        with open(Path(self.working_dir) / path) as f:
            return f.read()
            
    def write_file(self, path: str, content: str) -> None:
        """Write content to a file"""
        with open(Path(self.working_dir) / path, 'w') as f:
            f.write(content)
            
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        return (Path(self.working_dir) / path).exists()
        
    def copy_file(self, src: str, dst: str) -> None:
        """Copy a file"""
        shutil.copy2(Path(self.working_dir) / src, 
                    Path(self.working_dir) / dst)
                    
    def move_file(self, src: str, dst: str) -> None:
        """Move/rename a file"""
        shutil.move(Path(self.working_dir) / src,
                   Path(self.working_dir) / dst)
                   
    def delete_file(self, path: str) -> None:
        """Delete a file"""
        (Path(self.working_dir) / path).unlink()
        
    def make_directory(self, path: str) -> None:
        """Create a directory"""
        (Path(self.working_dir) / path).mkdir(parents=True, exist_ok=True)
        
    def remove_directory(self, path: str) -> None:
        """Remove a directory and its contents"""
        shutil.rmtree(Path(self.working_dir) / path)
        
    def get_environment_variable(self, name: str) -> Optional[str]:
        """Get environment variable value"""
        return os.environ.get(name)
        
    def set_environment_variable(self, name: str, value: str) -> None:
        """Set environment variable"""
        os.environ[name] = value
