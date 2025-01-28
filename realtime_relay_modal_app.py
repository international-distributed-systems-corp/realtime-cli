from modal import Image, Stub, asgi_app
from fastapi import FastAPI
import uvicorn

# Create FastAPI app
web_app = FastAPI()

# Create Modal app and image
app = Stub("realtime-relay")
image = (
    Image.debian_slim()
    .pip_install(["fastapi", "uvicorn", "websockets", "requests"])
)

@app.function(
    image=image,
    keep_warm=1
)
@asgi_app(label="realtime-relay")
def fastapi_app():
    return web_app

if __name__ == "__main__":
    app.serve()
