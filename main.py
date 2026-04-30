import sys
import subprocess
import time

import stuff
stuff.create_dir_if_not_exists("./logs")

import os
import discord
from datetime import UTC, datetime
from discord.ext import commands
from discord import Color, Embed, Forbidden, HTTPException, Interaction, MissingApplicationID, app_commands
from bot import PoxBot
from logger import logger
from src.translator import translator_instance as i18n

import psutil
process_ps = psutil.Process(os.getpid())
process_ps.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)

bot_token = stuff.get_bot_token()

intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = PoxBot(
    intents=intents,
    command_prefix=commands.when_mentioned_or("p!"),
    owner_id=457436960655409153,
    #chunk_guilds_at_startup=False,
    #member_cache_flags=discord.MemberCacheFlags.none()
)

tree = bot.tree

@tree.command(name="reload_cogs", description=app_commands.locale_str("command.admin.reload_cogs.description"))
@app_commands.check(stuff.is_bot_owner)
async def reload_cogs(interaction: Interaction):
    loc = await bot.settings_db.get_locale(interaction) if bot.settings_db else interaction.locale
    
    await interaction.response.defer()
    
    loaded, failed, skipped = 0, 0, 0
    cog_files = [f for f in os.listdir('./cogs') if f.endswith('.py')]
    total = len(cog_files)
    
    embed = Embed(color=Color.gold())
    embed.title = i18n.T("command.admin.reload_cogs.embeds.loading.title", loc)
    embed.description = i18n.T("command.admin.reload_cogs.embeds.loading.description", loc)
    msg = await interaction.followup.send(embed=embed, wait=True)
    
    last_update_time = time.time()
    update_interval = 1.75
    
    for index, fname in enumerate(cog_files):
        ext_name = fname[:-3]
        
        if ext_name in bot.EXCLUDE_EXTENSIONS:
            skipped += 1
        else:
            try:
                await bot.reload_extension(f"cogs.{ext_name}")
                loaded += 1
            except Exception as e:
                logger.exception(f"[{e.__class__.__name__}] Failed to load {ext_name}: {e}")
                failed += 1
        
        current_time = time.time()
        if (current_time - last_update_time) >= update_interval or index == total - 1:
            progress_text = i18n.T(
                "command.admin.reload_cogs.embeds.loading.progress",
                loc,
                {
                    "current": index + 1,
                    "total": total,
                    "loaded": loaded,
                    "failed": failed
                }
            )
            embed.description = progress_text
            
            try:
                await msg.edit(embed=embed)
                last_update_time = current_time
            except HTTPException:
                pass
    
    sync_success = False
    num_synched = 0
    error_key = None
    
    try:
        synched = await bot.tree.sync()
        num_synched = len(synched)
        sync_success = True
        logger.info(f"Synchronized {num_synched} commands.")
    except app_commands.CommandSyncFailure:
        logger.exception("CommandSyncFailure: Invalid command data")
        error_key = "command.admin.reload_cogs.errors.sync_failure"
    except Forbidden:
        logger.error("Forbidden: Missing application.commands scope")
        error_key = "command.admin.reload_cogs.errors.forbidden"
    except MissingApplicationID:
        logger.error("MissingApplicationID: ID is empty")
        error_key = "command.admin.reload_cogs.errors.missing_id"
    except app_commands.TranslationError:
        logger.exception("TranslationError during sync")
        error_key = "command.admin.reload_cogs.errors.translation_error"
    except HTTPException:
        logger.error("HTTPException during sync")
        error_key = "command.admin.reload_cogs.errors.http_error"
    
    if sync_success:
        embed.title = i18n.T("command.admin.reload_cogs.embeds.success.title", loc)
        embed.color = Color.green()
        embed.description = i18n.T(
            "command.admin.reload_cogs.embeds.success.description",
            loc,
            {
                "loaded": loaded,
                "failed": failed,
                "synched": num_synched
            }
        )
    else:
        embed.title = i18n.T("command.admin.reload_cogs.embeds.error.title", loc)
        embed.color = Color.red()
        embed.description = i18n.T(error_key or "command.admin.reloads_cogs.errors.generic", loc)
    
    await msg.edit(embed=embed)

async def try_returnerror(interaction: Interaction, embed: Embed):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except HTTPException as e:
        logger.error(f"Could not send error embed due to network/Discord error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected failure in try_returnerror: {e}")

