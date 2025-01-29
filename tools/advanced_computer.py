import asyncio
import pyperclip
from typing import Literal, Optional
from dataclasses import dataclass
from .base import BaseAnthropicTool, ToolError, ToolResult

@dataclass
class WindowInfo:
    """Information about a window"""
    id: str
    title: str
    app: str
    position: tuple[int, int]
    size: tuple[int, int]

class AdvancedComputerTool(BaseAnthropicTool):
    """Advanced computer control capabilities"""
    
    name: Literal["advanced_computer"] = "advanced_computer"
    
    async def __call__(
        self,
        *,
        action: Literal[
            "get_windows",
            "focus_window", 
            "move_window",
            "resize_window",
            "get_clipboard",
            "set_clipboard",
            "press_key_sequence",
            "smooth_mouse_move"
        ],
        window_id: Optional[str] = None,
        position: Optional[tuple[int, int]] = None,
        size: Optional[tuple[int, int]] = None,
        text: Optional[str] = None,
        keys: Optional[list[str]] = None,
        coordinate: Optional[list[int]] = None,
        duration: Optional[float] = None,
        **kwargs
    ) -> ToolResult:
        """Execute advanced computer control actions"""
        
        if action == "get_windows":
            # Get list of windows using applescript
            script = """
            tell application "System Events"
                set windowList to {}
                repeat with proc in processes
                    if exists (window 1 of proc) then
                        set end of windowList to {
                            id: id of window 1 of proc,
                            title: name of window 1 of proc,
                            app: name of proc
                        }
                    end if
                end repeat
                return windowList
            end tell
            """
            result = await self._run_applescript(script)
            return ToolResult(output=str(result))
            
        elif action == "focus_window":
            if not window_id:
                raise ToolError("window_id required for focus_window")
            script = f"""
            tell application "System Events"
                set frontmost of process "{window_id}" to true
            end tell
            """
            await self._run_applescript(script)
            return ToolResult(output=f"Focused window {window_id}")
            
        elif action == "move_window":
            if not window_id or not position:
                raise ToolError("window_id and position required for move_window")
            x, y = position
            script = f"""
            tell application "System Events"
                set position of window 1 of process "{window_id}" to {{{x}, {y}}}
            end tell
            """
            await self._run_applescript(script)
            return ToolResult(output=f"Moved window {window_id} to {position}")
            
        elif action == "resize_window":
            if not window_id or not size:
                raise ToolError("window_id and size required for resize_window") 
            w, h = size
            script = f"""
            tell application "System Events"
                set size of window 1 of process "{window_id}" to {{{w}, {h}}}
            end tell
            """
            await self._run_applescript(script)
            return ToolResult(output=f"Resized window {window_id} to {size}")
            
        elif action == "get_clipboard":
            content = pyperclip.paste()
            return ToolResult(output=content)
            
        elif action == "set_clipboard":
            if not text:
                raise ToolError("text required for set_clipboard")
            pyperclip.copy(text)
            return ToolResult(output=f"Set clipboard to: {text}")
            
        elif action == "press_key_sequence":
            if not keys:
                raise ToolError("keys required for press_key_sequence")
            import pyautogui
            for key in keys:
                await asyncio.to_thread(pyautogui.press, key)
                await asyncio.sleep(0.05)
            return ToolResult(output=f"Pressed keys: {keys}")
            
        elif action == "smooth_mouse_move":
            if not coordinate or not duration:
                raise ToolError("coordinate and duration required for smooth_mouse_move")
            import pyautogui
            x, y = coordinate
            await asyncio.to_thread(
                pyautogui.moveTo, 
                x, y,
                duration=duration,
                tween=pyautogui.easeInOutQuad
            )
            return ToolResult(output=f"Smoothly moved mouse to {coordinate}")
            
        raise ToolError(f"Unknown action: {action}")
        
    async def _run_applescript(self, script: str) -> str:
        """Run an AppleScript and return the result"""
        import subprocess
        proc = await asyncio.create_subprocess_exec(
            'osascript', 
            '-e', 
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if stderr:
            raise ToolError(f"AppleScript error: {stderr.decode()}")
        return stdout.decode()

    def to_params(self):
        return {
            "name": self.name,
            "description": "Advanced computer control including windows, clipboard, and smooth movements",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "get_windows",
                            "focus_window",
                            "move_window", 
                            "resize_window",
                            "get_clipboard",
                            "set_clipboard",
                            "press_key_sequence",
                            "smooth_mouse_move"
                        ]
                    },
                    "window_id": {"type": "string"},
                    "position": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "size": {
                        "type": "array", 
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "text": {"type": "string"},
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "coordinate": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "duration": {"type": "number"}
                },
                "required": ["action"]
            }
        }
