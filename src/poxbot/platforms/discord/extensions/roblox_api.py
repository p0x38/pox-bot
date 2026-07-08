from aiocache import cached
from discord import Color, Embed, Interaction, app_commands
from discord.ext import commands
from roblox import AvatarThumbnailType, Client, UserNotFound
from roblox.users import User
from roblox.utilities.exceptions import (
    BadRequest,
    Forbidden,
    InternalServerError,
    TooManyRequests,
)

from ....application import PoxBot
from ....infrastructure.logger import get_logger


class RobloxAPICog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.logger = get_logger(__name__, prefix='RobloxCog')
        self.bot: PoxBot = bot
        self._client = Client()

    group = app_commands.Group(
        name='roblox',
        description=app_commands.locale_str('command.roblox.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True,
        ),
    )

    # auto complete for roblox usernames
    async def roblox_username_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = []
        async for user in self._client.user_search(
            current,
            max_items=10,
        ):
            choices.append(
                app_commands.Choice(
                    name=f'{user.display_name} (@{user.name})',
                    value=user.name,
                ),
            )
            if len(choices) >= 24:
                break
        return choices

    @cached(300)
    @group.command(
        name='user_avatar',
        description=app_commands.locale_str('command.roblox.avatar.description'),
    )
    @app_commands.choices(
        render_type=[
            app_commands.Choice(name='Bust', value=AvatarThumbnailType.bust.value),
            app_commands.Choice(
                name='Avatar',
                value=AvatarThumbnailType.full_body.value,
            ),
            app_commands.Choice(
                name='Headshot',
                value=AvatarThumbnailType.headshot.value,
            ),
        ],
    )
    async def get_user_avatar(
        self,
        interaction: Interaction,
        username: str,
        render_type: str,
    ):
        await interaction.response.defer()
        loc = await self.bot.get_locale(interaction)

        cache_id = (':'.join(['rbx', 'users', 'thumbnail', render_type, username]),)

        avatar_cache = self.bot.resources.cache.get(cache_id)

        embed = Embed(color=Color.red())

        if avatar_cache:
            avatar_url = avatar_cache
            embed.color = Color.yellow()
        else:
            try:
                user = await self._client.get_user_by_username(
                    username,
                )
                if not user:
                    embed.description = self.bot.internal_translator.T(
                        'error.custom.roblox_user_not_found',
                        loc,
                        {'username': username},
                    )
                    return await interaction.followup.send(embed=embed)

                thumb = await self._client.thumbnails.get_user_avatar_thumbnails(
                    users=[user.id],
                    type=AvatarThumbnailType(render_type),
                    size=(420, 420),
                )

                if len(thumb) > 0:
                    avatar_url = thumb[0]
                    self.bot.resources.cache.set(
                        cache_id,
                        avatar_url,
                    )
                else:
                    avatar_url = None
            except UserNotFound:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.roblox_user_not_found',
                    loc,
                    {'username': username},
                )
                return await interaction.followup.send(embed=embed)
            except BadRequest:
                embed.description = self.bot.internal_translator.T(
                    'error.http.400',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except Forbidden:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.roblox_forbidden',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except TooManyRequests:
                embed.description = self.bot.internal_translator.T(
                    'error.http.429',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except InternalServerError:
                embed.description = self.bot.internal_translator.T(
                    'error.http.500',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except Exception as e:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.Unknown',
                    loc,
                    {'e': e},
                )
                return await interaction.followup.send(embed=embed)

        if avatar_url:
            embed = Embed(
                title=self.bot.internal_translator.T(
                    'command.roblox.avatar.embeds.default.title',
                    loc,
                    {'username': username},
                ),
            )
            embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.display_avatar.url,
            )
            embed.set_image(url=avatar_url.image_url)
            return await interaction.followup.send(embed=embed)
        return await interaction.followup.send(
            self.bot.internal_translator.T(
                'error.custom.roblox_failed_retrieve_avatar',
                loc,
                {'username': username},
            ),
        )

    @cached(300)
    @group.command(
        name='user',
        description=app_commands.locale_str('command.roblox.user.description'),
    )
    async def roblox_get_user(self, interaction: Interaction, username: str):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        await interaction.response.defer(thinking=True)

        embed = Embed()

        cache_ids = {
            'info': ':'.join(['rbx', 'users', 'info', username]),
            'avatar': ':'.join(['rbx', 'users', 'thumbnail', 'avatar', username]),
        }

        info_cache = self.bot.resources.cache.get(cache_ids['info'])
        image_cache = self.bot.resources.cache.get(cache_ids['avatar'])

        result = None
        image_url = None

        if info_cache:
            result = info_cache
        else:
            try:
                user = await self._client.get_user_by_username(
                    username,
                )
                if user:
                    result = user
                    self.bot.resources.cache.set(cache_ids['info'], result)
                else:
                    embed.description = self.bot.internal_translator.T(
                        'error.custom.roblox_user_not_found',
                        loc,
                        {'username': username},
                    )
                    return await interaction.followup.send(embed=embed)
            except UserNotFound:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.roblox_user_not_found',
                    loc,
                    {'username': username},
                )
                return await interaction.followup.send(embed=embed)
            except BadRequest:
                embed.description = self.bot.internal_translator.T(
                    'error.http.400',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except Forbidden:
                embed.description = self.bot.internal_translator.T(
                    'error.custom.roblox_forbidden',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except TooManyRequests:
                embed.description = self.bot.internal_translator.T(
                    'error.http.429',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except InternalServerError:
                embed.description = self.bot.internal_translator.T(
                    'error.http.500',
                    loc,
                )
                return await interaction.followup.send(embed=embed)
            except Exception as e:
                embed.description = self.bot.internal_translator.T(
                    'error.exceptions.Unknown',
                    loc,
                    {'e': e},
                )
                return await interaction.followup.send(embed=embed)

        if image_cache:
            image_url = image_cache
        else:
            try:
                thumb = await self._client.thumbnails.get_user_avatar_thumbnails(
                    users=[result.id],
                    type=AvatarThumbnailType.full_body,
                    size=(420, 420),
                )

                if len(thumb) > 0:
                    image_url = thumb[0]
                    self.bot.resources.cache.set(
                        cache_ids['avatar'],
                        image_url,
                    )
                else:
                    image_url = None
            except Exception:
                image_url = None

        if result:
            if isinstance(result, User):
                rows = {
                    'label.roblox_user_id': result.id,
                    'label.roblox_user_name': result.name,
                    'label.roblox_user_display': result.display_name,
                    'label.roblox_user_banned': self.bot.internal_translator.T(
                        'text.boolean.true',
                        loc,
                    )
                    if result.is_banned
                    else self.bot.internal_translator.T('text.boolean.false', loc),
                    'label.roblox_user_created': result.created.strftime(
                        '%Y-%m-%d %H:%M:%S UTC',
                    ),
                }
                embed = Embed(
                    title=self.bot.internal_translator.T(
                        'command.roblox.user.embeds.default.title',
                        loc,
                        {'username': result.name},
                    ),
                    description=result.description,
                )

                for name, value in rows.items():
                    embed.add_field(
                        name=self.bot.internal_translator.T(name, loc),
                        value=value,
                        inline=True,
                    )

                if image_url:
                    embed.set_thumbnail(url=image_url.image_url)

                return await interaction.followup.send(embed=embed)
        else:
            return await interaction.followup.send(
                'Failed to retrieve user information.',
            )


async def setup(bot):
    await bot.add_cog(RobloxAPICog(bot))
