from aiocache import cached
from discord import Color, Interaction, Embed, app_commands
from discord.ext import commands

from roblox import UserNotFound
import roblox
import roblox.users
from roblox.utilities.exceptions import Forbidden, BadRequest, TooManyRequests, InternalServerError, NotFound

from src.translator import translator_instance

from bot import PoxBot

class RobloxAPICog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="roblox", description=app_commands.locale_str("command.roblox.description"))
    
    # auto complete for roblox usernames
    async def roblox_username_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = []
        try:
            async for user in self.bot.roblox_client.user_search(current, max_items=10):
                choices.append(app_commands.Choice(name=f"{user.display_name} (@{user.name})", value=user.name))
                if len(choices) >= 24:
                    break
        except Exception:
            pass
        return choices
    
    @cached(300)
    @group.command(name="user_avatar", description=app_commands.locale_str("command.roblox.avatar.description"))
    async def get_user_avatar(self, interaction: Interaction, username: str):
        await interaction.response.defer()
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        
        avatar_cache = self.bot.cache.get(f"rbxthumb.user.avatar.{username}")
        
        embed = Embed(color=Color.red())
        
        if avatar_cache:
            avatar_url = avatar_cache
            embed.color = Color.yellow()
        else:
            try:
                user = await self.bot.roblox_client.get_user_by_username(username)
                if not user:
                    embed.description = translator_instance.T("error.custom.roblox_user_not_found", loc, {"username": username})
                    return await interaction.followup.send(embed=embed)
                
                thumb = await self.bot.roblox_client.thumbnails.get_user_avatar_thumbnails(
                    users=[user.id],
                    type=roblox.thumbnails.AvatarThumbnailType.full_body,
                    size=(420, 420)
                )

                if len(thumb) > 0:
                    avatar_url = thumb[0]
                    self.bot.cache.set(f"rbxthumb.user.avatar.{username}", avatar_url)
                else:
                    avatar_url = None
            except UserNotFound:
                embed.description = translator_instance.T("error.custom.roblox_user_not_found", loc, {"username": username})
                return await interaction.followup.send(embed=embed)
            except BadRequest:
                embed.description = translator_instance.T("error.http.400", loc)
                return await interaction.followup.send(embed=embed)
            except Forbidden:
                embed.description = translator_instance.T("error.custom.roblox_forbidden", loc)
                return await interaction.followup.send(embed=embed)
            except TooManyRequests:
                embed.description = translator_instance.T("error.http.429", loc)
                return await interaction.followup.send(embed=embed)
            except InternalServerError:
                embed.description = translator_instance.T("error.http.500", loc)
                return await interaction.followup.send(embed=embed)
            except Exception as e:
                embed.description = translator_instance.T("error.exceptions.Unknown", loc, {"e": e})
                return await interaction.followup.send(embed=embed)
            
        if avatar_url:
            embed = Embed(title=translator_instance.T("command.roblox.avatar.embeds.default.title", loc, {"username": username}))
            embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_image(url=avatar_url.image_url)
            return await interaction.followup.send(embed=embed)
        else:
            return await interaction.followup.send(translator_instance.T("error.custom.roblox_failed_retrieve_avatar", loc, {"username": username}))


    @cached(300)
    @group.command(name="user", description=app_commands.locale_str("command.roblox.user.description"))
    async def roblox_get_user(self, interaction: Interaction, username: str):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        await interaction.response.defer(thinking=True)
        
        embed = Embed()
        
        info_cache = self.bot.cache.get(f"rbxuser.{username}")
        image_cache = self.bot.cache.get(f"rbxthumb.user.avatar.{username}")

        result = None
        image_url = None

        if info_cache:
            result = info_cache
        else:
            try:
                user = await self.bot.roblox_client.get_user_by_username(username)
                if user:
                    result = user
                    self.bot.cache.set(f"rbxuser.{username}", result)
                else:
                    embed.description = translator_instance.T("error.custom.roblox_user_not_found", loc, {"username": username})
                    return await interaction.followup.send(embed=embed)
            except UserNotFound:
                embed.description = translator_instance.T("error.custom.roblox_user_not_found", loc, {"username": username})
                return await interaction.followup.send(embed=embed)
            except BadRequest:
                embed.description = translator_instance.T("error.http.400", loc)
                return await interaction.followup.send(embed=embed)
            except Forbidden:
                embed.description = translator_instance.T("error.custom.roblox_forbidden", loc)
                return await interaction.followup.send(embed=embed)
            except TooManyRequests:
                embed.description = translator_instance.T("error.http.429", loc)
                return await interaction.followup.send(embed=embed)
            except InternalServerError:
                embed.description = translator_instance.T("error.http.500", loc)
                return await interaction.followup.send(embed=embed)
            except Exception as e:
                embed.description = translator_instance.T("error.exceptions.Unknown", loc, {"e": e})
                return await interaction.followup.send(embed=embed)
        
        if image_cache:
            image_url = image_cache
        else:
            try:
                thumb = await self.bot.roblox_client.thumbnails.get_user_avatar_thumbnails(
                    users=[result.id],
                    type=roblox.thumbnails.AvatarThumbnailType.full_body,
                    size=(420, 420)
                )

                if len(thumb) > 0:
                    image_url = thumb[0]
                    self.bot.cache.set(f"rbxthumb_user_avatar_{username}", image_url)
                else:
                    image_url = None
            except Exception:
                image_url = None

        if result:
            if isinstance(result, roblox.users.User):
                rows = {
                    'label.roblox_user_id': result.id,
                    'label.roblox_user_name': result.name,
                    'label.roblox_user_display': result.display_name,
                    'label.roblox_user_banned': translator_instance.T("text.boolean.true", loc) if result.is_banned else translator_instance.T("text.boolean.false"),
                    'label.roblox_user_created': result.created.strftime("%Y-%m-%d %H:%M:%S UTC")
                }
                embed = Embed(title=translator_instance.T("command.roblox.user.embeds.default.title", loc, {"username": result.name}), description=result.description)
                
                for name, value in rows.items():
                    embed.add_field(name=translator_instance.T(name, loc), value=value, inline=True)

                if image_url:
                    embed.set_thumbnail(url=image_url.image_url)

                return await interaction.followup.send(embed=embed)
        else:
            return await interaction.followup.send("Failed to retrieve user information.")

async def setup(bot):
    await bot.add_cog(RobloxAPICog(bot))