# Emote Collector collects emotes from other servers for use by people without Nitro
# Copyright © 2018–2019 lambda#0987
#
# Emote Collector is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Emote Collector is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Emote Collector. If not, see <https://www.gnu.org/licenses/>.

import asyncio
import collections
import contextlib

import discord
from discord.ext.commands import CommandError

# Derived mainly from R.Danny but also from Liara:
# Copyright © 2015 Rapptz

# Copyright © 2016-2017 Pandentia and contributors
# https://github.com/Thessia/Liara/blob/75fa11948b8b2ea27842d8815a32e51ef280a999/cogs/utils/paginator.py

class CannotPaginate(CommandError):
	pass

class Pages:
	"""Implements a paginator that queries the user for the
	pagination interface.

	Pages are 1-index based, not 0-index based.

	If the user does not reply within 2 minutes then the pagination
	interface exits automatically.

	Parameters
	------------
	ctx: Context
		The context of the command.
	entries: List[str]
		A list of entries to paginate.
	per_page: int
		How many entries show up per page.
	show_entry_count: bool
		Whether to show an entry count in the footer.
	timeout: float
		How long to wait for reactions on the message.
	delete_message: bool
		Whether to delete the message when the user presses the stop button.
	delete_message_on_timeout: bool
		Whether to delete the message after the reaction timeout is reached.

	Attributes
	-----------
	embed: discord.Embed
		The embed object that is being used to send pagination info.
		Feel free to modify this externally. Only the description
		and footer fields are internally modified.
	permissions: discord.Permissions
		Our permissions for the channel.
	text_message: Optional[str]
		What to display above the embed.
	"""
	def __init__(self, ctx, *, entries, per_page=7, show_entry_count=True, timeout=120.0,
		delete_message=True, delete_message_on_timeout=False,
	):
		self.bot = ctx.bot
		self.entries = entries
		self.message = ctx.message
		self.channel = ctx.channel
		self.author = ctx.author
		self.per_page = per_page
		pages, left_over = divmod(len(self.entries), self.per_page)
		if left_over:
			pages += 1
		self.maximum_pages = pages
		self.embed = discord.Embed()
		self.paginating = len(entries) > per_page
		self.show_entry_count = show_entry_count
		self.timeout = timeout
		self.delete_message = delete_message
		self.delete_message_on_timeout = delete_message_on_timeout
		self.text_message = None
		self.reaction_emojis = collections.OrderedDict((
			('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
			('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
			('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
			('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
			('\N{INPUT SYMBOL FOR NUMBERS}', self.numbered_page),
			('\N{BLACK SQUARE FOR STOP}', self.stop),
			('\N{INFORMATION SOURCE}', self.show_help),
		))

		if ctx.guild is not None:
			self.permissions = self.channel.permissions_for(ctx.guild.me)
		else:
			self.permissions = self.channel.permissions_for(ctx.bot.user)

		if not self.permissions.embed_links:
			raise CannotPaginate(_('Bot does not have embed links permission.'))

		if not self.permissions.send_messages:
			raise CannotPaginate(_('Bot cannot send messages.'))

		if self.paginating:
			# verify we can actually use the pagination session
			if not self.permissions.add_reactions:
				raise CannotPaginate(_('Bot does not have add reactions permission.'))

			if not self.permissions.read_message_history:
				raise CannotPaginate(_('Bot does not have Read Message History permission.'))

	def get_page(self, page):
		base = (page - 1) * self.per_page
		return self.entries[base:base + self.per_page]

	def get_content(self, entries, page, *, first=False):
		return self.text_message

	def get_embed(self, entries, page, *, first=False):
		self.prepare_embed(entries, page, first=first)
		return self.embed

	def prepare_embed(self, entries, page, *, first=False):
		p = []
		for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page)):
			p.append(f'{index}. {entry}')

		if self.maximum_pages > 1:
			if self.show_entry_count:
				text = _('Page {page}⁄{self.maximum_pages} ({num_entries} entries)').format(
					num_entries=len(self.entries),
					**locals())
			else:
				text = _('Page {page}⁄{self.maximum_pages}').format(**locals())

			self.embed.set_footer(text=text)

		if self.paginating and first:
			p.append('')
			p.append(_('Confused? React with \N{INFORMATION SOURCE} for more info.'))

		self.embed.description = '\n'.join(p)

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)
		content = self.get_content(entries, page, first=first)
		embed = self.get_embed(entries, page, first=first)

		if not self.paginating:
			return await self.channel.send(content=content, embed=embed)

		if not first:
			await self.message.edit(content=content, embed=embed)
			return

		self.message = await self.channel.send(content=content, embed=embed)
		await self.add_reactions()

	async def add_reactions(self):
		for reaction in self.reaction_emojis:
			if self.maximum_pages == 2 and reaction in {'⏮', '⏭'}:
				# no |<< or >>| buttons if we only have two pages
				# we can't forbid it if someone ends up using it but remove
				# it from the default set
				continue

			with contextlib.suppress(discord.HTTPException):
				await self.message.add_reaction(reaction)

	async def checked_show_page(self, page):
		if page != 0 and page <= self.maximum_pages:
			await self.show_page(page)

	async def first_page(self):
		"""goes to the first page"""
		await self.show_page(1)

	async def last_page(self):
		"""goes to the last page"""
		await self.show_page(self.maximum_pages)

	async def next_page(self):
		"""goes to the next page"""
		await self.checked_show_page(self.current_page + 1)

	async def previous_page(self):
		"""goes to the previous page"""
		await self.checked_show_page(self.current_page - 1)

	async def show_current_page(self):
		if self.paginating:
			await self.show_page(self.current_page)

	async def numbered_page(self):
		"""lets you type a page number to go to"""

		to_delete = []
		to_delete.append(await self.channel.send(_('What page do you want to go to?')))

		def message_check(m):
			return m.author == self.author and \
				   self.channel == m.channel and \
				   m.content.isdigit()

		try:
			msg = await self.bot.wait_for('message', check=message_check, timeout=30.0)
		except asyncio.TimeoutError:
			to_delete.append(await self.channel.send(_('You took too long.')))
			await asyncio.sleep(5)
		else:
			page = int(msg.content)
			to_delete.append(msg)
			if page != 0 and page <= self.maximum_pages:
				await self.show_page(page)
			else:
				to_delete.append(await self.channel.send(_(
					'Invalid page given. ({page}/{self.maximum_pages})').format(**locals())))
				await asyncio.sleep(5)

		for message in to_delete:
			# we could use self.channel.delete_messages, but doing so would stop as soon as one of them fails
			# doing it this way ensures all of them are deleted
			with contextlib.suppress(discord.HTTPException):
				await message.delete()

	async def show_help(self):
		"""shows this message"""

		messages = [_('Welcome to the interactive paginator!\n')]
		messages.append(_('This interactively allows you to see pages of text by navigating with '
						  'reactions. They are as follows:\n'))

		for emoji, func in self.reaction_emojis.items():
			messages.append(f'{emoji} {func.__doc__}')

		self.embed.description = '\n'.join(messages)
		self.embed.clear_fields()
		self.embed.set_footer(
			text=_('We were on page {self.current_page} before this message.').format(**locals()))
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(60.0)
			await self.show_current_page()

		self.bot.loop.create_task(go_back_to_current_page())

	async def stop(self, *, delete=None):
		"""stops the interactive pagination session"""

		if delete is None:
			delete = self.delete_message

		if delete:
			with contextlib.suppress(discord.HTTPException):
				await self.message.delete()
		else:
			await self._clear_reactions()

		self.paginating = False

	async def _clear_reactions(self):
		try:
			await self.message.clear_reactions()
		except discord.Forbidden:
			for emoji in self.reaction_emojis:
				with contextlib.suppress(discord.HTTPException):
					await self.message.remove_reaction(emoji, self.message.author)
		except discord.HTTPException:
			pass

	def react_check(self, reaction, user):
		if user is None or user.id != self.author.id:
			return False

		if reaction.message.id != self.message.id:
			return False

		try:
			self.match = self.reaction_emojis[reaction.emoji]
		except KeyError:
			return False
		return True

	async def begin(self):
		"""Actually paginate the entries and run the interactive loop if necessary."""

		first_page = self.show_page(1, first=True)
		if not self.paginating:
			await first_page
		else:
			# allow us to react to reactions right away if we're paginating
			self.bot.loop.create_task(first_page)

		while self.paginating:
			try:
				reaction, user = await self.bot.wait_for(
					'reaction_add',
					check=self.react_check,
					timeout=self.timeout)
			except asyncio.TimeoutError:
				await self.stop(delete=self.delete_message_on_timeout)
				break

			await asyncio.sleep(0.2)
			with contextlib.suppress(discord.HTTPException):
				await self.message.remove_reaction(reaction, user)

			await self.match()

class FieldPages(Pages):
	"""
	Similar to Pages except entries should be a list of
	tuples having (key, value) to show as embed fields instead.
	"""

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)

		self.embed.clear_fields()
		self.embed.description = discord.Embed.Empty

		for key, value in entries:
			self.embed.add_field(name=key, value=value, inline=False)

		if self.maximum_pages > 1:
			if self.show_entry_count:
				text = _('Page {page}⁄{self.maximum_pages} ({num_entries} entries)').format(
					num_entries=len(self.entries),
					**locals())
			else:
				text = _('Page {page}⁄{self.maximum_pages}').format(**locals())

			self.embed.set_footer(text=text)

		kwargs = {'embed': self.embed}
		if self.text_message:
			kwargs['content'] = self.text_message

		if not self.paginating:
			return await self.channel.send(**kwargs)

		if not first:
			await self.message.edit(**kwargs)
			return

		self.message = await self.channel.send(**kwargs)
		await self.add_reactions()
