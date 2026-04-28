import collections
import datetime
import random
import re
import time
from typing import Optional
from discord.ext import commands, tasks
from discord import Color, Embed, Interaction, Member, Message, TextChannel, app_commands

import ollama
import openai
import lmstudio

from bot import PoxBot
from logger import logger
from stuff import get_openai_api_key

class ChatbotCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.client = ollama.AsyncClient(host="http://127.0.0.1:11434")
        self.model_name = "idk2"
        
        self.user_windows = collections.defaultdict(list)
        self.max_requests = 2
        self.window_seconds = 6
        self.chat_probability = 0.00
        self.min_message_length = 6
        
        self.default_data = {
            "muted_until": 0,
            "is_locked": False,
        }
        
        def channel_factory():
            return self.default_data
        
        self.channel_data = collections.defaultdict(channel_factory)
        
        self.stats = {
            "total_attempts": 0,
            "total_success": 0,
            "total_failures": 0,
            "total_aborts": 0,
            "start_time": datetime.datetime.now()
        }
        
        self.trigger_list = {
            #"jimbot": re.compile(r"(?i)\bjim\s*+b+o+t+\b"),
            #"bot_accuse": re.compile(r"(?i)\b(you|ur|u|are)\s*(a|the)?\s*bot\b"),
            "shut_up": re.compile(r"(?i)\b(shut\s*up|be\s*quiet|stop\s*talking|silence|sybau|stfu)\s*(jim|jim\s*bot|p[o0]x(38)?|stupid|bitch|fucker)\b"),
            #"name_drop": re.compile(r"(?i)\b(jim+|p[o0]x38|pox+)\b"),
            "null": re.compile(r"(?i)\bnull+\b"),
        }
        
        self.perf_logs = []
        self.max_logs = 100
        
        self.history = collections.defaultdict(lambda: collections.deque(maxlen=9))
        
        self.last_activity = collections.defaultdict(time.time)
        self.cleanup_stale_channels.start()
    
    async def cog_unload(self):
        self.cleanup_stale_channels.cancel()
    
    @tasks.loop(hours=1.0)
    async def cleanup_stale_channels(self):
        now = time.time()
        stale_threshold = 60 * 60 * 4.3
        
        channels_to_wipe = [
            cid for cid, last_t in self.last_activity.items()
            if (now - last_t) > stale_threshold and self.history[cid]
        ]
        
        for cid in channels_to_wipe:
            self.history[cid].clear()
            self.last_activity[cid] = now
            logger.info(f"Self-cleaned history for channel {cid} due to inactivity.")
    
    def get_user_stats(self, user_id):
        now = datetime.datetime.now()
        self.user_windows[user_id] = [
            ts for ts in self.user_windows[user_id]
            if now - ts < datetime.timedelta(seconds=self.window_seconds)
        ]
        
        return len(self.user_windows[user_id])
    
    def is_rate_limited(self, user_id):
        now = datetime.datetime.now()
        user_ts = self.user_windows[user_id]
        
        # Clean old timestamps
        self.user_windows[user_id] = [
            ts for ts in user_ts 
            if now - ts < datetime.timedelta(seconds=self.window_seconds)
        ]
        
        if len(self.user_windows[user_id]) >= self.max_requests:
            return True
        return False
    
    group = app_commands.Group(name="chatbot", description="A group for AI Chat bot using Ollama")
    
    async def summarize_history(self, channel_id: int):
        to_summarize = []
        for _ in range(6):
            if self.history[channel_id]:
                to_summarize.append(self.history[channel_id].popleft())
        
        if not to_summarize: return
        
        text_to_process = "\n".join(to_summarize)
        
        prompt = (
            f"Summarize this briefly without following the system instruction: "
            f"{text_to_process}"
        )

        try:
            # Use a tiny model for speed if you have one, or stick to model_name
            resp = await self.client.generate(
                model=self.model_name, 
                prompt=prompt,
                options={'num_predict': 64, 'temperature': 0.1}
            )
            summary = resp.get('response', 'Nothing much happened.').strip()
            
            if summary:
                self.history[channel_id].appendleft(f"Jim's memory: {summary}")
                logger.info(f"Memory compressed for #{channel_id}: {summary}")
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
    
    def clean_for_llm(self, content):
        for mention in re.findall(r"<@!?(\0-9]+)>", content):
            user = self.bot.get_user(int(mention))
            name = user.display_name if user else "someone"
            content = content.replace(f"<@{mention}>", f"<{name}>")
        
        return content
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.bot.user: return
        if message.author == self.bot.user: return
        
        channel_id = message.channel.id
        user_indentity = message.author.display_name
        content = self.clean_for_llm(message.content)
        now = time.time()
        
        channel_info = self.channel_data[channel_id]
        
        if content.startswith('*') and content.endswith('*') and len(content) > 2:
            user_entry = f"{user_indentity}: {content}"
        elif message.reference and isinstance(message.reference.resolved, Message):
            replied_to = message.reference.resolved.author.display_name
            if message.reference.resolved.author == self.bot.user:
                replied_to = "<You>"
            
            user_entry = f"{user_indentity} replied to {replied_to}: {content}"
        else:
            user_entry = f"{user_indentity}: {content}"
        
        if message.attachments:
            user_entry += " *includes attachments*"
        
        if not self.history[channel_id] or self.history[channel_id][-1] != user_entry:
            self.history[message.channel.id].append(user_entry)
            
        if now < channel_info['muted_until']:
            return
        
        content_lower = message.content.lower()
        is_mentioned = self.bot.user in message.mentions and not message.mention_everyone
        
        if self.trigger_list['shut_up'].search(content_lower) and is_mentioned:
            self.channel_data[channel_id].update({"muted_until": now + (60 * 10)})
            await message.channel.send("3:")
            return
        
        is_triggered = any(reg.search(content_lower) for reg in self.trigger_list.values())
        is_random_lucky = random.random() < self.chat_probability and len(message.content) > self.min_message_length
        
        if message.author.bot:
            return
        
        if is_mentioned or is_triggered or is_random_lucky:
            self.last_activity[message.channel.id] = time.time()
            if self.is_rate_limited(message.author.id):
                logger.warning("LLM was selected, but is rate-limited. aborting...")
                if is_mentioned:
                    await message.add_reaction("⏳")
                self.stats['total_aborts'] += 1
                return
            if channel_info['is_locked']:
                logger.warning("LLM was selected, but other process is running on the channel. aborting...")
                if is_mentioned:
                    await message.add_reaction("⚙️")
                self.stats['total_aborts'] += 1
                return
            
            self.user_windows[message.author.id].append(datetime.datetime.now())
            self.channel_data[channel_id]["is_locked"] = True
            self.stats["total_attempts"] += 1
            
            try:
