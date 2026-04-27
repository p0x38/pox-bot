import discord, websockets, asyncio, json
from discord.ext import commands

from bot import PoxBot

from logger import logger

def get_int(i):
    if not i: return 0
    try:
        return int(i)
    except ValueError:
        return 0

class WebsocketCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.clients = set()
        self.bot.loop.create_task(self.start_ws())
    
    async def start_ws(self):
        await self.bot.wait_until_ready()

        valid_protocol = websockets.Subprotocol(self.bot.auth_code)
        async with websockets.serve(self.ws_handler, "0.0.0.0", 9021, subprotocols=[valid_protocol]):
            logger.info("Websockets server started on port 9021")
            await asyncio.Future()
    
    async def ws_handler(self, websocket):
        if websocket.subprotocol != self.bot.auth_code:
            await websocket.close(1008, "Invalid authorization")
            return
        
        self.clients.add(websocket)

        await websocket.send(json.dumps({
            "type": "status",
            "online": True,
        }))

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    #target_id = get_int(data.get("channel_id", 0))
                    content = data.get("content")

                    if not content: return

                    channel = self.bot.get_channel(1454890969706008818)

                    if channel and isinstance(channel, discord.TextChannel):
                        await channel.send(content.strip())
                        await websocket.send(json.dumps({"type": "res", "code": 200, "reason": "Success"}))
                    else:
                        await websocket.send(json.dumps({"type": "error", "code": 404, "reason": "Channel not found"}))
                except (json.JSONDecodeError, ValueError, TypeError):
                    await websocket.send(json.dumps({
                        "code": 400,
                        "reason": "Invalid JSON"
                    }))
        finally:
            self.clients.remove(websocket)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or not self.clients:
            return
        
        payload = json.dumps({
            "type": "chat",
            "username": message.author.name,
            "content": message.content,
            #"timestamp": int(message.created_at.timestamp())
        })

        websockets.broadcast(self.clients, payload)

async def setup(bot):
    await bot.add_cog(WebsocketCog(bot))