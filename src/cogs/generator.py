import ast
import glob
import operator
import os
import random
import re
import uuid
import wave
from datetime import datetime
from io import BytesIO
from itertools import islice
from os.path import dirname, join
from pathlib import Path
from time import time

import aiofiles
import markovify
import numpy as np
import PIL.Image
from aiocache import cached
from discord import Color, Embed, File, Interaction, Message, app_commands
from discord.app_commands import AppCommandContext, locale_str
from discord.ext.commands import Cog
from matplotlib import pyplot as plt
from moviepy.config import change_settings
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.loop import loop
from proglog import TqdmProgressBarLogger
from pytz import UTC

import data
import stuff
from logger import logger
from src.bot import PoxBot

change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})


class DiscordProgress(TqdmProgressBarLogger):
    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction
        self.last_update = 0

    def callback(self, **changes):  # noqa: ARG002
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
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS  # type: ignore


class SecureBytebeatEvaluator:

    def __init__(self, formula: str):
        # initialize operator mapping per-instance to avoid shared mutable state
        self.OPERATORS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.LShift: operator.lshift,
            ast.RShift: operator.rshift,
            ast.BitOr: operator.or_,
            ast.BitXor: operator.xor,
            ast.BitAnd: operator.and_,
        }

        self.node = ast.parse(formula, mode='eval').body

    def eval(self, t_array: np.ndarray) -> np.ndarray | int | float:
        return self._eval_node(self.node, t_array)

    def _eval_node(self, node, t_array: np.ndarray) -> np.ndarray | int | float:
        # 変数 't' の処理
        if isinstance(node, ast.Name):
            if node.id == 't':
                return t_array
            raise ValueError(f"許可されていない変数です: {node.id}")

        # 数値リテラルの処理
        elif isinstance(node, ast.Constant):
            val = node.value
            if isinstance(val, (int, float)):
                return val
            raise ValueError(f"許可されていないリテラル値です: {val!r}")

        # 二項演算 (t >> 2 や t * 5 など) の処理
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type in self.OPERATORS:
                left = self._eval_node(node.left, t_array)
                right = self._eval_node(node.right, t_array)
                return self.OPERATORS[op_type](left, right)
            raise ValueError(f"許可されていない演算子です: {op_type.__name__}")

        # 単項演算 (-t や ~t など) の処理
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, t_array)
            if isinstance(node.op, ast.USub):
                # use numpy negative to support arrays
                return np.negative(operand)
            elif isinstance(node.op, ast.Invert):
                # use numpy bitwise_not to support arrays
                return np.bitwise_not(operand)
            raise ValueError(f"許可されていない単項演算子です: {type(node.op).__name__}")

        raise ValueError("不正な数式構造です。")


