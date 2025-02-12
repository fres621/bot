import random
import asyncio
from interactions import *
from utilities.emojis import emojis, make_url
from datetime import datetime, timedelta
from utilities.database.main import UserData
from utilities.localization import Localization, fnum
from utilities.message_decorations import Colors, fancy_message

wool_finds = {
    5: [ "devoted", "positive_major"],
    20: [ "unhappy", "negative_normal"],
    30: [ "yippie", 'positive_normal'],
    40: [ "misdeed", 'negative_minimum'],
    70: [ "despise", 'negative_major'],
    100: [ "ogie", 'positive_minimum']
}
wool_values = {
    'positive_minimum': [ 5_000, 30_000 ],
    'positive_normal': [ 10_000, 30_000 ],
    'positive_major': [ 100_000, 500_000 ],
    'negative_minimum': [-100, -500],
    'negative_normal': [-1_000, -3_000],
    'negative_major': [-5_000, -10_000]
}


class WoolCommands(Extension):

	@slash_command(description='All things to do with wool')
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def wool(self, ctx: SlashContext):
		pass

	@wool.subcommand(sub_cmd_description='View your balance')
	@slash_option(description='The person you want to view balance of instead', name='of', opt_type=OptionType.USER)
	@slash_option(description="Whether you want the response to be visible for others in the channel", name="public", opt_type=OptionType.BOOLEAN)
	async def balance(self, ctx: SlashContext, of: User = None, public: bool = False):
		await ctx.defer(ephemeral=not public)
		loc = Localization(ctx.locale)
		if of is None:
			of = ctx.user

		user_data: UserData = await UserData(of.id).fetch()
		wool: int = user_data.wool
		who_path = "other"
		if public == False and of == ctx.user:
			who_path = "you"
		if of == ctx.client.user:
			who_path = "twm"
		elif of.bot:
			who_path = "bot"
		return await fancy_message(ctx, loc.l(f'wool.balance.{who_path}.{"none" if wool == 0 else "some"}', mention=of.mention, balance=fnum(wool, locale=ctx.locale)), edit=True)

	@wool.subcommand(sub_cmd_description='Give away some of your wool')
	@slash_option(description='Who would you like to give?', name='to', required=True, opt_type=OptionType.USER)
	@slash_option(description='How much wool would you like to give them?', name='amount', required=True, opt_type=OptionType.INTEGER, min_value=-1)
	async def give(self, ctx: SlashContext, to: User, amount: int):
		loc = Localization(ctx.locale)
		if to.id == ctx.author.id:
			return await fancy_message(ctx, loc.l("wool.transfer.errors.self_transfer"), ephemeral=True, color=Colors.BAD)

		if to.bot and not (amount <= 0):
			buttons = [
			    Button(style=ButtonStyle.RED, label=loc.l('general.buttons._yes'), custom_id=f'yes'),
			    Button(style=ButtonStyle.GRAY, label=loc.l('general.buttons._no'), custom_id=f'no')
			]

			confirmation_m = await fancy_message(ctx, message=loc.l("wool.transfer.to.bot.confirmation"), color=Colors.WARN, components=buttons, ephemeral=True)
			try:
				await ctx.client.wait_for_component(messages=confirmation_m, timeout=60.0 * 1000)
				await ctx.delete(confirmation_m)
			except asyncio.TimeoutError:
				await confirmation_m.edit(content=loc.l("general.responses.timeout.yn"), components=[])
				await ctx.delete()
				await asyncio.sleep(15)
				await confirmation_m.delete()

		loading = await fancy_message(ctx, loc.l('general.loading'))
		from_user: UserData = await UserData(ctx.author.id).fetch()
		to_user: UserData = await UserData(to.id).fetch()

		if from_user.wool < amount:
			return await fancy_message(ctx, loc.l("wool.transfer.errors.not_enough", balance=fnum(from_user.wool, locale=ctx.locale)), edit=True, ephemeral=True, color=Colors.BAD)

		await from_user.manage_wool(-amount)
		await to_user.manage_wool(amount)

		if amount < 0:
			return await fancy_message(loading, loc.l("wool.transfer.steal", user_one=ctx.author.mention, user_two=to.mention), edit=True)
		await fancy_message(
		    loading,
		    loc.l(f'wool.transfer.to.{"bot" if to.bot else "user"}.{"none" if amount == 0 else "some"}', user_one=ctx.author.mention, user_two=to.mention, amount=amount),
		    edit=True
		)

	@slash_command(description="Pray to The World Machine")
	async def pray(self, ctx: SlashContext):
		loc = Localization(ctx.locale)

		user_data: UserData = await UserData(ctx.author.id).fetch()
		last_reset_time = user_data.daily_wool_timestamp

		now = datetime.now()

		if now < last_reset_time:
			time_unix = last_reset_time.timestamp()
			return await fancy_message(ctx, loc.l("wool.pray.errors.timeout", timestamp_relative=f"<t:{int(time_unix)}:R>"), ephemeral=True, color=Colors.BAD)
		# TODO: use silly relative timestamp function

		# reset the limit if it is a new day
		if now >= last_reset_time:
			reset_time = datetime.combine(now.date(), now.time()) + timedelta(days=1)
			await user_data.update(daily_wool_timestamp=reset_time)
		rolled = random.randint(0, 100)

		finding = wool_finds[min(wool_finds.keys(), key=lambda k: abs(k - rolled))]
		amount = wool_values[finding[1]]
		amount = int(random.uniform(amount[0], amount[1]))

		await user_data.manage_wool(amount)

		await ctx.send(
		    embed=Embed(
		        thumbnail=make_url(emojis["treasures"]["die"]),
		        title=loc.l("wool.pray.title"),
		        description=f"{loc.l(f'wool.pray.finds.{finding[0]}')}\n-# " + loc.l(f"wool.pray.Change.{'gain' if amount > 0 else 'loss'}", amount=abs(amount)),
		        color=Colors.GREEN if amount > 0 else Colors.BAD
		    )
		)
