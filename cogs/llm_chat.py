from collections import deque
from enum import StrEnum
from typing import Any, Optional
import time
import asyncio
import json
import os

from discord import (
    Color,
    DMChannel,
    Embed,
    GroupChannel,
    Message,
    PartialMessageable,
    AllowedMentions,
    StageChannel,
    TextChannel,
    Thread,
    VoiceChannel,
    app_commands,
)
from discord.ext import commands
from openrouter import OpenRouter

import stuff
from bot import PoxBot
from logger import logger

class LLMProviderType(StrEnum):
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"

class LLMChatCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.api_key = stuff.get_openrouter_api_key()
        self.history: dict[int, deque[dict[str, Any]]] = {}
        self.history_limit = 50
        self.persistence_dir = os.path.join("data", "llm_history")
        os.makedirs(self.persistence_dir, exist_ok=True)
        self.cooldowns: dict[int, float] = {}
        self.cooldown_seconds = 8.0
        self.locks: dict[int, asyncio.Lock] = {}
    
    async def format_discord_message(self, message: Message) -> dict[str, Any]:
        message_author = message.author
        message_content = message.content.strip()
        if message_content:
            # remove bot mentions from message content
            message_content = message_content.replace(f"<@{self.bot.user.id}> ", "").replace(f"<@!{self.bot.user.id}> ", "") # type: ignore
        
        role_type = "assistant" if message_author == self.bot.user else "user"
        role_content = ""
        
        formatted_message_author = message_author.display_name
        formatted_message_content = message_content if message_content else "Empty message"
        formatted_referenced_message_author = None
        referenced_message_author = None
        data = {} # {"role": "<assistant|user>", "content": "<content>"}
        
        if message.reference and isinstance(message.reference.resolved, Message):
            referenced_message = message.reference.resolved
            formatted_referenced_message_author = (
                "You"
                if referenced_message.author == self.bot.user
                else referenced_message.author.display_name
            )
        
        if message.attachments:
            # include only filenames to avoid exposing URLs
            attachments = ", ".join(a.filename for a in message.attachments)
            formatted_message_content = f"{message_content} *includes attachments: {attachments}*"
        
        if formatted_referenced_message_author:
            role_content = f"[{formatted_message_author} -> {formatted_referenced_message_author}] {formatted_message_content}"
        else:
            # Priority: @everyone > i were mentioned > normal
            if message.mention_everyone:
                role_content = f"[{formatted_message_author} -> @everyone] {formatted_message_content}"
            elif len(message.mentions) == 1 and self.bot.user in message.mentions:
                role_content = f"[{formatted_message_author} -> You] {formatted_message_content}"
            else:
                role_content = f"[{formatted_message_author}] {formatted_message_content}"
        
        data["role"] = role_type
        data["content"] = role_content
        
        return data

    def _sanitize_history_item(self, item: Any) -> dict[str, Any]:
        # Ensure history entries are dicts with 'role' and 'content' strings.
        if asyncio.iscoroutine(item):
            logger.warning("History contains coroutine item; converting to string")
            try:
                item = {"role": "assistant", "content": f"<coroutine {item!r}>"}
            except Exception:
                item = {"role": "assistant", "content": "<coroutine>"}

        if not isinstance(item, dict):
            return {"role": "assistant", "content": str(item)}

        role = item.get("role", "assistant")
        content = item.get("content", "")
        if asyncio.iscoroutine(content):
            logger.warning("History item content is coroutine; converting to string")
            content = f"<coroutine {content!r}>"

        return {"role": str(role), "content": str(content)}
    
    async def generate_response(self, input_data: dict):
        if not input_data: raise RuntimeError("Input data must not be empty")
        
        provider_type = input_data.get("provider")
        llm_model = input_data.get("model")
        query = input_data.get("query")
        
        if not provider_type: raise ValueError("Provider type must not be empty")
        if not llm_model: raise ValueError("LLM model must not be empty")
        if not query: raise ValueError("Query must not be empty")
        
        if not isinstance(provider_type, str): raise TypeError("Provider type must be a string")
        if not isinstance(llm_model, str): raise TypeError("LLM model must be a string")
        
        match provider_type:
            case LLMProviderType.OPENROUTER.value:
                if not isinstance(query, list):
                    raise TypeError("Query must be a list")

                try:
                    async with OpenRouter(api_key=self.api_key) as client:
                        logger.info("Requesting response to OpenRouter...")
                        thinking = False
                        generating = False
                        response = await client.chat.send_async(
                            model=llm_model,
                            messages=query,
                            stream=True
                        )

                        async for chunk in response:
                            if not thinking:
                                thinking = True
                                logger.info("LLM is thinking...")

                            if chunk.choices and chunk.choices[0].delta.content:
                                if not generating:
                                    generating = True
                                    logger.info("LLM is generating response...")

                                yield chunk.choices[0].delta.content
                except Exception as e:
                    msg = str(e)
                    if "401" in msg or "Unauthorized" in msg or "invalid api key" in msg.lower():
                        logger.error("Authentication error when contacting OpenRouter: %s", msg)
                        raise RuntimeError("Authentication failed when contacting the LLM provider. Check API key.") from e
                    if "timeout" in msg.lower() or isinstance(e, asyncio.TimeoutError):
                        logger.warning("Timeout while generating response: %s", msg)
                        raise RuntimeError("The LLM request timed out. Try again later.") from e
                    logger.exception(f"Failed to generate response: {e}")
                    raise RuntimeError(f"Failed to generate response: {e}") from e
            case _:
                raise ValueError(f"Unknown provider type: {provider_type}")
    
    async def populate_channel_cache(self, channel: TextChannel | StageChannel | VoiceChannel | Thread | DMChannel | GroupChannel | PartialMessageable, limit: int = 10):
        if channel.id not in self.history:
            self.history[channel.id] = deque(maxlen=self.history_limit)

        # try load persisted history first
        file_path = os.path.join(self.persistence_dir, f"{channel.id}.json")
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for item in loaded:
                        self.history[channel.id].append(self._sanitize_history_item(item))
            except Exception as e:
                logger.exception(f"Failed to load persisted history for {channel.id}: {e}")

        try:
            async for message in channel.history(limit=limit, oldest_first=True):
                data = await self.format_discord_message(message)
                # append in chronological order: oldest -> newest
                self.history[channel.id].append(self._sanitize_history_item(data))
        except Exception as e:
            logger.exception(f"Failed to populate channel cache: {e}")

        # persist current in-memory history (trim to limit)
        try:
            to_save = list(self.history[channel.id])[-self.history_limit:]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"Failed to persist history for {channel.id}: {e}")
    
    async def respond(self, message: Message, provider: str, model: str, include_history: bool = False):
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        output = ""

        if not self.bot.user:
            raise RuntimeError("Bot user is not set")

        if include_history:
            try:
                if message.channel.id not in self.history:
                    await self.populate_channel_cache(message.channel)

                for data in self.history[message.channel.id]:
                    messages.append(self._sanitize_history_item(data))
            except Exception as e:
                raise RuntimeError(f"Failed to get chat history: {e}") from e

        data = await self.format_discord_message(message)
        messages.append(self._sanitize_history_item(data))

        # ensure history deque exists and append in chronological order
        if message.channel.id not in self.history:
            self.history[message.channel.id] = deque(maxlen=self.history_limit)
        self.history[message.channel.id].append(self._sanitize_history_item(data))

        # persist trimmed history asynchronously
        try:
            file_path = os.path.join(self.persistence_dir, f"{message.channel.id}.json")
            to_save = list(self.history[message.channel.id])[-self.history_limit:]
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, lambda: open(file_path, "w", encoding="utf-8").write(json.dumps(to_save, ensure_ascii=False)))
        except Exception:
            logger.exception("Failed to persist history asynchronously")

        # cooldown check
        now = time.time()
        user_cd = self.cooldowns.get(message.author.id)
        if user_cd and now - user_cd < self.cooldown_seconds:
            remaining = round(self.cooldown_seconds - (now - user_cd), 1)
            try:
                await message.reply(f"You are on cooldown. Please retry after {remaining} seconds", allowed_mentions=AllowedMentions.none())
            except Exception:
                pass
            return

        # get or create channel lock to avoid concurrent LLM calls
        lock = self.locks.get(message.channel.id)
        if lock is None:
            lock = asyncio.Lock()
            self.locks[message.channel.id] = lock

        async with lock:
            # update cooldown timestamp for user
            self.cooldowns[message.author.id] = now

            async with message.channel.typing():
                sent_message: Optional[Message] = None
                try:

                    async for chunk in self.generate_response({
                        "provider": provider,
                        "model": model,
                        "query": messages
                    }):
                        output += chunk
                        # accumulate chunks; DO NOT edit the placeholder during streaming
                except Exception as e:
                    embed = Embed(
                        title=e.__class__.__name__,
                        description=str(e),
                        color=Color.red()
                    )
                    logger.exception(f"Failed to generate response: {e}")

                    return await message.channel.send(embed=embed, allowed_mentions=AllowedMentions.none())

                if output:
                    output = output.strip()
                    if not output:
                        return

                    output = output.replace("{author_name}", message.author.display_name)
                    output = output.replace("{author_mention}", message.author.mention)

                    # handle reply prefix
                    if output.startswith("[REPLY]"):
                        final = output[7:]
                        sent = await message.reply(final[:2000], allowed_mentions=AllowedMentions.none())
                    else:
                        sent = await message.channel.send(output[:2000], allowed_mentions=AllowedMentions.none())

                    # append assistant response to history and persist
                    self.history[message.channel.id].append(self._sanitize_history_item({
                        "role": "assistant",
                        "content": output
                    }))
                    try:
                        file_path = os.path.join(self.persistence_dir, f"{message.channel.id}.json")
                        to_save = list(self.history[message.channel.id])[-self.history_limit:]
                        loop = asyncio.get_running_loop()
                        loop.run_in_executor(None, lambda: open(file_path, "w", encoding="utf-8").write(json.dumps(to_save, ensure_ascii=False)))
                    except Exception:
                        logger.exception("Failed to persist history after assistant response")
        
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.user: return
        if self.bot.user and not self.bot.user.mentioned_in(message): return
        if message.mention_everyone: return
        
        if message.channel.id not in self.history:
            await self.populate_channel_cache(message.channel)

        member = getattr(message.guild, "me", None)
        if member is None:
            try:
                member = message.guild.get_member(self.bot.user.id)
            except Exception:
                member = None

        if member is None:
            logger.warning("Could not resolve guild member for bot in guild %s", getattr(message.guild, "id", "unknown"))
            return

        permissions = message.channel.permissions_for(member)
        if permissions and permissions.send_messages:
            await self.respond(message, "openrouter", "@preset/default", permissions.read_message_history)
async def setup(bot: PoxBot):
    await bot.add_cog(LLMChatCog(bot))