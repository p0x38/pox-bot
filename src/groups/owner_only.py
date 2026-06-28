from discord import Interaction, app_commands


class AdminGroup(app_commands.Group):
    async def interaction_check(self, interaction: Interaction) -> bool:
        app = interaction.client.application

        if not app:
            return False

        if app.owner.id == interaction.user.id:
            return True

        team = app.team
        if team is not None:
            return any(m.id == interaction.user.id for m in team.members)

        return False
