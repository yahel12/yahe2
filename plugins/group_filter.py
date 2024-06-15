
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


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    try:
        offset = int(offset)
    except ValueError:
        offset = 0
    
    search = BUTTONS.get(key)
    if not search:
        await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        return

    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except ValueError:
        n_offset = 0

    if not files:
        return
    
    settings = await get_settings(query.message.chat.id)

    btn = [
        [
            InlineKeyboardButton(
                text=f"➲ {get_size(file.file_size)} || {file.file_name}", callback_data=f'files#{file.file_id}'
            ),
        ]
        for file in files
    ] if settings.get('button', False) else [
        [
            InlineKeyboardButton(
                text=f"{file.file_name}", callback_data=f'files#{file.file_id}'
            ),
            InlineKeyboardButton(
                text=f"{get_size(file.file_size)}",
                callback_data=f'files_#{file.file_id}',
            ),
        ]
        for file in files
    ]
    
    if settings.get('auto_delete', True):
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/Adultship_films')])
    
    max_btn = settings.get('max_btn', True)
    max_b_tn_value = int(MAX_B_TN) if max_btn else 10
    if 0 < offset <= max_b_tn_value:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - max_b_tn_value

    if n_offset == 0:
        btn.append(
            [InlineKeyboardButton("«« 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset) / max_b_tn_value) + 1} / {math.ceil(total / max_b_tn_value)}", callback_data="pages")]
        )
    elif off_set is None:
        btn.append([InlineKeyboardButton("📑 ᴩᴀɢᴇꜱ", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset) / max_b_tn_value) + 1} / {math.ceil(total / max_b_tn_value)}", callback_data="pages"), InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append(
            [
                InlineKeyboardButton("«« 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{math.ceil(int(offset) / max_b_tn_value) + 1} / {math.ceil(total / max_b_tn_value)}", callback_data="pages"),
                InlineKeyboardButton("𝕹𝖊𝖝𝖙 »»", callback_data=f"next_{req}_{key}_{n_offset}")
            ],
        )
    
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    
    await query.answer()

