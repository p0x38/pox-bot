import random
from discord import Color, Embed, Interaction, app_commands
from discord.ext import commands
import aiosqlite
import time
from datetime import datetime

from os.path import join

from pytz import UTC

from bot import PoxBot
from src.database import EconomyDatabase

from src.translator import translator_instance as i18n

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.db: EconomyDatabase = bot.economy_db
    
    group = app_commands.Group(name="economy", description=app_commands.locale_str("command.economy.description"))

    async def get_loc(self, interaction: Interaction) -> str:
        if self.bot.settings_db:
            return await self.bot.settings_db.get_locale(interaction)
        return "en"
    
    @group.command(name="balance", description=app_commands.locale_str("command.economy.balance.description"))
    async def balance(self, interaction: Interaction):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.db:
            user = await self.db.get_user(interaction.user.id)

            embed.title = i18n.T("command.economy.balance.embeds.default.title", loc, {"user": interaction.user.display_name})
            embed.color = Color.green()
            embed.timestamp = interaction.created_at

            rows = {
                'command.economy.balance.fields.wallet': f"{user.wallet:,}",
                'command.economy.balance.fields.bank': f"{user.bank:,}"
            }

            for key, value in rows.items():
                translated = i18n.T(key, loc)
                embed.add_field(name=translated, value=value, inline=True)
            
            embed.set_footer(text=i18n.T('command.economy.balance.embeds.default.footer', loc, {"coins": f"{user.total:,}"}))

            await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
    
    @group.command(name="deposit", description=app_commands.locale_str("command.economy.deposit.description"))
    async def deposit(self, interaction: Interaction, amount: int):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            user = await self.db.get_user(interaction.user.id)
            
            if amount <= 0:
                embed.title = i18n.T('error.embeds.only_positive_value.title', loc)
                embed.description = i18n.T('error.embeds.only_positive_value.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            if amount > user.wallet:
                embed.title = i18n.T('error.embeds.too_high_value.title', loc, {"max": user.wallet})
                embed.description = i18n.T('error.embeds.too_high_value.description', loc, {"max": user.wallet})
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            user.wallet -= amount
            user.bank += amount

            await self.db.save_user(user)
            await self.db.log_tx(user.user_id, "deposit", amount, "Deposited to bank")

            embed.title = i18n.T('command.economy.deposit.embeds.default.title', loc)
            embed.description = i18n.T('command.economy.deposit.embeds.default.description', loc)
            embed.color = Color.green()
            return await interaction.followup.send(embed=embed)
        
    @group.command(name="withdraw", description=app_commands.locale_str("command.economy.withdraw.description"))
    async def withdraw(self, interaction: Interaction, amount: int):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            user = await self.db.get_user(interaction.user.id)
            
            if amount <= 0:
                embed.title = i18n.T('error.embeds.only_positive_value.title', loc)
                embed.description = i18n.T('error.embeds.only_positive_value.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            if amount > user.bank:
                embed.title = i18n.T('error.embeds.too_high_value.title', loc, {"max": user.wallet})
                embed.description = i18n.T('error.embeds.too_high_value.description', loc, {"max": user.wallet})
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            user.wallet -= amount
            user.bank += amount

            await self.db.save_user(user)
            await self.db.log_tx(user.user_id, "deposit", amount, "Deposited to bank")

            embed.title = i18n.T('command.economy.withdraw.embeds.default.title', loc)
            embed.description = i18n.T('command.economy.withdraw.embeds.default.description', loc)
            embed.color = Color.green()
            return await interaction.followup.send(embed=embed)
    
    @group.command(name="work", description=app_commands.locale_str("command.economy.work.description"))
    async def work(self, interaction: Interaction):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            user = await self.db.get_user(interaction.user.id)
            now = int(time.time())
            if now - user.last_work < 3600:
                rem = int((3600 - (now - user.last_work)) / 60)
                embed.title = i18n.T('command.economy.work.embeds.tired.title', loc)
                embed.description = i18n.T('command.economy.work.embeds.tired.description', loc, {"rem": rem})
                embed.color = Color.yellow()

                return await interaction.followup.send(embed=embed)
            
            bonus = random.randint(0, 500)
            earned = random.randint(50, 300)
            user.wallet += earned
            user.last_work = now
            await self.db.save_user(user)
            await self.db.log_tx(user.user_id, "work", earned, "Salary")

            embed.title = i18n.T("command.economy.work.embeds.default.title", loc)
            embed.description = i18n.T("command.economy.work.embeds.default.description", loc)
            embed.color = Color.green()

            await interaction.followup.send(embed=embed)
    
    @group.command(name='list', description=app_commands.locale_str("command.economy.list.description"))
    async def list_items(self, interaction: Interaction):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            items = await self.db.get_shop_items()
            if not items:
                embed.title = i18n.T('command.economy.list.embeds.closed.title', loc)
                embed.description = i18n.T('command.economy.list.embeds.closed.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
                
            embed = Embed(title="PoxBot Shop", color=Color.blue())
            for i in items:
                buy_price = i18n.T('command.economy.list.fields.buy_price', loc, {"price": f"{i['buy_price']:,}"}) if i['buy_price'] else i18n.T('command.economy.list.fields.not_sale', loc)
                embed.add_field(name=f"{i['name']} (ID: {i['id']})", value=f"{buy_price}\n{i['description']}", inline=False)
            await interaction.response.send_message(embed=embed)
    
    @group.command(name="buy", description=app_commands.locale_str("command.economy.buy.description"))
    async def buy_items(self, interaction: Interaction, item_id: str):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            user = await self.db.get_user(interaction.user.id)
            item = await self.db.get_item(item_id)

            if not item or not item['buy_price']:
                embed.title = i18n.T('command.economy.buy.embeds.item_unavailable.title', loc)
                embed.description = i18n.T('command.economy.buy.embeds.item_unavailable.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            if user.wallet < item['buy_price']:
                embed.title = i18n.T('command.economy.buy.embeds.not_afford.title', loc)
                embed.description = i18n.T('command.economy.buy.embeds.not_afford.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            user.wallet -= item['buy_price']
            await self.db.save_user(user)
            await self.db.modify_inventory(user.user_id, item_id, 1)
            await self.db.log_tx(user.user_id, "purchase", -item['buy_price'], f"Bought {item['name']}")

            embed.title = i18n.T("command.economy.buy.embeds.purchased.title", loc)
            embed.description = i18n.T("command.economy.buy.embeds.purchased.description", loc, {"item_name": item['name']})
            embed.color = Color.green()

            await interaction.followup.send(embed=embed)
    
    @group.command(name="sell", description=app_commands.locale_str("command.economy.sell.description"))
    async def sell_items(self, interaction: Interaction, item_id: str):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            item = await self.db.get_item(item_id)
            if not item or not item['sell_price']:
                embed.title = i18n.T('command.economy.sell.embeds.unable_to_sell.title', loc)
                embed.description = i18n.T('command.economy.sell.embeds.unable_to_sell.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            user = await self.db.get_user(interaction.user.id)
            await self.db.modify_inventory(user.user_id, item_id, -1)

            user.wallet += item['sell_price']
            await self.db.save_user(user)
            await self.db.log_tx(user.user_id, "sale", item['sell_price'], f"Sold {item['name']}")

            embed.title = i18n.T("command.economy.buy.embeds.purchased.title", loc)
            embed.description = i18n.T("command.economy.buy.embeds.purchased.description", loc, {"item_name": item['name']})
            embed.color = Color.green()

            await interaction.followup.send(embed=embed)
    
    @group.command(name="inventory", description=app_commands.locale_str("command.economy.inventory.description"))
    async def inventory(self, interaction: Interaction):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)

        embed = Embed()

        if self.bot.economy_db:
            items = await self.db.get_inventory(interaction.user.id)
            if not items:
                embed.title = i18n.T('command.economy.inventory.embeds.empty.title', loc)
                embed.description = i18n.T('command.economy.inventory.embeds.empty.description', loc)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
            
            embed.title = i18n.T("command.economy.inventory.embeds.default.title", loc, {"user": interaction.user.display_name})
            embed.color = Color.green()

            for i in items:
                embed.add_field(
                    name=f"{i['name']} (x{i['quantity']})",
                    value=i['description'], inline=False
                )
            
            await interaction.response.send_message(embed=embed)

    @group.command(name="daily", description=app_commands.locale_str("command.economy.daily.description"))
    async def daily(self, interaction: Interaction):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)
        
        embed = Embed()

        if self.db:
            user = await self.db.get_user(interaction.user.id)

            now = int(time.time())
            cooldown = 86400

            if now - user.last_daily < cooldown:
                remaining = cooldown - (now - user.last_daily)
                hours, remainder = divmod(remaining, 3600)
                minutes, _ = divmod(remainder, 60)

                embed.title = i18n.T("error.embeds.daily_cooldown.title", loc)
                embed.description = i18n.T("error.embeds.daily_cooldown.description", loc, {"h": hours, "m": minutes})
                embed.timestamp = datetime.now(UTC)
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            reward = random.randint(100, 900)
            user.wallet += reward
            user.last_daily = now

            await self.db.save_user(user)
            await self.db.log_tx(interaction.user.id, "daily", reward, "Claimed daily reward")

            embed.title = i18n.T("command.economy.daily.embeds.default.title", loc)
            embed.description = i18n.T("command.economy.daily.embeds.default.description", loc, {"amount": reward})

            await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
    
    @group.command(name='history', description=app_commands.locale_str("command.economy.history.description"))
    async def history(self, interaction: Interaction, limit: app_commands.Range[int, 1, 12]):
        await interaction.response.defer()

        loc = await self.get_loc(interaction)
        
        limit = max(1, min(12, limit))

        embed = Embed()

        if self.db:
            rows = await self.db.get_history(interaction.user.id, limit)

            if not rows:
                embed.title = i18n.T("error.embeds.no_transactions.title", loc)
                embed.description = i18n.T("error.embeds.no_transactions.description", loc)

                return await interaction.followup.send(embed=embed)
            
            embed.description = i18n.T("command.economy.history.embeds.default.description", loc)
            embed.color = Color.blue()

            for row in rows:
                date_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(row['timestamp']))
                sign = "+" if row['amount'] >= 0 else "-"

                embed.add_field(
                    name=f"[{row['type'].upper()}] {sign}{row['amount']:,}",
                    value=f"_{date_str}_\n{row['description']}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
        else:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)
    
async def setup(bot):
    await bot.add_cog(EconomyCog(bot))