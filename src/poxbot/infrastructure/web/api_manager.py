from datetime import datetime

import uvicorn
from fastapi import APIRouter, FastAPI
from pytz import UTC


class FastAPIManager:
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.start_time = datetime.now(UTC)
        
        self.app: FastAPI = FastAPI(title="my discord bot API")
        self.router = APIRouter()

        self._register_routes()
        self.app.include_router(self.router)
    
    def _register_routes(self):
        @self.router.get("/health")
        async def get_health():
            uptime = datetime.now(UTC) - self.start_time
            return {
                "status": "healthy",
                "uptime_seconds": round(uptime.total_seconds(), 2),
                "platforms": {
                    "discord": "unknown",
                    "matrix": "unknown",
                },
            }
    
    async def start_server(self):
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        await server.serve()
