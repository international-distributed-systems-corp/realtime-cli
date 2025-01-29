import sys
import json
import time
import asyncio
from typing import Optional, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.panel import Panel

console = Console()

def print_event(direction: str, event: Dict[Any, Any]) -> None:
    """Pretty print events with color coding"""
    if direction == "sent":
        color = "green"
        prefix = "→"
    else:
        color = "blue" 
        prefix = "←"
    
    console.print(f"\n[{color}]{prefix} {event['type']}[/{color}]")
    if "error" in event:
        console.print(Panel(str(event["error"]), style="red"))
    else:
        console.print(json.dumps(event, indent=2))

class StreamingTextAccumulator:
    """Accumulates streaming text content with live updates"""
    def __init__(self):
        self.buffer = []
        self.live = Live("", refresh_per_second=4)
        self.transcript = ""
        
    def start(self):
        self.live.start()
        
    def update(self, text: str):
        self.buffer.append(text)
        self.live.update("".join(self.buffer))
        
    def stop(self):
        self.live.stop()
        return "".join(self.buffer)

class ProgressSpinner:
    """Shows a spinner with status text"""
    def __init__(self, text: str):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        )
        self.task_id = self.progress.add_task(text, total=None)
        
    def __enter__(self):
        self.progress.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.stop()

async def handle_interrupt(ws):
    """Clean shutdown on Ctrl+C"""
    console.print("\n[yellow]Shutting down...[/yellow]")
    if ws:
        try:
            await ws.close()
        except:
            pass
    # Use asyncio.get_event_loop().stop() instead of sys.exit()
    asyncio.get_event_loop().stop()
