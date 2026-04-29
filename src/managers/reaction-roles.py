from bot import PoxBot
from src.models import ReactionRoleEntry


class ReactionRoleManager:
    def __init__(self, bot: PoxBot):
        self.bot = bot
    
    async def get_role_id(self, guild_id: int, message_id: int, emoji: str) -> int | None:
        if not self.bot.guild_db:
            return None
        
        config = await self.bot.guild_db.get_config(guild_id)
        for entry in config.reaction_roles:
            if entry.message_id == message_id and entry.emoji == emoji:
                return entry.role_id
        return None

    async def add_mapping(self, guild_id: int, message_id: int, emoji: str, role_id: int):
        if not self.bot.guild_db:
            return None
        
        config = await self.bot.guild_db.get_config(guild_id)
        config.reaction_roles = [
            e for e in config.reaction_roles 
            if not (e.message_id == message_id and e.emoji == emoji)
        ]
        config.reaction_roles.append(ReactionRoleEntry(
            message_id=message_id, emoji=emoji, role_id=role_id
        ))
        await self.bot.guild_db.update_config(guild_id, config)