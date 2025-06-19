"""
Calculator and math operations tool
"""
import math
import json
import ast
import operator
from typing import ClassVar, Literal, Optional, Union
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult


class CalculatorTool(BaseAnthropicTool):
    """
    A tool for mathematical calculations and operations.
    """
    name: ClassVar[Literal["calculator"]] = "calculator"
    api_type: ClassVar[Literal["calculator_20241022"]] = "calculator_20241022"

    def __init__(self):
        # Safe operators for evaluation
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        # Safe functions
        self.functions = {
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'ceil': math.ceil,
            'floor': math.floor,
            'factorial': math.factorial,
            'degrees': math.degrees,
            'radians': math.radians,
            'pi': math.pi,
            'e': math.e,
        }

    def _safe_eval(self, expression: str):
        """Safely evaluate a mathematical expression"""
        try:
            # Parse the expression
            node = ast.parse(expression, mode='eval')
            return self._eval_node(node.body)
        except Exception as e:
            raise ValueError(f"Invalid expression: {str(e)}")

    def _eval_node(self, node):
        """Recursively evaluate an AST node"""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.Name):
            if node.id in self.functions:
                return self.functions[node.id]
            else:
                raise ValueError(f"Unknown variable: {node.id}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.operators.get(type(node.op))
            if op:
                return op(left, right)
            else:
                raise ValueError(f"Unsupported operation: {type(node.op)}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op = self.operators.get(type(node.op))
            if op:
                return op(operand)
            else:
                raise ValueError(f"Unsupported unary operation: {type(node.op)}")
        elif isinstance(node, ast.Call):
            func = self._eval_node(node.func)
            args = [self._eval_node(arg) for arg in node.args]
            if callable(func):
                return func(*args)
            else:
                raise ValueError(f"Not a function: {func}")
        elif isinstance(node, ast.List):
            return [self._eval_node(elt) for elt in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elt) for elt in node.elts)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    async def __call__(
        self,
        *,
        action: Literal[
            "calculate",
            "solve_equation",
            "convert_units",
            "statistics",
            "matrix_operations",
            "geometry",
            "trigonometry"
        ],
        expression: Optional[str] = None,
        numbers: Optional[list] = None,
        unit_from: Optional[str] = None,
        unit_to: Optional[str] = None,
        value: Optional[float] = None,
        angle_unit: str = "degrees",
        **kwargs
    ) -> ToolResult:
        """Execute mathematical operations"""
        
        try:
            if action == "calculate":
                if not expression:
                    return ToolResult(error="Expression is required for calculate")
                
                try:
                    result = self._safe_eval(expression)
                    return ToolResult(output=f"{expression} = {result}")
                except Exception as e:
                    return ToolResult(error=f"Calculation failed: {str(e)}")
            
            elif action == "statistics":
                if not numbers:
                    return ToolResult(error="Numbers list is required for statistics")
                
                if not isinstance(numbers, list) or not numbers:
                    return ToolResult(error="Numbers must be a non-empty list")
                
                try:
                    numbers = [float(n) for n in numbers]
                    
                    stats = {
                        "count": len(numbers),
                        "sum": sum(numbers),
                        "mean": sum(numbers) / len(numbers),
                        "median": sorted(numbers)[len(numbers) // 2],
                        "min": min(numbers),
                        "max": max(numbers),
                        "range": max(numbers) - min(numbers)
                    }
                    
                    # Calculate variance and standard deviation
                    mean = stats["mean"]
                    variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
                    stats["variance"] = variance
                    stats["standard_deviation"] = math.sqrt(variance)
                    
                    return ToolResult(output=json.dumps(stats, indent=2))
                    
                except ValueError as e:
                    return ToolResult(error=f"Invalid numbers in list: {str(e)}")
            
            elif action == "convert_units":
                if not all([unit_from, unit_to, value is not None]):
                    return ToolResult(error="unit_from, unit_to, and value are required for convert_units")
                
                # Basic unit conversions
                conversions = {
                    # Length
                    ("meters", "feet"): 3.28084,
                    ("feet", "meters"): 0.3048,
                    ("inches", "centimeters"): 2.54,
                    ("centimeters", "inches"): 0.393701,
                    ("kilometers", "miles"): 0.621371,
                    ("miles", "kilometers"): 1.60934,
                    
                    # Weight
                    ("kilograms", "pounds"): 2.20462,
                    ("pounds", "kilograms"): 0.453592,
                    ("grams", "ounces"): 0.035274,
                    ("ounces", "grams"): 28.3495,
                    
                    # Temperature (special handling)
                    ("celsius", "fahrenheit"): lambda c: (c * 9/5) + 32,
                    ("fahrenheit", "celsius"): lambda f: (f - 32) * 5/9,
                    ("celsius", "kelvin"): lambda c: c + 273.15,
                    ("kelvin", "celsius"): lambda k: k - 273.15,
                }
                
                conversion_key = (unit_from.lower(), unit_to.lower())
                
                if conversion_key in conversions:
                    converter = conversions[conversion_key]
                    if callable(converter):
                        result = converter(value)
                    else:
                        result = value * converter
                    
                    return ToolResult(output=f"{value} {unit_from} = {result} {unit_to}")
                else:
                    return ToolResult(error=f"Conversion from {unit_from} to {unit_to} not supported")
            
            elif action == "geometry":
                shape = kwargs.get("shape", "").lower()
                
                if shape == "circle":
                    radius = kwargs.get("radius")
                    if radius is None:
                        return ToolResult(error="Radius is required for circle calculations")
                    
                    area = math.pi * radius ** 2
                    circumference = 2 * math.pi * radius
                    
                    return ToolResult(output=json.dumps({
                        "shape": "circle",
                        "radius": radius,
                        "area": area,
                        "circumference": circumference
                    }, indent=2))
                
                elif shape == "rectangle":
                    width = kwargs.get("width")
                    height = kwargs.get("height")
                    if width is None or height is None:
                        return ToolResult(error="Width and height are required for rectangle calculations")
                    
                    area = width * height
                    perimeter = 2 * (width + height)
                    diagonal = math.sqrt(width ** 2 + height ** 2)
                    
                    return ToolResult(output=json.dumps({
                        "shape": "rectangle",
                        "width": width,
                        "height": height,
                        "area": area,
                        "perimeter": perimeter,
                        "diagonal": diagonal
                    }, indent=2))
                
                elif shape == "triangle":
                    base = kwargs.get("base")
                    height = kwargs.get("height")
                    if base is None or height is None:
                        return ToolResult(error="Base and height are required for triangle calculations")
                    
                    area = 0.5 * base * height
                    
                    return ToolResult(output=json.dumps({
                        "shape": "triangle",
                        "base": base,
                        "height": height,
                        "area": area
                    }, indent=2))
                
                else:
                    return ToolResult(error=f"Unsupported shape: {shape}")
            
            elif action == "trigonometry":
                if value is None:
                    return ToolResult(error="Value is required for trigonometry calculations")
                
                # Convert angle to radians if needed
                if angle_unit.lower() == "degrees":
                    angle_rad = math.radians(value)
                else:
                    angle_rad = value
                
                trig_values = {
                    "angle": value,
                    "angle_unit": angle_unit,
                    "sin": math.sin(angle_rad),
                    "cos": math.cos(angle_rad),
                    "tan": math.tan(angle_rad),
                    "asin": math.degrees(math.asin(math.sin(angle_rad))) if angle_unit.lower() == "degrees" else math.asin(math.sin(angle_rad)),
                    "acos": math.degrees(math.acos(math.cos(angle_rad))) if angle_unit.lower() == "degrees" else math.acos(math.cos(angle_rad)),
                    "atan": math.degrees(math.atan(math.tan(angle_rad))) if angle_unit.lower() == "degrees" else math.atan(math.tan(angle_rad))
                }
                
                return ToolResult(output=json.dumps(trig_values, indent=2))
            
            else:
                return ToolResult(error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(error=f"Math operation failed: {str(e)}")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }