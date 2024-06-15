
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}

@Client.on_message(filters.text & filters.incoming & filters.group)
async def give_filter(client, message: Message):
    glob = await global_filters(client, message)
    if not glob:
        manual = await manual_filters(client, message)
        if not manual:
            settings = await get_settings(message.chat.id)
            if settings.get('auto_ffilter', False):
                await auto_filter(client, message)
            else:
                grpid = await active_connection(str(message.from_user.id))
                await save_group_settings(grpid, 'auto_ffilter', True)
                settings = await get_settings(message.chat.id)
                if settings.get('auto_ffilter', False):
                    await auto_filter(client, message)
