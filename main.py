import sys
import subprocess
from typing import Optional

from aiohttp.web_fileresponse import extension
import stuff
stuff.create_dir_if_not_exists("./logs")
import os
import discord
from datetime import UTC, datetime
from discord.ext import commands
from discord import Color, Embed, Forbidden, HTTPException, Interaction, MissingApplicationID, app_commands
from bot import PoxBot
from logger import logger
from src.translator import translator_instance

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

@tree.command(name="reload_cogs", description="Reloads cogs. (not restarting bot)")
@app_commands.check(stuff.is_bot_owner)
async def reload_cogs(interaction: Interaction):
    loaded_extension = 0
    failed_extension = 0
    
    await interaction.response.defer()
    
    translation_success = translator_instance.refresh()
    
    for fname in os.listdir('./cogs'):
        if fname.endswith('.py'):
            logger.debug(f"Loading extension {fname[:-3]}.")
            if fname[:-3] in bot.EXCLUDE_EXTENSIONS:
                logger.warning("This extension has excluded from loading.")
                continue
            
            try:
                await bot.reload_extension(f"cogs.{fname[:-3]}")
                logger.debug(f"Successfully loaded {fname[:-3]}.")
                loaded_extension += 1
            except commands.ExtensionNotLoaded as e:
                logger.exception(f"Extension {fname[:-3]} was not loaded due to {e}.")
                failed_extension += 1
            except commands.ExtensionNotFound:
                logger.exception(f"Extension {fname[:-3]} was not found from cogs folder.")
                failed_extension += 1
            except commands.NoEntryPointError:
                logger.exception(f"Extension {fname[:-3]} has no entrypoint to load.")
                failed_extension += 1
            except commands.ExtensionFailed as e:
                logger.exception(f"Extension {fname[:-3]} has failed to load due to {e}.")
                failed_extension += 1
            except Exception as e:
                logger.exception(f"Uncaught exception thrown while reloading, due to {e}.")
                failed_extension += 1
    
    try:
        synched = await bot.tree.sync()
        logger.info(f"Synchronized {len(synched)} commands, with {loaded_extension} loaded extensions and {failed_extension} failed.")
        return await interaction.followup.send(f"Synchronized {len(synched)} commands, with {loaded_extension} loaded extensions and {failed_extension} failed. (Translation: {translation_success})")
    except app_commands.CommandSyncFailure:
        logger.exception("CommandSyncFailure: Invalid command data")
        return await interaction.followup.send("Failed to sync commands. It seems some commands has invalid data.")
    except Forbidden:
        logger.error("Forbidden: The bot doesn't have permission to use `application.commands`")
        #await interaction.followup.send("Failed to sync commands. The scope `application.commands` is not allowed in this guild.\nMake sure to allow the usage of `application.commands`.")
        return
    except MissingApplicationID:
        logger.error("MissingApplicationID: The application ID is empty or missing")
        return
    except app_commands.TranslationError:
        logger.exception("TranslationError: Error occured while translating commands")
        return await interaction.followup.send("Failed to sync commands. It seems the syncing failed due to translation failure.")
    except HTTPException:
        logger.error("HTTPException: Failed to sync commands")
        return await interaction.followup.send("Failed to sync commands.")

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
    loc = interaction.locale
    
    error_name = error.__class__.__name__
    key = f"error.exceptions.{error_name}"
    
    kwargs = {"e": str(error)}
    
    if isinstance(error, app_commands.CommandOnCooldown):
        kwargs["remaining"] = str(round(error.retry_after, 2))
    
    if isinstance(error, (app_commands.CommandInvokeError, app_commands.TransformerError)):
        logger.exception(f"Critical Error in /{interaction.command.qualified_name if interaction.command else "unknown_command"}: {error}")
    else:
        logger.warning(f"User Error in /{interaction.command.qualified_name if interaction.command else "unknown_command"}: {error}")
    
    description = translator_instance.translate(key, loc, **kwargs)
    
    if description == key:
        description = translator_instance.translate("error.exceptions.AppCommandError", loc)
    
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
        monitor_proc = start_monitor()
        
        try:
            bot.run(bot_token, log_handler=None)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            pass
        except Exception as e:
            logger.exception(f"Uncaught exception: {e}")
        finally:
            monitor_proc.terminate()
            logger.info("Bot has been stopped")