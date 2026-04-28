#### I let you know about this but,
#### don't take it seriously.
#### it come from The Broken Script's Null interactions.

import asyncio
from random import shuffle
import random
import re
from aiocache import cached
from discord.ext import commands
from discord import app_commands, Interaction, Embed, File
from typing import Optional

import os

import profanityfilter

from bot import PoxBot
import data

null_responses = {
    r"(hi|hello|ya|yo)\??": ["err.type=null.hello"],
    r"hey": ["What."],
    r'(are\s?(you|u|yu)\s?)?void': ["It's me."],
    r"who\s?(are|r|are|aer)\s?(you|u|yu)?": ["err.type=null."],
    r"(what|wat)\s?do\s?(you|u|yu)\s?(wants?|wunts?)\?": ["err.type=null.freedom"],
    r"circuit": ["It was all his fault."],
    r"integrity": ["Deep down under the bedrock."],
    r"revuxor": ["Poor soul."],
    r"clan_build": ["Home."],
    r"nothing\s?is\s?(watching|watchin|waching|wacthing|wathcing)": ["A broken promise."],
    r"entity\s?303": ["Ended his own life."],
    r"steve": ["[0.1]"],
    r"herobrine": ["_ _"],
    r"can\s?you\s?see\s?me\??": ["Yes.","Hello."],
    r"follow": ["Is behind you."],
    r"null": ["The end is nigh.","The end is null."],
    r"where\s?it\s?c(o|a)me\s?from\??": ["_ _"],
    r"xxram2diexx": ["Rot in hell."],
    r"friend\??": ["Boo.","Don't ask for a friend."],
    r"how\s?i\s?can\s?help\s?you\??": ["[?][?][?]"],
    r"i'm\s?your\s?fan": ["You shouldn't be here."],
}

pf = profanityfilter.ProfanityFilter(extra_censor_list=[
    "stfu",
    "dum",
    "jap",
    "blyat"
])

class NullCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    nullgroup = app_commands.Group(name="null",description=":)")
    
    @cached(60)
    @nullgroup.command(name="response", description="Null is already here. he's waiting for you. btw don't take it seriously.")
    async def nulltalk(self, interaction: Interaction, *, input: str):
        await interaction.response.defer(thinking=True)
        
        input = input.lower()
        
        if pf.is_profane(input):
            if self.bot.swears_in_row < len(data.nullchill):
                await interaction.followup.send(data.nullchill[self.bot.swears_in_row])
            else:
                await interaction.followup.send("I am not gonna response to your swears too much.")
            self.bot.swears_in_row += 1
            return
        
        self.bot.swears_in_row = 0
        
        for pattern, text_to_show in null_responses.items():
            if re.match(pattern, input) is not None:
                for text in text_to_show:
                    await asyncio.sleep(random.uniform(1,2))
                    await interaction.followup.send(text)
                return
        
        await interaction.followup.send("NullPointerException thrown.")
    
    @cached(240)
    @nullgroup.command(name="kys",description="dead meme i think")
    async def kysimage(self, interaction: Interaction):
        url = os.path.dirname(__file__)
        url2 = os.path.join(url,"../resources/nah.jpg")

        with open(url2, 'rb') as f:
            pic = File(f,"nah.jpg")
        
        e = Embed()
        e.set_image(url="attachment://nah.jpg")
        await interaction.response.send_message(file=pic,embed=e)
    
    @cached(240)
    @nullgroup.command(name="generate", description="Generates random sentence.")
    async def generator(self, interaction: Interaction, index_to_generate: Optional[int], size: Optional[int]):
        await interaction.response.defer()

        choosen1 = []
        if size is None:
            size = 1
        
        for i in range(size):
            if index_to_generate is not None:
                length = len(self.bot.activity_messages)
                if index_to_generate > length:
                    choosen = random.choice(self.bot.activity_messages)
                else:
                    choosen = self.bot.activity_messages[index_to_generate]
            else:
                choosen = random.choice(self.bot.activity_messages)
            
            choosen1.append(choosen)
        
        e = Embed(
            title="Ah.",
            description="",
        )

        e.description = "\n".join(choosen1)

        await interaction.followup.send(embed=e)

async def setup(bot):
    await bot.add_cog(NullCog(bot))