@tree.error
async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError):
    loc = await bot.settings_db.get_locale(interaction) if bot.settings_db else interaction.locale
    
    error_name = error.__class__.__name__
    key = f"error.exceptions.{error_name}"
    
    kwargs = {"e": str(error)}
    
    if isinstance(error, app_commands.CommandOnCooldown):
        kwargs["remaining"] = str(round(error.retry_after, 2))
    
    if isinstance(error, (app_commands.CommandInvokeError, app_commands.TransformerError)):
        logger.exception(f"Critical Error in /{interaction.command.qualified_name if interaction.command else "unknown_command"}: {error}")
    else:
        logger.warning(f"User Error in /{interaction.command.qualified_name if interaction.command else "unknown_command"}: {error}")
    
    description = i18n.T(key, loc, kwargs)
    
    if description == key:
        description = i18n.T("error.exceptions.AppCommandError", str(loc))
    
    embed = Embed(
        title=f"Error thrown: {error_name}",
        description=description,
        color=Color.red(),
        timestamp=datetime.now()
    )
    
    return await try_returnerror(interaction, embed)

""" @tree.error
async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.AppCommandError):
        embed = Embed(title="Error thrown!", color=Color.red(), timestamp=datetime.now())
        if isinstance(error, app_commands.CommandInvokeError):
            logger.exception(f"An error occurred while invoking command: {error}")
            embed.description = "An error occurred while executing the command."
        elif isinstance(error, app_commands.TransformerError):
            logger.exception(f"An error occurred during argument transformation: {error}")
            embed.description = "An error occurred while processing command arguments."
        elif isinstance(error, app_commands.TranslationError):
            logger.exception(f"An error occurred during command translation: {error}")
            embed.description = "An error occurred while translating the command."
        elif isinstance(error, app_commands.CheckFailure):
            if isinstance(error, app_commands.NoPrivateMessage):
                logger.warning(f"Check failure: {error}")
                embed.description = "This command cannot be used in private messages."
            elif isinstance(error, app_commands.MissingRole):
                logger.warning(f"Check failure: {error}")
                embed.description = "You do not have the required role to use this command."
            elif isinstance(error, app_commands.MissingAnyRole):
                logger.warning(f"Check failure: {error}")
                embed.description = "You do not have any of the required roles to use this command."
            elif isinstance(error, app_commands.MissingPermissions):
                logger.warning(f"Check failure: {error}")
                embed.description = "You do not have the required permissions to use this command."
            elif isinstance(error, app_commands.BotMissingPermissions):
                logger.warning(f"Check failure: {error}")
                embed.description = "I do not have the required permissions to execute this command."
            elif isinstance(error, app_commands.CommandOnCooldown):
                logger.warning(f"Check failure: {error}")
                embed.description = f"This command is on cooldown. Please try again after {round(error.retry_after, 2)} seconds."
            else:
                logger.warning(f"Check failure: {error}")
                embed.description = "You do not have permission to use this command."
        elif isinstance(error, app_commands.CommandLimitReached):
            logger.warning(f"Command limit reached: {error}")
            embed.description = "The command limit has been reached. Please try again later."
        elif isinstance(error, app_commands.CommandAlreadyRegistered):
            logger.warning(f"Command already registered: {error}")
            embed.description = "This command is already registered."
        elif isinstance(error, app_commands.CommandSignatureMismatch):
            logger.warning(f"Command signature mismatch: {error}")
            embed.description = "There is a signature mismatch for this command."
        elif isinstance(error, app_commands.CommandNotFound):
            logger.warning(f"Command not found: {error}")
            embed.description = "This command was not found."
        elif isinstance(error, app_commands.CommandSyncFailure):
            logger.warning(f"Command sync failure: {error}")
            embed.description = "Failed to synchronize commands."
        else:
            logger.exception(f"An unknown AppCommandError occurred: {error}")
            embed.description = "An unknown error occurred while executing the command."
        
        return await try_returnerror(interaction, embed)
    else:
        logger.exception(f"An unexpected error occurred: {error}")
        return """

def start_monitor():
    return subprocess.Popen([sys.executable, "src/performance_gui.py"])

if __name__ == "__main__":
    if not bot_token:
        logger.critical("You should to put the bot token to 'TOKEN' in .env!")
        exit()
    else:
        #monitor_proc = start_monitor()
        
        try:
            bot.run(bot_token, log_handler=None)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            pass
        except Exception as e:
            logger.exception(f"Uncaught exception: {e}")
        finally:
            #monitor_proc.terminate()
            logger.info("Bot has been stopped")