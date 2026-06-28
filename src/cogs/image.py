import random
import re
import string
from datetime import datetime
from io import BytesIO

from discord import (
    Color,
    Embed,
    File,
    Interaction,
    Member,
    PartialEmoji,
    User,
    app_commands,
)
from discord.ext.commands import Cog
from petpetgif import petpet
from PIL import Image, ImageDraw, ImageFont
from pytz import UTC
from qrcode import QRCode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import VerticalGradiantColorMask
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer

import stuff
from src.bot import PoxBot

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS  # type: ignore


def sanitize_filename(filename):
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    sanitized = sanitized.replace(" ", "_")
    return sanitized.lstrip(".")


class ImageCog(Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.base_virtual_filename_prefix = "tonguebot_"
        self.label = "Generated with TongueBot"

    def generate_random_string(self, length: int | None = 8):
        if not length:
            length = 8
        length = stuff.clamp(length, 4, 10)
        result = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        return result

    def generate_basename(self, suffix: str | None = None):
        prefix = self.base_virtual_filename_prefix
        now = datetime.now(UTC)
        unix = str(int(now.timestamp() * 1000))
        random_string = self.generate_random_string()

        return (
            f"{prefix + unix}_{random_string}_{suffix}"
            if suffix
            else f"{prefix + unix}_{random_string}"
        )

    async def resolve_to_image(
        self,
        interaction: Interaction,
        target: User | Member | PartialEmoji | str | None
    ) -> bytes:
        target_url = None

        if interaction.message and interaction.message.attachments:
            attachment = interaction.message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith("image"):
                target_url = attachment.url
            else:
                raise RuntimeError("First attachment is not image")
        elif target is not None:
            if isinstance(target, (Member, User)):
                target_url = target.display_avatar.url
            elif isinstance(target, PartialEmoji):
                if target.id:
                    target_url = target.url
                else:
                    raise TypeError("Type of emoji must not be built-in emoji")
            else:
                raise ValueError(
                    "Invalid parameter."
                    "Make sure to specify the type from User, Custom Emoji or Image.")
        else:
            target_url = interaction.user.display_avatar.url

        if target_url and self.bot.session:
            async with self.bot.session.get(target_url) as resp:
                if resp.status != 200:
                    raise RuntimeError("Failed to retrieve image")
                return await resp.read()
        else:
            raise ValueError("Target was empty")

    async def make_pat_gif(self, b: bytes) -> BytesIO:
        istream = BytesIO(b)
        dest = BytesIO()

        petpet.make(istream, dest)
        dest.seek(0)

        return dest

    group = app_commands.Group(
        name="image",
        description=app_commands.locale_str("command.image.description"),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    async def theme_autocomplete(
        self, interaction: Interaction, current: str  # noqa: ARG002
    ) -> list[app_commands.Choice[str]]:
        choices = ["light", "dark"]
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices
            if current.lower() in choice.lower()
        ]

    @group.command(name="qrcode", description="Generate QR Code")
    @app_commands.autocomplete(theme=theme_autocomplete)
    async def generate_qrcode(
        self, interaction: Interaction, input: str, theme: str | None = "dark"
    ):
        embed = Embed(color=Color.green())
        if not input.strip():
            embed.description = "The input cannot be empty!"
            embed.color = Color.red()
            return await interaction.response.send_message(embed=embed)

        await interaction.response.defer()

        bg_color = (49, 51, 56) if theme == "dark" else (255, 255, 255)
        text_top_color = (255, 255, 255) if theme == "dark" else (49, 51, 56)
        text_bottom_color = (149, 231, 240) if theme == "dark" else (180, 200, 210)

        qr = QRCode()
        qr.add_data(input.strip())
        qr.make(fit=True)

        result = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=VerticalGradiantColorMask(
                back_color=bg_color,
                top_color=text_top_color,
                bottom_color=text_bottom_color,
            ),
        )

        if result and hasattr(result, "convert"):
            sub = result.get_image()

            if sub.mode == "RGBA":
                background = Image.new("RGB", sub.size, bg_color)
                background.paste(sub, (0, 0), sub)
                sub = background
            else:
                sub = sub.convert("RGB")

            width, height = sub.size

            font_size = 20

            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default(font_size)

            label_text = self.label
            padding = 20
            extra_height = font_size + padding * 3

            canvas = Image.new("RGB", (width, height + extra_height), bg_color)
            canvas.paste(sub, (0, 0))

            draw = ImageDraw.Draw(canvas)

            bbox = draw.textbbox((0, 0), label_text, font=font)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2
            ty = height + (padding // 2)

            draw.text((tx, ty), label_text, font=font, fill=text_top_color)

            filename = self.generate_basename("qrcode") + ".jpg"

            buffer = BytesIO()
            canvas.save(buffer, format="JPEG", quality=95, subsampling=0)
            buffer.seek(0)

            file = File(fp=buffer, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            embed.description = "Generated! >:D"

            await interaction.followup.send(embed=embed, file=file)
        else:
            embed.description = "Couldn't generate image! D:"
            await interaction.followup.send(embed=embed)

    @group.command(name="petpet",
                   description=app_commands.locale_str("command.image.petpet.description"))
    @app_commands.describe(member=app_commands.locale_str("command.image.petpet.parameters.member"))
    async def pet(self, interaction: Interaction, member: Member | User | None = None):
        await interaction.response.defer()
        loc = (
            await self.bot.settings_db.get_locale(interaction)
            if self.bot.settings_db else interaction.locale.value
        )

        embed = Embed()

        gif = None
        img = await self.resolve_to_image(interaction, member)
        if img:
            gif = await self.make_pat_gif(img)

        if gif:
            embed.title = self.bot.internal_translator.T("command.image.petpet.embeds.default.title", loc, {
                "executor": interaction.user.mention,
                "target": member.mention if member else interaction.user.mention})
            embed.description = self.bot.internal_translator.T("command.image.petpet.embeds.default.description", loc, {
                "executor": interaction.user.mention,
                "target": member.mention if member else interaction.user.mention})
            await interaction.followup.send(file=File(gif, filename="pat.gif"), embed=embed)


async def setup(bot):
    await bot.add_cog(ImageCog(bot))