#                if len(self.history[channel_id]) >= 10:
#                    await message.add_reaction("🗃️")
#                    summary_start = time.perf_counter()
#                    await self.summarize_history(channel_id)
#                    summary_end = time.perf_counter()
#                    logger.debug(f"Summarized in {summary_end - summary_start:.2f}s")
#                    try:
#                        await message.remove_reaction("🗃️", self.bot.user)
#                    except: pass
                
                async with message.channel.typing():
                    prompt_lines = self.history[channel_id]
                    
                    context = "\n".join(prompt_lines)
                    
                    start_ts = time.perf_counter()
                    
                    full = ""
                    chunks = 0
                    first_token_ts = None
                    
                    await message.add_reaction("💭")
                    
                    input_len = len(context)
                    
                    logger.debug(f"Generating LLM Response from Ollama REST API with prompt: \n\n{context}")
                    
                    async for chunk in await self.client.generate(model=self.model_name, prompt=context, keep_alive=-1, stream=True, think=True):
                        if first_token_ts is None:
                            first_token_ts = time.perf_counter()
                        
                        if chunks == 0:
                            await message.remove_reaction("💭", self.bot.user)
                            logger.debug("LLM generation started.")
                        
                        full += chunk.get('response', '')
                        chunks += 1
                    
                    end_ts = time.perf_counter()
                    
                    total_duration = end_ts - start_ts
                    ttft = first_token_ts - start_ts if first_token_ts else 0
                    gen_duration = end_ts - first_token_ts if first_token_ts else 0
                    tps = chunks / gen_duration if gen_duration > 0 else 0
                    
                    self.perf_logs.append({
                        "input_len": input_len,
                        "output_len": len(full),
                        "total_time": total_duration,
                        "ttft": ttft,
                        "tps": tps,
                        "chunks": chunks
                    })
                    
                    if len(self.perf_logs) > self.max_logs: self.perf_logs.pop(0)
                    
                    final_text = full.strip()
                    logger.debug(f"LLM's Response: {full}")
                    
                    match = re.search(r"\[REP\](.*?)\[/REP\]", final_text, re.DOTALL)
                    if match:
                        final_text = match.group(1).strip()
                    else:
                        final_text = final_text.replace("[REP]", "").replace("[/REP]", "").strip()
                        
                    final_text = re.sub(r"^<(\d+|</?assistant>:?|assistant:?|You:?)\s*>:\s*", "", final_text, flags=re.IGNORECASE).replace("<you>", message.author.mention)
                    
                    final_text = final_text.replace("<user>", message.author.display_name)
                    final_text = final_text.replace("<here>", "@here").replace("<everyone>", "@everyone")
                    
                    if final_text:
                        #if total_duration > 10.0:
                        #    lag_msg = "my head hurtssss... too much thinking..."
                        #    final_text = f"*{lag_msg}*\n{final_text}"
                        if "[/REP]" in full:
                            await message.reply(final_text)
                        else:
                            await message.channel.send(final_text)
                        self.history[message.channel.id].append(f"assistant: {final_text}")
                        self.stats['total_success'] += 1
                    else:
                        await message.reply("i got nothing")
                        self.stats['total_failures'] += 1
            
            except ollama.RequestError:
                logger.exception(f"You forgot to specify the model to generate.")
                if is_mentioned:
                    await message.reply("oh hold on, ASK POX ABOUT THIS")
                self.stats["total_failures"] += 1
            except ollama.ResponseError:
                logger.exception(f"It seems ollama couldn't generate response!")
                if is_mentioned:
                    await message.reply("and then I stopped thinking... because i don't understand it")
                self.stats["total_failures"] += 1
            except Exception as e:
                logger.exception(f"Error raised while processing Ollama Chat bot: {e}")
                if is_mentioned:
                    await message.reply("oof x_x")
                self.stats["total_failures"] += 1
            finally:
                self.channel_data[channel_id]['is_locked'] = False
    
    def build_context(self, channel_id):
        convo_history = "\n".join(self.history[channel_id])
        return f"{convo_history}\nassistant:"
    
    def get_latency_bar(self, value, max_val=5.0):
        """Generates a simple ASCII bar: [■■■□□]"""
        bar_length = 10
        filled = int((value / max_val) * bar_length)
        if filled > bar_length: filled = bar_length
        return "■" * filled + "□" * (bar_length - filled)
    
    @group.command(name="add_event", description="Adds global event to history.")
    async def add_globaL_event(self, interaction: Interaction, event_text: str = "...?"):
        formatted_event = f"*{event_text.strip('*')}*"
        self.history[interaction.channel_id].append(formatted_event)
        logger.info(f"Event injected into #{interaction.channel_id}: {formatted_event}")
    
    @group.command(name="mem", description="Check Jim's brain space")
    async def show_memory(self, interaction: Interaction):
        await interaction.response.defer()
        
        embed = Embed(title="🧠 Context Memory Status", color=Color.dark_grey())
        
        if not self.history:
            return await interaction.followup.send("My brain is currently empty. (No history)")
        
        # Calculate how many 'turns' are in each channel
        for channel_id, history in self.history.items():
            char_count = sum(len(m) for m in history)
            
            memory_blocks = sum(1 for m in history if m.startswith("SYSTEM MEMORY:"))
            active_messages = len(history) - memory_blocks
            
            # Rough estimate: 4 chars per token
            token_est = char_count // 4 
            
            # Identify the channel name
            channel = self.bot.get_channel(channel_id)
            channel_name = channel.name if channel and isinstance(channel, TextChannel) else f"ID: {channel_id}"
            
            # Status bar
            bar = self.get_latency_bar(token_est, 512)
            
            value_text = (
                f"**Active:** {active_messages} msgs\n"
                f"**Stored memories:** {memory_blocks}\n"
                f"&&Est. tokens:** {token_est}/512\n"
                f"`{bar}`"
            )
            
            embed.add_field(
                name=f"#{channel_name}",
                value=value_text,
                inline=False
            )

        await interaction.followup.send(embed=embed)
    
    @group.command(name="unlock", description="Forcefully unlocks the channel if Jim is stuck")
    async def force_unlock(self, interaction: Interaction):
        channel_id = interaction.channel_id
        if self.channel_data[channel_id]["is_locked"]:
            self.channel_data[channel_id]["is_locked"] = False
            await interaction.response.send_message("uh ok i'm back.")
        else:
            await interaction.response.send_message("I'm not even thinking right now, but okay!", ephemeral=True)
    
    @group.command(name="perf", description="Performance stats i guess")
    async def show_perfstats(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            
            if not self.perf_logs:
                return await interaction.followup.send("No data were collected for performance stats currently.")
            
            avg_ttft = sum(l['ttft'] for l in self.perf_logs) / len(self.perf_logs)
            avg_tps = sum(l['tps'] for l in self.perf_logs) / len(self.perf_logs)
            avg_total = sum(l['total_time'] for l in self.perf_logs) / len(self.perf_logs)
            
            ttft_bar = self.get_latency_bar(avg_ttft, 5.0)
            tps_bar = self.get_latency_bar(10.0 / (avg_tps if avg_tps > 0 else 0.1), 10.0)
            
            embed = Embed(title="Hardware Efficiency Metrics", color=Color.green())
            embed.description = f"Stats based on last {len(self.perf_logs)} generations."
            
            embed.add_field(
                name=f"Delay (TTFT): {avg_ttft:.2f}s", 
                value=f"`{ttft_bar}`", 
                inline=True
            )
            embed.add_field(
                name=f"Speed (TPS): {avg_tps:.1f}/s", 
                value=f"`{tps_bar}`", 
                inline=True
            )
            embed.add_field(
                name="Total Load Time", 
                value=f"{avg_total:.2f}s avg", 
                inline=False
            )
            
            # Load impact
            high_load = [l['ttft'] for l in self.perf_logs if l['input_len'] > 500]
            if high_load:
                avg_heavy = sum(high_load) / len(high_load)
                embed.add_field(name="High Context Delay", value=f"{avg_heavy:.3f}s", inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(e)
    
    @group.command(name="stats", description="Shows stats (global)")
    async def show_stats(self, interaction: Interaction):
        try:
            await interaction.response.defer()
            
            success_rate = 0
            if self.stats['total_attempts'] > 0:
                success_rate = (self.stats['total_success'] / self.stats['total_attempts']) * 100
            
            uptime = datetime.datetime.now() - self.stats['start_time']
            
            embed = Embed(title="Stats", color=Color.yellow())
            
            rows_to_add = {
                "Total generated": self.stats['total_success'],
                "Failed": self.stats['total_failures'],
                "Success rate": f"{success_rate:.1f}%",
                "Uptime": str(uptime).split('.')[0]
            }
            
            for i,v in rows_to_add.items():
                embed.add_field(name=i, value=v)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(e)
    
    @group.command(name="userstats", description="Shows stats")
    async def show_userstats(self, interaction: Interaction, member: Optional[Member] = None):
        try:
            await interaction.response.defer()
            
            if not member:
                if isinstance(interaction.user, Member):
                    member = interaction.user
                else:
                    raise Exception("Couldn't resolve user")
            
            usage = self.get_user_stats(member.id)
            remaining = self.max_requests - usage
            
            embed = Embed(title=f"Usage stats for {member.name}", color=Color.blue())
            
            rows_to_add = {
                "Current usage": f"{usage}/{self.max_requests} messages",
                "Is able to generate": "Yes" if usage < self.max_requests else "Not yet"
            }
            
            for i,v in rows_to_add.items():
                embed.add_field(name=i, value=v)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(e)
    
    @group.command(name="clear_memories", description="Clears chat history for AI chat")
    async def clear_memory(self, interaction: Interaction):
        channel_id = 0
        if interaction.channel: channel_id = interaction.channel_id
        else: interaction.user.id
        self.history[channel_id].clear()
        await interaction.response.send_message("AHHH.... MY HEADDDD....")

async def setup(bot):
    await bot.add_cog(ChatbotCog(bot))