from discord import Color, Embed, File, Interaction, app_commands
from discord.ext import commands

from ....application import PoxBot
from ....features.text_transform.models import TransformerRequest
from ....persistence.models.contributor import ContributorItem


class ContributorsCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.contributors_list: list[ContributorItem] = []

    group = app_commands.Group(
        name='contributors',
        description=app_commands.locale_str('command.contributors.description'),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    async def safe_get_user(self, user_id: int):
        user = self.bot.get_user(user_id)
        if user:
            return user

        try:
            return await self.bot.fetch_user(user_id)
        except Exception:
            return None

    async def cog_load(self) -> None:
        try:
            self.contributors_list = await self.bot.resources.load_contributors_async(
                'json/contributors.v2.json',
            )

            self.bot.logger.info('Successfully pre-loaded contributor data in cog_load')
        except FileNotFoundError:
            self.bot.logger.exception(
                "contributors.v2.json doesn't seems exists. returning empty",
            )
            self.contributors_list = []

    @group.command(
        name='list',
        description=app_commands.locale_str('command.contributors.list.description'),
    )
    async def list_contributors(self, interaction: Interaction):
        loc = await self.bot.get_locale(interaction)

        embed = Embed(
            title=self.bot.internal_translator.T(
                'command.contributors.list.embeds.default.title',
                str(loc),
            ),
            description=self.bot.internal_translator.T(
                'command.contributors.list.embeds.default.description',
                str(loc),
            ),
        )

        await interaction.response.defer()

        hmmm = []
        for contributor in self.contributors_list:
            user_id = contributor.id
            if not user_id:
                continue

            user = await self.safe_get_user(int(user_id))
            name = (
                user.display_name
                if user
                else contributor.command
                or self.bot.internal_translator.T('text.unknown', loc)
            )

            contribution = (
                contributor.description.default
                or self.bot.internal_translator.T('text.unknown', str(loc))
            )

            hmmm.append(f'**{name}**: {contribution}')

        embed.description = '\n'.join(hmmm)
        embed.color = Color.blue()

        return await interaction.followup.send(embed=embed)

    async def contributor_autocomplete(
        self,
        _interaction: Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=contributor.command, value=contributor.command)
            for contributor in self.contributors_list
            if contributor.command and current.lower() in contributor.command.lower()
        ]

    @group.command(
        name='view',
        description=app_commands.locale_str('command.contributors.view.description'),
    )
    @app_commands.autocomplete(contributor_id=contributor_autocomplete)
    async def view_contributor(self, interaction: Interaction, contributor_id: str):
        loc = await self.bot.get_locale(interaction)

        await interaction.response.defer()

        contributor_data = next(
            (d for d in self.contributors_list if d.command == contributor_id),
            None,
        )

        if contributor_data:
            is_scary_active = hasattr(self.bot, 'constants') and getattr(
                self.bot.constants,
                'scary_mode',
                False,
            )

            user_id = contributor_data.id
            user_name = contributor_id
            avatar_url = None

            if user_id:
                user = await self.safe_get_user(int(user_id))
                if user:
                    user_name = user.display_name
                    avatar_url = user.display_avatar.url

            mode = 'scary' if is_scary_active else 'default'

            final_footer = getattr(contributor_data.quote, mode) or ''
            chosen_thumbnail = getattr(contributor_data.thumbnail_url, mode)

            desc_text = (
                contributor_data.description.scary
                if (is_scary_active and contributor_data.description.scary)
                else contributor_data.description.default
            )
            content_data = (
                contributor_data.content.scary
                if (is_scary_active and contributor_data.content.scary)
                else contributor_data.content.default
            )

            if not desc_text:
                desc_text = self.bot.internal_translator.T('text.unknown', str(loc))

            rows = [desc_text, '\n\n']
            if content_data:
                rows.append('\n'.join(content_data))
            final_description = ''.join(rows)

            final_title = self.bot.internal_translator.T(
                'command.contributors.view.embeds.default.title',
                str(loc),
                contributor=user_name,
            )

            if is_scary_active:
                final_title = self.bot.text_converter.transform(
                    'zalgo',
                    TransformerRequest(
                        text=final_title,
                        decode=False,
                    ),
                )
                if (
                    not contributor_data.description.scary
                    and not contributor_data.content.scary
                ):
                    final_description = self.bot.text_converter.transform(
                        'zalgo',
                        TransformerRequest(
                            text=final_description,
                            decode=False,
                        ),
                    )
                if not contributor_data.quote.scary and final_footer:
                    final_footer = self.bot.text_converter.transform(
                        'zalgo',
                        TransformerRequest(
                            text=final_footer,
                            decode=False,
                        ),
                    )

            embed = Embed(
                title=final_title,
                color=Color.blue(),
                description=final_description,
            )
            if final_footer:
                embed.set_footer(text=final_footer)

            pic = None
            if (
                chosen_thumbnail
                and isinstance(chosen_thumbnail, str)
                and chosen_thumbnail.startswith('file:')
            ):
                relative_file_path = chosen_thumbnail.replace('file:', '', 1)
                try:
                    path = self.bot.resources.get_asset_path(relative_file_path)
                    pic = File(fp=path, filename=path.name)
                    avatar_url = f'attachment://{pic.filename}'
                except FileNotFoundError:
                    self.bot.logger.warning(
                        'Contributor asset file missing: %s',
                        relative_file_path,
                    )

            if avatar_url:
                embed.set_thumbnail(url=avatar_url)

            if pic:
                return await interaction.followup.send(embed=embed, file=pic)
            return await interaction.followup.send(embed=embed)
        error_embed = Embed(color=Color.red())
        error_embed.title = self.bot.internal_translator.T(
            'error.embeds.contributor_not_found.title',
            str(loc),
        )
        error_embed.description = self.bot.internal_translator.T(
            'error.embeds.contributor_not_found.description',
            str(loc),
            {'contributor': contributor_id},
        )
        return await interaction.followup.send(embed=error_embed)


async def setup(bot: PoxBot):
    await bot.add_cog(ContributorsCog(bot))
