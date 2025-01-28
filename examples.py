from fastapi import FastAPI
from tool_registry_client import tools

app = FastAPI()

# Example endpoint tool
@app.post("/calculate")
@tools.endpoint(
    name="calculator",
    description="Performs basic arithmetic operations",
    input_schema={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
            "x": {"type": "number"},
            "y": {"type": "number"}
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "result": {"type": "number"}
        }
    }
)
async def calculate(operation: str, x: float, y: float):
    if operation == "add":
        return {"result": x + y}
    elif operation == "subtract":
        return {"result": x - y}
    elif operation == "multiply":
        return {"result": x * y}
    elif operation == "divide":
        return {"result": x / y}

# Example function tool
@tools.function(
    name="string_manipulator",
    description="Manipulates strings in various ways",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "operation": {"type": "string", "enum": ["uppercase", "lowercase", "reverse"]}
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "result": {"type": "string"}
        }
    }
)
async def manipulate_string(text: str, operation: str):
    if operation == "uppercase":
        return {"result": text.upper()}
    elif operation == "lowercase":
        return {"result": text.lower()}
    elif operation == "reverse":
        return {"result": text[::-1]}
