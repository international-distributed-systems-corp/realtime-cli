"""
System monitoring and process management tool
"""
import os
import psutil
import json
import platform
from typing import ClassVar, Literal, Optional, List
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult


class SystemMonitorTool(BaseAnthropicTool):
    """
    A tool for system monitoring and process management.
    """
    name: ClassVar[Literal["system_monitor"]] = "system_monitor"
    api_type: ClassVar[Literal["system_monitor_20241022"]] = "system_monitor_20241022"

    async def __call__(
        self,
        *,
        action: Literal[
            "get_system_info",
            "get_cpu_info",
            "get_memory_info", 
            "get_disk_info",
            "get_network_info",
            "list_processes",
            "get_process_info",
            "kill_process",
            "get_running_services",
            "get_environment_variables",
            "get_user_info",
            "get_boot_time"
        ],
        process_id: Optional[int] = None,
        process_name: Optional[str] = None,
        limit: int = 20,
        **kwargs
    ) -> ToolResult:
        """Execute system monitoring operations"""
        
        try:
            if action == "get_system_info":
                info = {
                    "platform": platform.platform(),
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "hostname": platform.node(),
                    "python_version": platform.python_version(),
                    "cpu_count": psutil.cpu_count(),
                    "cpu_count_logical": psutil.cpu_count(logical=True)
                }
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "get_cpu_info":
                cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
                cpu_freq = psutil.cpu_freq()
                
                info = {
                    "cpu_percent_total": psutil.cpu_percent(interval=1),
                    "cpu_percent_per_core": cpu_percent,
                    "cpu_count_physical": psutil.cpu_count(logical=False),
                    "cpu_count_logical": psutil.cpu_count(logical=True),
                    "cpu_frequency": {
                        "current": cpu_freq.current if cpu_freq else None,
                        "min": cpu_freq.min if cpu_freq else None,
                        "max": cpu_freq.max if cpu_freq else None
                    } if cpu_freq else None,
                    "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
                }
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "get_memory_info":
                virtual_mem = psutil.virtual_memory()
                swap_mem = psutil.swap_memory()
                
                info = {
                    "virtual_memory": {
                        "total": virtual_mem.total,
                        "available": virtual_mem.available,
                        "used": virtual_mem.used,
                        "free": virtual_mem.free,
                        "percent": virtual_mem.percent
                    },
                    "swap_memory": {
                        "total": swap_mem.total,
                        "used": swap_mem.used,
                        "free": swap_mem.free,
                        "percent": swap_mem.percent
                    }
                }
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "get_disk_info":
                disk_usage = psutil.disk_usage('/')
                disk_io = psutil.disk_io_counters()
                disk_partitions = psutil.disk_partitions()
                
                info = {
                    "disk_usage_root": {
                        "total": disk_usage.total,
                        "used": disk_usage.used,
                        "free": disk_usage.free,
                        "percent": (disk_usage.used / disk_usage.total) * 100
                    },
                    "disk_io": {
                        "read_count": disk_io.read_count,
                        "write_count": disk_io.write_count,
                        "read_bytes": disk_io.read_bytes,
                        "write_bytes": disk_io.write_bytes
                    } if disk_io else None,
                    "partitions": [
                        {
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype
                        } for partition in disk_partitions
                    ]
                }
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "get_network_info":
                net_io = psutil.net_io_counters()
                net_connections = psutil.net_connections(kind='inet')
                
                info = {
                    "network_io": {
                        "bytes_sent": net_io.bytes_sent,
                        "bytes_recv": net_io.bytes_recv,
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv,
                        "errin": net_io.errin,
                        "errout": net_io.errout,
                        "dropin": net_io.dropin,
                        "dropout": net_io.dropout
                    },
                    "active_connections": len(net_connections),
                    "connections_by_status": {}
                }
                
                # Count connections by status
                for conn in net_connections:
                    status = conn.status
                    info["connections_by_status"][status] = info["connections_by_status"].get(status, 0) + 1
                
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "list_processes":
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by CPU usage
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                
                return ToolResult(output=json.dumps(processes[:limit], indent=2))
            
            elif action == "get_process_info":
                if not process_id and not process_name:
                    return ToolResult(error="Either process_id or process_name is required")
                
                try:
                    if process_id:
                        proc = psutil.Process(process_id)
                    else:
                        # Find process by name
                        processes = [p for p in psutil.process_iter() if p.name() == process_name]
                        if not processes:
                            return ToolResult(error=f"No process found with name: {process_name}")
                        proc = processes[0]
                    
                    info = {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "status": proc.status(),
                        "cpu_percent": proc.cpu_percent(),
                        "memory_percent": proc.memory_percent(),
                        "memory_info": proc.memory_info()._asdict(),
                        "create_time": proc.create_time(),
                        "num_threads": proc.num_threads(),
                        "cmdline": proc.cmdline() if proc.cmdline() else [],
                        "cwd": proc.cwd() if hasattr(proc, 'cwd') else None
                    }
                    
                    return ToolResult(output=json.dumps(info, indent=2))
                    
                except psutil.NoSuchProcess:
                    return ToolResult(error=f"Process not found: {process_id or process_name}")
                except psutil.AccessDenied:
                    return ToolResult(error=f"Access denied to process: {process_id or process_name}")
            
            elif action == "kill_process":
                if not process_id and not process_name:
                    return ToolResult(error="Either process_id or process_name is required")
                
                try:
                    if process_id:
                        proc = psutil.Process(process_id)
                    else:
                        # Find process by name
                        processes = [p for p in psutil.process_iter() if p.name() == process_name]
                        if not processes:
                            return ToolResult(error=f"No process found with name: {process_name}")
                        proc = processes[0]
                    
                    proc_name = proc.name()
                    proc_pid = proc.pid
                    proc.terminate()
                    
                    return ToolResult(output=f"Terminated process: {proc_name} (PID: {proc_pid})")
                    
                except psutil.NoSuchProcess:
                    return ToolResult(error=f"Process not found: {process_id or process_name}")
                except psutil.AccessDenied:
                    return ToolResult(error=f"Access denied to terminate process: {process_id or process_name}")
            
            elif action == "get_boot_time":
                boot_time = psutil.boot_time()
                from datetime import datetime
                boot_datetime = datetime.fromtimestamp(boot_time)
                
                info = {
                    "boot_time_timestamp": boot_time,
                    "boot_time_formatted": boot_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    "uptime_seconds": psutil.time.time() - boot_time
                }
                
                return ToolResult(output=json.dumps(info, indent=2))
            
            elif action == "get_environment_variables":
                env_vars = dict(os.environ)
                return ToolResult(output=json.dumps(env_vars, indent=2))
            
            elif action == "get_user_info":
                users = psutil.users()
                user_info = [
                    {
                        "name": user.name,
                        "terminal": user.terminal,
                        "host": user.host,
                        "started": user.started
                    } for user in users
                ]
                
                return ToolResult(output=json.dumps(user_info, indent=2))
            
            else:
                return ToolResult(error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(error=f"System monitoring operation failed: {str(e)}")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }