from aiocache import cached
import aiohttp
from discord import Color, Embed, Interaction, app_commands
from discord.ext import commands
import random
import string

from typing import Optional

from bot import PoxBot
import data
import stuff
import ciphers

def zalgo(text, Z):
    marks = list(map(chr, range(768, 879)))
    words = text.split()
    result = ' '.join(
        ''.join(
            c + ''.join(random.choice(marks) for _ in range((i // 2 + 1) * Z)) if c.isalnum() else c
            for c in word
        )
        for i, word in enumerate(words)
    )
    return result

class ConversionCog(commands.Cog):
    def __init__(self,bot):
        self.bot: PoxBot = bot
    
    converter_group = app_commands.Group(name="convert",description="Commands for Converters")

    @cached(60)
    @converter_group.command(name="meow",description="makes text to MEOW MEOW.")
    @app_commands.describe(text="Text to be meowified")
    async def meowify(self, ctx: Interaction, text: str):
        await ctx.response.defer(thinking=True)
        try:
            await ctx.followup.send(stuff.meow_phrase_weighted(text))
        except Exception as e:
            await ctx.followup.send(f"Error occured! {e}")

    @cached(60)
    @converter_group.command(name="uwu", description="same with say_uwuify, but with mention lol")
    @app_commands.describe(text="Text to be uwuified")
    async def uwuify(self, ctx: Interaction, text: str):
        await ctx.response.defer(thinking=True)
        
        try:
            await ctx.followup.send(f"<@{ctx.user.id}>: {stuff.to_uwu(text)}")
        except Exception as e:
            await ctx.followup.send(f"Error. {e}")

    @cached(60)
    @converter_group.command(name="base64", description="Makes your message into base64")
    @app_commands.describe(text="Text to be base64-ified")
    async def base64ify(self, ctx: Interaction, text: str):
        await ctx.response.defer(thinking=True)
        
        try:
            await ctx.followup.send(f"<@{ctx.user.id}>: {stuff.base64_encode(text)}")
        except Exception as e:
            await ctx.followup.send(f"Error. {e}")

    @cached(60)
    @converter_group.command(name="unbase64", description="Makes your base64 message decoded")
    @app_commands.describe(text="Base64 to be textified")
    async def debase64ify(self, ctx: Interaction, text: str):
        await ctx.response.defer(thinking=True)
        
        try:
            await ctx.followup.send(f"<@{ctx.user.id}>: {stuff.base64_decode(text)}")
        except Exception as e:
            await ctx.followup.send(f"Error. {e}")

    @cached(60)
    @converter_group.command(name="muffle", description="muffles your response")
    @app_commands.describe(text="Message to be MMMPHHHH-ified")
    async def mmphify(self, ctx: Interaction, text: str):
        await ctx.response.defer(thinking=True)
        try:
            await ctx.followup.send(stuff.muffle(text))
        except Exception as e:
            await ctx.followup.send(f"Error: {e} 3:")

    @cached(60)
    @converter_group.command(name="base7777", description="Base 7777 by galaxy_fl3x")
    async def base7777ify(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        splitted1 = list(data.alphabet)
        splitted2 = list(data.base7777_key)
        result = ""
        for char in list(text):
            try:
                index = splitted1.index(char)
            except ValueError:
                result += char
                continue
            result += splitted2[index]
        
        await interaction.followup.send(result)

    @cached(60)
    @converter_group.command(name="unbase7777", description="Base 7777 by galaxy_fl3x")
    async def debase7777ify(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        splitted1 = list(data.alphabet)
        splitted2 = list(data.base7777_key)
        result = ""
        for char in list(text):
            try:
                index = splitted1.index(char)
            except ValueError:
                result += char
                continue
            result += splitted1[index]
        
        await interaction.followup.send(result)

    @cached(60)
    @converter_group.command(name="glitch", description="Makes the text corrupted.")
    async def zalgo_text(self, interaction: Interaction, text:  str, level: Optional[int] = 2):
        if level is None: level = 2
        level = stuff.clamp(level, 1, 3)
        result = zalgo(text, 2)

        await interaction.response.send_message(result)

    @cached(60)
    @converter_group.command(name="nsrc1", description="Converts text into NSRC-1 Encoded")
    async def nsrc1(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        
        alphabet = string.ascii_letters + string.digits
        reversed = alphabet[::-1]
        trans1 = str.maketrans(alphabet,reversed)
        
        shift = 6
        shifted = alphabet[shift:] + alphabet[:shift]
        trans2 = str.maketrans(alphabet, shifted)

        ciphered_1 = text.translate(trans1)
        ciphered_2 = ciphered_1.translate(trans2)

        await interaction.followup.send(ciphered_2)

    @cached(60)
    @converter_group.command(name="un_nsrc1", description="Decodes NSRC-1 into text")
    async def un_nsrc1(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        
        alphabet = string.ascii_letters + string.digits
        reversed = alphabet[::-1]
        trans1 = str.maketrans(reversed,alphabet)
        
        shift = -6
        shifted = alphabet[shift:] + alphabet[:shift]
        trans2 = str.maketrans(alphabet, shifted)

        ciphered_1 = text.translate(trans2)
        ciphered_2 = ciphered_1.translate(trans1)

        await interaction.followup.send(ciphered_2)

    @cached(60)
    @converter_group.command(name="invert_letters", description="Makes the word inverts per letter.")
    async def letterreverse(self, interaction: Interaction, text: str):
        await interaction.response.send_message(ciphers.letter_reverser(text,False))
    
    @cached(60)
    @converter_group.command(name="caesar_cipher", description="Encrypts text by Caesar Cipher.")
    async def caesar(self, interaction: Interaction, text: str, shift: int):
        await interaction.response.send_message(ciphers.caesar_cipher(text,shift,False))
    
    @cached(60)
    @converter_group.command(name="uncaesar_cipher", description="Decrypts text by Caesar Cipher.")
    async def decaesar(self, interaction: Interaction, text: str, shift: int):
        await interaction.response.send_message(ciphers.caesar_cipher(text,shift,True))
    
    @cached(60)
    @converter_group.command(name="rail_fence", description="Encrypts text by Rail fence Cipher.")
    async def railfence(self, interaction: Interaction, text: str, key: int):
        await interaction.response.send_message(ciphers.rail_fence(text,key))
    
    @cached(60)
    @converter_group.command(name="unrail_fence", description="Decrypts text by Rail fence Cipher.")
    async def unrailfence(self, interaction: Interaction, text: str, key: int):
        await interaction.response.send_message(ciphers.decrypt_rail_fence(text,key))
    
    @cached(60)
    @converter_group.command(name="morse_code", description="Converts text to morse code. (by AnnaYarik13Alt)")
    async def morse_codify(self, interaction: Interaction, text: str):
        await interaction.response.send_message(f"`{ciphers.morse_code(text)}`")
    
    @cached(60)
    @converter_group.command(name="binary", description="Converts text to binary. (by AnnaYarik13Alt)")
    async def binarify(self, interaction: Interaction, text: str):
        await interaction.response.send_message(f"`{ciphers.binary(text)}`")
    
    @cached(60)
    @converter_group.command(name="demorse_code", description="Converts morse code to text. (by AnnaYarik13Alt)")
    async def demorse_codify(self, interaction: Interaction, text: str):
        await interaction.response.send_message({ciphers.morse_code(text,True)})
    
    @cached(60)
    @converter_group.command(name="unbinary", description="Converts binary to text. (by AnnaYarik13Alt)")
    async def unbinarify(self, interaction: Interaction, text: str):
        await interaction.response.send_message(ciphers.binary(text,True))
    
    @cached(60)
    @converter_group.command(name="reverse_words", description="Reverses text per words.")
    async def reverser(self, interaction: Interaction, text: str):
        vce = ' '.join(word[::-1] for word in text.split(" "))
        await interaction.response.send_message(vce)
    
    @cached(60)
    @converter_group.command(name="color_name", description="Retrieves color name from colornames.org.")
    async def color_name(self, interaction: Interaction, hex: str):
        await interaction.response.defer()

        hex = stuff.expand_hex(hex)

        embed = Embed(title=f"Color name of {hex}")

        cached = self.bot.cache.get(f'colornames.org_{hex}')

        if not cached:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://colornames.org/search/json/?hex={hex}") as response:
                    if response.status != 200:
                        embed.description = "Couldn't get info."
                        return await interaction.followup.send(embed=embed)

                    data = await response.json()

                    if not isinstance(data, dict) or not data:
                        embed.description = "The response is invalid or empty."
                        return await interaction.followup.send(embed=embed)
                    
                    cached = data
                    self.bot.cache.set(f'colornames.org_{hex}', cached)
        
        if not isinstance(cached, dict) or not cached:
            embed.description = "Retrieved data is not valid."
            return await interaction.followup.send(embed=embed)

        embed.description = f"**{cached.get('name', "Unknown")}**"
        embed.color = Color.from_str(f"#{hex}")

        return await interaction.followup.send(embed=embed)
    
    @cached(60)
    @converter_group.command(name="psc1", description="Converts text into PSC-1 Encoded")
    async def psc1(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        
        output = None

        try:
            output = ciphers.psc1(text, False)
        except Exception as e:
            return await interaction.followup.send(f"Error occured: {e}")
        
        return await interaction.followup.send(output)
    
    @cached(60)
    @converter_group.command(name="un_psc1", description="Decodes PSC-1 into text")
    async def un_psc1(self, interaction: Interaction, text: str):
        await interaction.response.defer(thinking=True)
        
        output = None

        try:
            output = ciphers.psc1(text, True)
        except Exception as e:
            return await interaction.followup.send(f"Error occured: {e}")
        
        return await interaction.followup.send(output)
    
# i will add this but not this time :(
# https://colornames.org/search/json/?hex=FF0000

async def setup(bot):
    await bot.add_cog(ConversionCog(bot))