class BytebeatGenerator:
    def __init__(self, formula: str, type: str = "classic", sr: int = 8000, duration: float = 10.0):
        self.formula = formula
        self.type = type
        self.sr = sr
        self.duration = duration

    def generate_wav_bytes(self) -> BytesIO:
        total_samples = int(self.sr * self.duration)
        t_array = np.arange(0, total_samples, dtype=np.uint32)

        evaluator = SecureBytebeatEvaluator(self.formula)
        result = evaluator.eval(t_array)

        if self.type == "floatbeat":
            result = np.clip(result, -1.0, 1.0)
            audio_16bit = (result * 32767).astype(np.int16)
        else:
            byte_data = np.mod(result, 256).astype(np.uint8)
            audio_16bit = ((byte_data.astype(np.int16) - 128) * 256)

        stereo_16bit = np.column_stack((audio_16bit, audio_16bit)).flatten()

        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sr)
            wav_file.writeframes(stereo_16bit.tobytes())

        wav_buffer.seek(0)
        return wav_buffer


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
    group = app_commands.Group(
        name="generate",
        description=locale_str("command.generate.description"),
        allowed_contexts=AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    )

    @group.command(name="emoticon", description=locale_str("command.generate.emoticon.description"))
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def send_emoticon(self, ctx):
        await ctx.response.send_message(random.choice(data.emoticons))

    @cached(300)
    @group.command(name="idek", description=locale_str("command.generate.idek.description"))
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def idek(self, ctx):
        await ctx.response.send_message("idek.")

    @cached(300)
    @group.command(name="nyan_cat", description=locale_str("command.generate.nyan_cat.description"))
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def nyan_cat_image(self, ctx: Interaction):
        try:
            url = dirname(__file__)
            url2 = join(url, "../src/assets/nyancat_big.gif")

            async with aiofiles.open(url2, 'rb') as f:
                pic = File(await f.read())

            await ctx.response.send_message(
                self.bot.internal_translator.T("command.generate.nyan_cat.messages.think_fast"), file=pic)
        except Exception as e:
            await ctx.response.send_message(f"err.type=null.error. {e}")

    @cached(300)
    @group.command(name="cat_jard", description=locale_str("command.generate.cat_jard.description"))
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def cat_jard(self, interaction: Interaction):
        embed = Embed()
        embed.set_image(url="attachment://cat.png")

        path = join(dirname(__file__), "../src/assets/cat_jard.png")

        async with aiofiles.open(path, 'rb') as f:
            pic = File(await f.read(), filename="cat.png")

        if embed:
            await interaction.response.send_message(embed=embed, file=pic)

    @group.command(name="target_close",
                   description=locale_str("command.generate.target_close.description"))
    async def algorithm_closing_to_target(self, ctx: Interaction, target_value: float | None,
                                          concurrents: int | None):
        await ctx.response.defer()
        conc = stuff.clamp(concurrents or 10, 1, 20)
        histories = [stuff.approach_target(target_value or 20) for _ in range(conc)]

        plt.style.use('dark_background')
        plt.figure(figsize=(12, 8))
        for i, his in enumerate(histories):
            plt.plot(his, label=f"Attempt {i + 1}")

        plt.axhline(y=target_value or 20, color='r', linestyle='--', label="Target")
        plt.title(
            f"Target close algorithm on {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")}, "
            f"with {conc} parallels")
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
        for i, hist in enumerate(histories):
            e.add_field(
                name=f"Attempt #{i + 1}",
                value=(
                    f"Length: {round(len(hist))}, "
                    f"Vx: \"{round(max(hist))},{round(min(hist))},{round(sum(hist) / len(hist))}\"")
            )

        e.set_image(url="attachment://output.png")
        if file and e:
            await ctx.followup.send(file=file, embed=e)

    @group.command(name="computer_latency", description="Calculates hosted computer's latency")
    async def check_computer_latency(self, ctx: Interaction, delay: float | None):
        await ctx.response.defer()
        delay = stuff.clamp_f(delay or 150, 10, 1000) / 10
        delay2 = delay / 1000
        iterations = int(1 / delay2)

        results = stuff.get_latency_from_uhhh_time(delay, iterations)

        plt.style.use('dark_background')
        plt.figure(figsize=(12, 8))

        plt.plot(results, linestyle='-', color='b', label="Estimated")

        plt.axhline(y=(sum(results) / len(results)), color='r', linestyle='--', label="Avg.")
        plt.title(f"Computer Latency on {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")}")
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
    async def generate_markovified_text(self, ctx: Interaction, amount: int | None):
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

        for _i, result in enumerate(results):
            if not result:
                while True:
                    result = model.make_sentence()
                    if result and result not in text2:
                        break

            lines.append(result)

        await ctx.followup.send("\n".join(lines))

    @group.command(name="markov2", description="Generates SCP-like anomaly with Markov-chain")
    @app_commands.describe(amount="Times to generate, up to 16 iterations (lines).")
    async def generate_markovified_anomaly_text(self, ctx: Interaction, amount: int | None):
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

        for _i, result in enumerate(results):
            if not result:
                while True:
                    result = model.make_sentence()
                    if result and result not in text2:
                        break

            lines.append(result)

        await ctx.followup.send("\n".join(lines))

    @group.command(name="meow", description="Make me say miaw :3")
    @app_commands.describe(put_face="Enables extra face such as :3")
    async def say_meow(self, ctx: Interaction, put_face: str):
        add_face = put_face.lower() in ("yes", "true")
        arrays = data.meows_with_extraformat

        for index, string in enumerate(arrays):
            arrays[index] = stuff.format_extra(string)
            if add_face:
                arrays[index] = arrays[index] + " " + random.choice(data.faces)

        await ctx.response.send_message(f"{random.choice(arrays)}.")

    @cached(300)
    @group.command(name="nyan_bot", description="Nyan bot.")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def nyan_bot_image(self, ctx):
        try:
            url = dirname(__file__)
            url2 = join(url, "../src/assets/windows_flavored_off_thing_staticc.gif")

            async with aiofiles.open(url2, 'rb') as f:
                pic = File(await f.read())

            await ctx.response.send_message("THINK FAST, CHUCKLE NUTS.", file=pic)
        except Exception as e:
            await ctx.response.send_message(f"Error. {e}")

    @cached(300)
    @app_commands.command(name="hi", description="replys as hi")
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def say_hi(self, ctx: Interaction):
        await ctx.response.send_message("Hi.")

    @group.command(
        name="collatz_graph", description="Generates Collatz Conjecture graph for a given number.")
    @app_commands.describe(number="The starting number for the Collatz sequence.")
    async def generate_collatz_graph(self, ctx: Interaction, number: int):
        def collatz_sequence(x):
            seq = [x]
            if x < 1:
                return [x]
            # Generate the Collatz sequence until reaching 1 or reaching a limit
            while x > 1 and len(seq) < 2500:
                try:
                    x = x // 2 if x % 2 == 0 else 3 * x + 1
                except OverflowError:
                    break
                seq.append(x)
            return seq

        await ctx.response.defer()

        sequence = collatz_sequence(number)

        plt.style.use('dark_background')
        plt.figure(figsize=(12, 8))
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

    async def image_autocomplete(self,
                                 interaction: Interaction,  # noqa: ARG002
                                 current: str) -> list[app_commands.Choice[str]]:
        results = []

        files = glob.glob(os.path.join(
            self.bot.root_path, "src/assets/imgs/*.jpg")) + glob.glob(
                os.path.join(self.bot.root_path, "src/assets/imgs/*.png"))

        for path in files:
            path = os.path.basename(path)
            results.append(app_commands.Choice(name=os.path.splitext(path)[0], value=path))
            results.append(app_commands.Choice(name=os.path.splitext(path)[0].replace('_', ' '),
                                               value=path))

        return list(
            islice(
                (v for v in results if (current or "").lower() in (getattr(v, "name", "") or "")
                 .lower()), 25))

    @group.command(name="image", description="Shows image by sum.")
    @app_commands.autocomplete(id=image_autocomplete)
    @app_commands.checks.cooldown(2, 6, key=lambda i: i.user.id)
    async def generate_image(self, interaction: Interaction, id: str):
        await interaction.response.defer()

        if os.path.exists(os.path.join(self.bot.root_path, "src/assets/imgs/" + id)):
            async with aiofiles.open(
                os.path.join(self.bot.root_path, "src/assets/imgs/" + id), 'rb') as f:
                cont = await f.read()

            pic = File(BytesIO(cont), filename=id)

            return await interaction.followup.send(f"Image name: {id}", file=pic)
        else:
            return await interaction.followup.send("I couldn't find that")

    @group.command(name="bytebeat",
                   description=app_commands.locale_str("commands.generate.bytebeat.description"))
    async def generate_bytebeat(
        self,
        interaction: Interaction,
        formula: str,
        duration: float | None = None,
        sample_rate: int | None = None
    ):
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db
            else interaction.locale
        )
        await interaction.response.defer()

        embed = Embed()

        pattern = re.compile(r'[0-9t\s\+\-\*\/\&\ \|\>\<\%\(\)]+$')

        if not bool(pattern.match(formula)):
            embed.color = Color.red()
            embed.description = self.bot.internal_translator.T("error.embeds.invalid_bytebeat_formula.description", loc)

            return await interaction.followup.send(embed=embed)

        if duration is None:
            duration = 10

        if sample_rate is None:
            sample_rate = 8000

        if duration > 30.0 or sample_rate > 48000:
            embed.color = Color.red()
            embed.description = "too high"
            return await interaction.followup.send(embed=embed)

        try:
            # Instantiate the class with your default variables
            # Defaults type to "classic" since your original code focused on np.uint8 formats
            generator = BytebeatGenerator(
                formula=formula,
                type="classic",
                sr=sample_rate,
                duration=duration
            )

            # Generate correct structural binary stream data
            abuffer = generator.generate_wav_bytes()

            filename = "bytebeat.wav"
            file = File(fp=abuffer, filename=filename)

            embed.description = "Generated!"

            if file and embed:
                await interaction.followup.send(file=file, embed=embed)
            else:
                await interaction.followup.send("An error occurred while generating the audio.")
        except Exception as e:
            await interaction.followup.send(f"err.type=null.error. {e}")

    @cached(60)
    async def generate_funny_fade_video(self, interaction: Interaction, message: Message):
        start_time = time()

        if not message.attachments or len(message.attachments) > 1:
            return await interaction.response.send_message(
                "This message has not exactly one attachment.", ephemeral=True)

        content_type = message.attachments[0].content_type or ""
        await interaction.response.send_message(
            f"Video request recceived by {interaction.user.mention}! Preparing data...")

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

            audio = AudioFileClip("src/assets/audio/nocturne.mp3")

            dur = min(8, audio.duration)
            audio = audio.set_duration(dur)

            if file_size > 24:
                return await interaction.followup.send(
                    "The filesize must be less than 24 MB.")
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
                color=(0, 0, 0)
            )
            bg_bar = bg_bar.set_opacity(0.6).set_duration(dur)

            txt = CompositeVideoClip([
                bg_bar.set_position('center'),
                txt.set_position('center')
            ], size=(clip.w, bg_bar.h)).set_duration(dur)

            faded = CompositeVideoClip(
                [clip, txt.set_position(('center', clip.h - txt.h - 20))]
            ).set_audio(audio).fx(fadein, dur / 2.5)

            progress_logger = DiscordProgress(interaction)
            faded.write_videofile(
                str(out_name),
                fps=20,
                codec='libx264',
                audio_codec='aac',
                bitrate="450k",
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
                for obj in ['final', 'clip', 'audio', 'txt', 'bg_bar', 'overlay']:
                    if obj in locals() and obj is not None:
                        locals()[obj].close()
            except Exception as e:
                logger.exception(e)

            try:
                for p in [in_name, out_name]:
                    if os.path.exists(p):
                        os.remove(p)
            except Exception as e:
                logger.exception(e)


async def setup(bot):
    await bot.add_cog(GenerationCog(bot))
