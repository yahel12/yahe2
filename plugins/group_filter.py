import asyncio, re, ast, math, logging
import pyrogram
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script 
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from info import SPELL_CHECK_REPLY, ADMINS, AUTH_CHANNEL, AUTH_USERS, CUSTOM_FILE_CAPTION, MSG_ALRT, GRP_LNK, CHNL_LNK, LOG_CHANNEL, MAX_B_TN

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums 
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, get_poster, temp, search_gagala, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, Media2, get_file_details, get_search_results, get_bad_files, db as clientDB, db2 as clientDB2
from database.filters_mdb import del_all, find_filter, get_filters
from database.gfilters_mdb import find_gfilter, get_gfilters, del_allg

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}

@Client.on_message(filters.text & filters.incoming & filters.group)
async def give_filter(client, message):
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

    # Answer the callback query immediately
    await query.answer()

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
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/+YGA7EOwVVB84ZTc8')])

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
            [InlineKeyboardButton("«« 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"📑 ᴩᴀɢᴇꜱ {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages")]
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"📑 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
             InlineKeyboardButton("𝕹𝖊𝖝𝖙 »»", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append(
            [
                InlineKeyboardButton("«« 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"📑 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
                InlineKeyboardButton("𝕹𝖊𝖝𝖙 »»", callback_data=f"next_{req}_{key}_{n_offset}")
            ],
        )

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("okDa", show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer("𝐋𝐢𝐧𝐤 𝐄𝐱𝐩𝐢𝐫𝐞𝐝 𝐊𝐢𝐧𝐝𝐥𝐲 𝐏𝐥𝐞𝐚𝐬𝐞 𝐒𝐞𝐚𝐫𝐜𝐡 𝐀𝐠𝐚𝐢𝐧 🙂.", show_alert=True)
    movie = movies[(int(movie_))]
    await query.answer('𝙸 𝙰𝙼 𝙲𝙷𝙴𝙲𝙺𝙸𝙽𝙶 𝙵𝙾𝚁 𝚃𝙷𝙴 𝙵𝙸𝙻𝙴 𝙾𝙽 𝙼𝚈 𝙳𝙰𝚃𝙰𝙱𝙰𝚂𝙴...⏳')
    k = await manual_filters(bot, query.message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            k = await query.message.edit('The file you are looking for is not available on my Database or might not be released yet 💌')
            await asyncio.sleep(20)
            await k.delete()



async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(message.chat.id, search.lower(), offset=0, filter=True)
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(client, msg)
                return
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
        settings = await get_settings(message.chat.id)

    temp.KEYWORD[message.from_user.id] = search

    pre = 'filep' if settings['file_secure'] else 'file'

    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"➲ {get_size(file.file_size)} || {file.file_name}",
                    callback_data=f'{pre}#{file.file_id}'
                ),
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"{file.file_name}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"{get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
            ]
            for file in files
        ]

    try:
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/+YGA7EOwVVB84ZTc8')])
    except KeyError:
        await save_group_settings(message.chat.id, 'auto_delete', True)
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/+YGA7EOwVVB84ZTc8al')])

    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [InlineKeyboardButton(text=f"📑 ᴩᴀɢᴇꜱ 1/{math.ceil(int(total_results) / 6)}", callback_data="pages"),
             InlineKeyboardButton(text="𝕹𝖊𝖝𝖙 »»", callback_data=f"next_{req}_{key}_{offset}")]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="📑 ᴩᴀɢᴇꜱ 1/1", callback_data="pages")]
        )

    imdb = await get_poster(search, file=files[0].file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    cap = TEMPLATE.format(
        query=search,
        title=imdb['title'],
        votes=imdb['votes'],
        aka=imdb["aka"],
        seasons=imdb["seasons"],
        box_office=imdb['box_office'],
        localized_title=imdb['localized_title'],
        kind=imdb['kind'],
        imdb_id=imdb["imdb_id"],
        cast=imdb["cast"],
        runtime=imdb["runtime"],
        countries=imdb["countries"],
        certificates=imdb["certificates"],
        languages=imdb["languages"],
        director=imdb["director"],
        writer=imdb["writer"],
        producer=imdb["producer"],
        composer=imdb["composer"],
        cinematographer=imdb["cinematographer"],
        music_team=imdb["music_team"],
        distributors=imdb["distributors"],
        release_date=imdb['release_date'],
        year=imdb['year'],
        genres=imdb['genres'],
        poster=imdb['poster'],
        plot=imdb['plot'],
        rating=imdb['rating'],
        url=imdb['url'],
        **locals()
    ) if imdb else f"<code>{search}</code>"

    try:
        if imdb and imdb.get('poster'):
            hehe = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
            await handle_auto_delete(hehe, message, settings)
        else:
            fuk = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
            await handle_auto_delete(fuk, message, settings)
    except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
        poster = imdb.get('poster').replace('.jpg', "._V1_UX360.jpg") if imdb and imdb.get('poster') else None
        if poster:
            hmm = await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
            await handle_auto_delete(hmm, message, settings)
        else:
            fek = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
            await handle_auto_delete(fek, message, settings)
    except Exception as e:
        logger.exception(e)
        fek = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
        await handle_auto_delete(fek, message, settings)

    if spoll:
        await msg.message.delete()

async def handle_auto_delete(msg, original_msg, settings):
    try:
        if settings['auto_delete']:
            await asyncio.sleep(180)
            await msg.delete()
            await original_msg.delete()
    except KeyError:
        await save_group_settings(original_msg.chat.id, 'auto_delete', True)
        await asyncio.sleep(180)
        await msg.delete()
        await original_msg.delete()

async def advantage_spell_chok(client, msg):
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)  # plis contribute some common words
    query = query.strip() + " movie"
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    gs_parsed = []
    if not g_s:
        k = await msg.reply("<b>💔 I couldn't find any movie in that name.</b>")
        await asyncio.sleep(8)
        await k.delete()
        return
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)  # look for imdb / wiki results
    gs = list(filter(regex.match, g_s))
    gs_parsed = [re.sub(
        r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)',
        '', i, flags=re.IGNORECASE) for i in gs]
    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*",
                         re.IGNORECASE)  # match something like Watch Niram | Amazon Prime
        for mv in g_s:
            match = reg.match(mv)
            if match:
                gs_parsed.append(match.group(1))
    user = msg.from_user.id if msg.from_user else 0
    movielist = []
    gs_parsed = list(dict.fromkeys(gs_parsed))  # removing duplicates https://stackoverflow.com/a/7961425
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]
    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)  # searching each keyword in imdb
            if imdb_s:
                movielist += [movie.get('title') for movie in imdb_s]
    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))  # removing duplicates
    if not movielist:
        k = await msg.reply("<b>💔 I couldn't find anything related to that. Check your spelling</b>")
        await asyncio.sleep(8)
        await k.delete()
        return
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=movie.strip(),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f'spolling#{user}#close_spellcheck')])
    await msg.reply("<b>💔 I couldn't find anything related to that</b>\n\n𝙸𝚏 𝚝𝚑𝚎 𝚏𝚒𝚕𝚎 𝚢𝚘𝚞 𝚠𝚊𝚗𝚝 𝚒𝚜 𝚝𝚑𝚎 𝚘𝚗𝚎 𝚋𝚎𝚕𝚘𝚠, 𝚌𝚕𝚒𝚌𝚔 𝚘𝚗 𝚒𝚝",
                    reply_markup=InlineKeyboardMarkup(btn))



async def manual_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            try:
                if fileid == "None":
                    await send_manual_message(client, group_id, reply_text, btn, settings, reply_id, message)
                else:
                    await send_manual_media(client, message, group_id, reply_text, btn, fileid, settings, reply_id)
            except Exception as e:
                logger.exception(e)
            break
    else:
        return False

async def send_manual_message(client, group_id, reply_text, btn, settings, reply_id, message):
    if btn == "[]":
        joelkb = await client.send_message(
            group_id,
            reply_text,
            disable_web_page_preview=True,
            protect_content=True if settings["file_secure"] else False,
            reply_to_message_id=reply_id
        )
    else:
        button = eval(btn)
        joelkb = await client.send_message(
            group_id,
            reply_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(btn),
            protect_content=True if settings["file_secure"] else False,
            reply_to_message_id=reply_id
        )
    await handle_manual_auto_filter(client, message, joelkb, settings)

async def send_manual_media(client, message, group_id, reply_text, btn, fileid, settings, reply_id):
    if btn == "[]":
        joelkb = await client.send_cached_media(
            group_id,
            fileid,
            caption=reply_text or "",
            protect_content=True if settings["file_secure"] else False,
            reply_to_message_id=reply_id
        )
    else:
        button = eval(btn)
        joelkb = await message.reply_cached_media(
            fileid,
            caption=reply_text or "",
            reply_markup=InlineKeyboardMarkup(btn),
            reply_to_message_id=reply_id
        )
    await handle_manual_auto_filter(client, message, joelkb, settings)

