import uuid
from datetime import datetime
from io import BytesIO

from aiocache import cached
from discord import Embed, File, Interaction, app_commands
from discord.ext import commands
from mcstatus import JavaServer
from minepi import Player
from pytz import UTC

from ....application import PoxBot


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
    except ValueError:
        return False
    else:
        return True


class MinecraftCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot: PoxBot = bot

    minecraft_group = app_commands.Group(
        name='minecraft',
        description='Sub-group',
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    @cached(60)
    @minecraft_group.command(
        name='server',
        description=app_commands.locale_str('command.minecraft.server.description'),
    )
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def minecraft_server_lookup(self, interaction: Interaction, address: str):
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer()
        embed = Embed(title=f'Information for "{address}"')

        try:
            row_to_add = {}
            server = await JavaServer.async_lookup(address)

            status = await server.async_status()
            embed.description = status.motd.to_plain()
            row_to_add = {
                'minecraft_server_version': status.version.name,
                'minecraft_server_protocol': status.version.protocol,
                'minecraft_server_latency': f'{status.latency:2f} ms',
                'minecraft_server_players': f'{status.players.online}/{status.players.max}',
            }

            try:
                query = server.query()

                if query.motd:
                    embed.description = query.motd.to_plain()

                if query.players and query.players.list:
                    row_to_add['minecraft_server_playerlist'] = ', '.join(
                        query.players.list,
                    )
            except Exception:
                if status.players.sample:
                    names = [p.name for p in status.players.sample]
                    row_to_add['minecraft_server_playerlist'] = ', '.join(names)
                else:
                    row_to_add['minecraft_server_playerlist'] = (
                        self.bot.internal_translator.T('text.unknown', loc)
                    )

            row_to_add = self.bot.internal_translator.translate_map(row_to_add, loc)

            for key, value in row_to_add.items():
                embed.add_field(name=key, value=value)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed.title = self.bot.internal_translator.T(
                'error.embeds.minecraft_lookup_failed.title',
                loc,
            )
            embed.description = self.bot.internal_translator.T(
                'error.embeds.minecraft_lookup_failed.description',
                loc,
                {'address': address, 'e': e},
            )
            return await interaction.followup.send(embed=embed)

    @cached(300)
    @minecraft_group.command(
        name='profile',
        description=app_commands.locale_str('command.minecraft.profile.description'),
    )
    @app_commands.checks.cooldown(1, 5, key=lambda i: (i.guild_id, i.user.id))
    async def user(self, interaction: Interaction, query: str):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )

        embed = Embed(timestamp=datetime.now(UTC))

        await interaction.response.defer()
        is_uuid = is_valid_uuid(query)
        try:
            player = Player(uuid=query) if is_uuid else Player(name=query)

            await player.initialize()

            files = []

            head = (
                await player.skin.render_head(ratio=20, vr=0, hr=0)
                if player.skin
                else None
            )
            body = await player.skin.render_skin() if player.skin else None

            if head:
                with BytesIO() as head_binary:
                    head.save(head_binary, 'PNG')
                    head_binary.seek(0)
                    files.append(File(fp=head_binary, filename='head.png'))

            if body:
                with BytesIO() as body_binary:
                    body.save(body_binary, 'PNG')
                    body_binary.seek(0)
                    files.append(File(fp=body_binary, filename='body.png'))

            embed.title = self.bot.internal_translator.T(
                'command.minecraft.profile.embeds.default.title',
                loc,
                {'name': player.name},
            )
            if head:
                embed.set_thumbnail(url='attachment://head.png')
            if body:
                embed.set_image(url='attachment://body.png')

            embed.add_field(name='UUID', value=f'`{player.uuid}`', inline=False)

            await interaction.followup.send(embed=embed, files=files)
        except Exception:
            embed.description = self.bot.internal_translator.T(
                'error.embeds.minecraft_user_not_found.description',
                loc,
                {'query': query},
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))
