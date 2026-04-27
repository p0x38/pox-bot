import glob
from itertools import islice
import os
from pathlib import Path
from time import time
import uuid
from aiocache import cached
import aiofiles
from discord.ext.commands import Cog
from discord import Message, app_commands, Embed, Interaction, File
from discord.app_commands import AppInstallationType, locale_str, AppCommandContext
import markovify
from io import BytesIO
from datetime import datetime
import random
from os.path import dirname, join
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, TextClip,ColorClip, CompositeVideoClip
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.loop import loop
from moviepy.config import change_settings
import PIL.Image

from typing import Optional

from bot import PoxBot
from logger import logger
import stuff
import data
from proglog import TqdmProgressBarLogger

from matplotlib import pyplot as plt

change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})

class DiscordProgress(TqdmProgressBarLogger):
    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction
        self.last_update = 0
    
    def callback(self, **changes):
        bars = self.state.get('bars', {})
        if 'video_render' in bars:
            data = bars['video_render']
            current_pct = int((data['index'] / data['total']) * 100)

            if current_pct >= self.last_update + 20:
                self.last_update = current_pct

                self.interaction.client.loop.create_task(
                    self.interaction.edit_original_response(content=f"Rendering... {current_pct}")
                )

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS # type: ignore

class GenerationCog(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.target_size_mb = 24
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name='Generate fade video',
                callback=self.generate_funny_fade_video
            )
        )
    group = app_commands.Group(name="generate", description="Generators.")
    
    @group.command(name="emoticon",description="Sends random emoticon")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def send_emoticon(self,ctx):
        await ctx.response.send_message(random.choice(data.emoticons))
    
    @cached(300)
    @group.command(name="idek", description="idek.")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def idek(self, ctx):
        await ctx.response.send_message(f"idek.")
    
    @cached(300)
    @group.command(name="nyan_cat",description="Nyan cat :D")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def nyan_cat_image(self, ctx: Interaction):
        try:
            url = dirname(__file__)
            url2 = join(url,"../resources/nyancat_big.gif")
            
            with open(url2, 'rb') as f:
                pic = File(f)
            
            await ctx.response.send_message("THINK FAST, CHUCKLE NUTS.",file=pic)
        except Exception as e:
            await ctx.response.send_message(f"err.type=null.error. {e}")
    
    @cached(300)
    @group.command(name="cat_jard", description="evade")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def cat_jard(self, interaction: Interaction):
        embed = Embed()
        embed.set_image(url="attachment://cat.png")
        
        path = join(dirname(__file__), "../resources/cat_jard.png")

        with open(path, 'rb') as f:
            pic = File(f, filename="cat.png")

        if embed:
            await interaction.response.send_message(embed=embed,file=pic)

    @group.command(name="target_close", description="Target Closing Algorithm")
    async def algorithm_closing_to_target(self, ctx: Interaction, target_value: Optional[float], concurrents: Optional[int]):
        await ctx.response.defer()
        conc = stuff.clamp(concurrents or 10, 1, 20)
        histories = [stuff.approach_target(target_value or 20) for _ in range(conc)]
        
        plt.style.use('dark_background')
        plt.figure(figsize=(12,8))
        for i, his in enumerate(histories):
            plt.plot(his, label=f"Attempt {i+1}")
        
        plt.axhline(y=target_value or 20, color='r', linestyle='--', label="Target")
        plt.title(f"Target close algorithm on {datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}, with {conc} parallels")
        plt.xlabel("Steps")
        plt.ylabel("Value")
        plt.legend(loc='lower right')
        plt.grid(True)
        plt.tight_layout()
        
        buffer = BytesIO()
        
        plt.savefig(buffer, format='png')
        
        buffer.seek(0)
        
        plt.close()
        
        file = File(fp=buffer, filename='output.png')
        
        e = Embed(title="Results with 'Target Close Algorithm'")
        for i,hist in enumerate(histories):
            e.add_field(name=f"Attempt #{i+1}",value=f"Length: {round(len(hist))}, Vx: \"{round(max(hist))},{round(min(hist))},{round(sum(hist)/len(hist))}\"")
        
        e.set_image(url="attachment://output.png")
        if file and e:
            await ctx.followup.send(file=file, embed=e)
    
    @group.command(name="computer_latency",description="Calculates hosted computer's latency")
    async def check_computer_latency(self, ctx: Interaction, delay: Optional[float]):
        await ctx.response.defer()
        delay = stuff.clamp_f(delay or 150, 10,1000) / 10
        delay2 = delay / 1000
        iterations = int(1/delay2)
        
        results = stuff.get_latency_from_uhhh_time(delay, iterations)

        plt.style.use('dark_background')
        plt.figure(figsize=(12,8))

        plt.plot(results,linestyle='-', color='b', label="Estimated")

        plt.axhline(y=(sum(results) / len(results)), color='r', linestyle='--', label="Avg.")
        plt.title(f"Computer Latency on {datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}")
        plt.xlabel("Steps")
        plt.ylabel("Milliseconds")
        plt.legend(loc='lower right')
        plt.grid(True)
        plt.tight_layout()
        
        buffer = BytesIO()
        
        plt.savefig(buffer, format='png')
        
        buffer.seek(0)
        
        plt.close()
        
        file = File(fp=buffer, filename='output.png')
        
        e = Embed(title="Results with 'Target Close Algorithm'")
        
        e.set_image(url="attachment://output.png")
        if file and e:
            await ctx.followup.send(file=file, embed=e)

    
    @group.command(name="markov", description="Generates random lines with Markov-chain")
    @app_commands.describe(amount="Times to generate, up to 16 iterations (lines).")
    async def generate_markovified_text(self, ctx: Interaction, amount: Optional[int]):
        await ctx.response.defer()
        amount = stuff.clamp(amount or 1, 1, 16)
        text2 = await stuff.get_markov_dataset("m2")
        
        if not text2:
            await ctx.followup.send("Unexcepted error occured.")
            return
        
        text = "\n".join(text2)
        
        model = markovify.Text(text, state_size=3)
        
        results = [model.make_sentence() for _ in range(amount)]

        lines = []
        
        for i,result in enumerate(results):
            if not result:
                while True:
                    result = model.make_sentence()
                    if result and not result in text2:
                        break
            
            lines.append(result)

        await ctx.followup.send("\n".join(lines))
    
    @group.command(name="markov2", description="Generates SCP-like anomaly with Markov-chain")
    @app_commands.describe(amount="Times to generate, up to 16 iterations (lines).")
    async def generate_markovified_anomaly_text(self, ctx: Interaction, amount: Optional[int]):
        await ctx.response.defer()
        amount = stuff.clamp(amount or 1, 1, 16)
        text2 = await stuff.get_markov_dataset("m1")
        
        if not text2:
            await ctx.followup.send("Unexcepted error occured.")
            return
        
        text = "\n".join(text2)
        
        model = markovify.Text(text, state_size=3)
        
        results = [model.make_sentence() for _ in range(amount)]

        lines = []
        
        for i,result in enumerate(results):
            if not result:
                while True:
                    result = model.make_sentence()
                    if result and not result in text2:
                        break
            
            lines.append(result)

        await ctx.followup.send("\n".join(lines))

    @group.command(name="meow",description="Make me say miaw :3")
    @app_commands.describe(put_face="Enables extra face such as :3")
    async def say_meow(self, ctx: Interaction,put_face:str):
        add_face = True if put_face.lower() in ("yes", "true") else False
        arrays = data.meows_with_extraformat
        
        for index, string in enumerate(arrays):
            arrays[index] = stuff.format_extra(string)
            if add_face:
                arrays[index] = arrays[index]+" "+random.choice(data.faces)
        
        await ctx.response.send_message(f"{random.choice(arrays)}.")
    
    @cached(300)
    @group.command(name="nyan_bot",description="Nyan bot.")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def nyan_bot_image(self, ctx):
        try:
            url = dirname(__file__)
            url2 = join(url,"../resources/windows_flavored_off_thing_staticc.gif")
            
            with open(url2, 'rb') as f:
                pic = File(f)
                
            await ctx.response.send_message("THINK FAST, CHUCKLE NUTS.",file=pic)
        except Exception as e:
            await ctx.response.send_message(f"Error. {e}")
    
    @cached(300)
    @app_commands.command(name="hi",description="replys as hi")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def say_hi(self, ctx: Interaction):
        await ctx.response.send_message("Hi.")
    
    @group.command(name="collatz_graph", description="Generates Collatz Conjecture graph for a given number.")
    @app_commands.describe(number="The starting number for the Collatz sequence.")
    async def generate_collatz_graph(self, ctx: Interaction, number: int):
        def collatz_sequence(x):
            seq = [x]
            if x < 1:
                return [x]
            # Generate the Collatz sequence until reaching 1 or reaching a limit
            while x > 1 and len(seq) < 2500:
                try:
                    if x % 2 == 0:
                        x = x // 2
                    else:
                        x = 3 * x + 1
                except OverflowError:
                    break
                seq.append(x)
            return seq
        
        await ctx.response.defer()

        sequence = collatz_sequence(number)

        plt.style.use('dark_background')
        plt.figure(figsize=(12,8))
        plt.plot(sequence, marker='o')
        plt.title(f"Collatz Conjecture Sequence for {number}")
        plt.xlabel("Steps")
        plt.ylabel("Value")
        plt.grid(True)
        plt.tight_layout()
        
        buffer = BytesIO()
        
        plt.savefig(buffer, format='png')
        
        buffer.seek(0)
        
        plt.close()
        
        file = File(fp=buffer, filename='collatz_output.png')
        
        e = Embed(title=f"Collatz Conjecture Sequence for {number}")
        e.set_image(url="attachment://collatz_output.png")

        if file and e:
            await ctx.followup.send(file=file, embed=e)
        else:
            await ctx.followup.send("An error occurred while generating the graph.")
    
    async def image_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        results = []
        
        files = glob.glob(os.path.join(self.bot.root_path, "resources/imgs/*.jpg")) + glob.glob(os.path.join(self.bot.root_path, "resources/imgs/*.png"))

        for path in files:
            path = os.path.basename(path)
            results.append(app_commands.Choice(name=os.path.splitext(path)[0], value=path))
            results.append(app_commands.Choice(name=os.path.splitext(path)[0].replace('_', ' '), value=path))

        return list(islice((v for v in results if (current or "").lower() in (getattr(v, "name", "") or "").lower()), 25))

    @group.command(name="image", description="Shows image by sum.")
    @app_commands.autocomplete(id=image_autocomplete)
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def generate_image(self, interaction: Interaction, id: str):
        await interaction.response.defer()

        if os.path.exists(os.path.join(self.bot.root_path, "resources/imgs/" + id)):
            async with aiofiles.open(os.path.join(self.bot.root_path, "resources/imgs/" + id), 'rb') as f:
                cont = await f.read()
            
            pic = File(BytesIO(cont), filename=id)

            return await interaction.followup.send(f"Image name: {id}",file=pic)
        else:
            return await interaction.followup.send("I couldn't find that")
        
    @cached(60)
    async def generate_funny_fade_video(self, interaction: Interaction, message: Message):
        start_time = time()

        if not message.attachments or len(message.attachments) > 1:
            return await interaction.response.send_message("This message has not exactly one attachment.", ephemeral=True)
        
        content_type = message.attachments[0].content_type or ""
        await interaction.response.send_message(f"Video request recceived by {interaction.user.mention}! Preparing data...")
        
        if not os.path.exists("cache"):
            os.makedirs("cache")
        
        job_id = uuid.uuid4().hex
        in_name = Path(f"cache/tempin_{job_id}{Path(message.attachments[0].filename).suffix}")
        out_name = Path(f"cache/tempout_{job_id}.mp4")

        faded = None
        clip = None
        try:
            await message.attachments[0].save(in_name)

            file_size = os.path.getsize(in_name.absolute()) / (1024 * 1024)

            audio = AudioFileClip("resources/audio/nocturne.mp3")

            dur = min(8, audio.duration)
            audio = audio.set_duration(dur)

            if file_size > 24: return await interaction.followup.send("The filesize must be less than 24 MB.")
            if "gif" in content_type:
                clip = VideoFileClip(str(in_name)).fx(loop, duration=dur)
            elif "image" in content_type:
                clip = ImageClip(str(in_name)).set_duration(dur)
            else:
                clip = VideoFileClip(str(in_name)).set_duration(dur)
            
            clip = clip.resize(height=480)

            fs = int(clip.w * 0.08)
            box_w = int(clip.w * 0.9)

            txt = TextClip(
                message.content.strip() or "",
                fontsize=fs,
                color='white',
                method='caption',
                size=(box_w, None),
                align='Center'
            ).set_duration(dur)

            bg_bar = ColorClip(
                size=(clip.w, txt.h + 20),
                color=(0,0,0)
            )
            bg_bar = bg_bar.set_opacity(0.6).set_duration(dur)

            txt = CompositeVideoClip([
                bg_bar.set_position('center'),
                txt.set_position('center')
            ], size=(clip.w, bg_bar.h)).set_duration(dur)

            faded = CompositeVideoClip([clip, txt.set_position(('center', clip.h - txt.h - 20))]).set_audio(audio).fx(fadein, dur/2.5)

            progress_logger = DiscordProgress(interaction)
            faded.write_videofile(
                str(out_name),
                fps=20,
                codec='libx264',
                audio_codec='aac',
                bitrate=f"450k",
                threads=(os.cpu_count() or 1) // 1.5,
                preset="ultrafast",
                logger=progress_logger
            )

            render_time = round(time() - start_time, 2)

            await interaction.edit_original_response(content=f"Rendered in {render_time} seconds!")
            await interaction.followup.send(file=File(out_name, f"generated_{job_id[:16]}.mp4"))
        except Exception as e:
            logger.exception(e)
            await interaction.followup.send(f"Oopsie! {e}"[:2000])
        finally:
            try:
                for obj in ['final','clip','audio','txt','bg_bar','overlay']:
                    if obj in locals() and obj is not None: locals()[obj].close()
            except Exception as e:
                logger.exception(e)
            
            try:
                for p in [in_name, out_name]:
                    if os.path.exists(p): os.remove(p)
            except Exception as e:
                logger.exception(e)
async def setup(bot):
    await bot.add_cog(GenerationCog(bot))