async def handle_manual_auto_filter(client, message, joelkb, settings):
    try:
        if settings['auto_ffilter']:
            await auto_filter(client, message)
            await handle_manual_auto_delete(joelkb, settings)
        else:
            await handle_manual_auto_delete(joelkb, settings)
    except KeyError:
        grpid = await active_connection(str(message.from_user.id))
        await save_group_settings(grpid, 'auto_ffilter', True)
        settings = await get_settings(message.chat.id)
        if settings['auto_ffilter']:
            await auto_filter(client, message)
        await handle_manual_auto_delete(joelkb, settings)

async def handle_manual_auto_delete(joelkb, settings):
    if settings.get('auto_delete', False):
        await asyncio.sleep(180)
        await joelkb.delete()


async def global_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_gfilters('gfilters')
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_gfilter('gfilters', keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            try:
                if fileid == "None":
                    await send_global_message(client, group_id, reply_text, btn, settings, reply_id, message)
                else:
                    await send_global_media(client, message, group_id, reply_text, btn, fileid, settings, reply_id)
            except Exception as e:
                logger.exception(e)
            break
    else:
        return False

async def send_global_message(client, group_id, reply_text, btn, settings, reply_id, message):
    if btn == "[]":
        joelkb = await client.send_message(
            group_id,
            reply_text,
            disable_web_page_preview=True,
            reply_to_message_id=reply_id
        )
    else:
        button = eval(btn)
        joelkb = await client.send_message(
            group_id,
            reply_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(btn),
            reply_to_message_id=reply_id
        )
    await handle_global_auto_filter(client, message, joelkb, settings)

async def send_global_media(client, message, group_id, reply_text, btn, fileid, settings, reply_id):
    if btn == "[]":
        joelkb = await client.send_cached_media(
            group_id,
            fileid,
            caption=reply_text or "",
            reply_to_message_id=reply_id
        )
    else:
        button = eval(btn)
        joelkb = await message.reply_cached_media(
            fileid,
            caption=reply_text or "",
            reply_markup=InlineKeyboardMarkup(btn),
            reply_to_message_id=reply_id
        )
    await handle_global_auto_filter(client, message, joelkb, settings)

async def handle_global_auto_filter(client, message, joelkb, settings):
    manual = await manual_filters(client, message)
    if not manual:
        try:
            if settings['auto_ffilter']:
                await auto_filter(client, message)
                await handle_global_auto_delete(joelkb, settings)
            else:
                await handle_global_auto_delete(joelkb, settings)
        except KeyError:
            grpid = await active_connection(str(message.from_user.id))
            await save_group_settings(grpid, 'auto_ffilter', True)
            settings = await get_settings(message.chat.id)
            if settings['auto_ffilter']:
                await auto_filter(client, message)
            await handle_global_auto_delete(joelkb, settings)
    else:
        await handle_global_auto_delete(joelkb, settings)

async def handle_global_auto_delete(joelkb, settings):
    if settings.get('auto_delete', False):
        await asyncio.sleep(180)
        await joelkb.delete()
