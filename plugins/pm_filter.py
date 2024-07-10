import asyncio
import re
import ast
import math
import random
import pyrogram
lock = asyncio.Lock()

from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, \
    make_inactive
from info import MAX_B_TN
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, get_poster, temp, get_settings, search_gagala
from database.users_chats_db import db
from database.ia_filterdb import Media, Media2, get_file_details, get_search_results, get_bad_files, db as clientDB, db2 as clientDB2
from plugins.group_filter import global_filters
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}


@Client.on_message(filters.text & filters.private & filters.incoming)
async def auto_pm_fill(b, m):
    glob = await global_filters(b, m)
    if not glob:
        await pm_AutoFilter(b, m)

@Client.on_callback_query(filters.regex(r"^pmnext"))
async def pm_next_page(bot, query):
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
                text=f"➲ {get_size(file.file_size)} || {file.file_name}", callback_data=f'pmfiles#{file.file_id}'
            ),
        ]
        for file in files
    ] if settings.get('button', False) else [
        [
            InlineKeyboardButton(
                text=f"{file.file_name}", callback_data=f'pmfiles#{file.file_id}'
            ),
            InlineKeyboardButton(
                text=f"{get_size(file.file_size)}",
                callback_data=f'pmfiles_#{file.file_id}',
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
            [InlineKeyboardButton("«« 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"pmnext_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"📑 ᴩᴀɢᴇꜱ {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages")]                                  
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"📑 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
             InlineKeyboardButton("𝕹𝖊𝖝𝖙 »»", callback_data=f"pmnext_{req}_{key}_{n_offset}")])
    else:
        btn.append([
            InlineKeyboardButton("<<< 𝕻𝖗𝖊𝖛𝖎𝖔𝖚𝖘", callback_data=f"pmnext_{req}_{key}_{off_set}"),
            InlineKeyboardButton(f"📑 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
            InlineKeyboardButton("𝕹𝖊𝖝𝖙 >>>", callback_data=f"pmnext_{req}_{key}_{n_offset}")
        ])
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()

@Client.on_callback_query(filters.create(lambda _, __, query: query.data.startswith("pmspolling")))
async def pm_spoll_tester(bot, query):
    # Split the callback data to extract user and movie index
    _, user, movie_ = query.data.split('#')

    # If the "close" button is clicked, delete the message
    if movie_ == "close_spellcheck":
        return await query.message.delete()

    # Get the list of movies from the temporary dictionary
    movies = temp.PM_SPELL.get(str(query.message.reply_to_message.id))
    
    # If no movies are found, show an alert
    if not movies:
        return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)

    # Get the selected movie based on the index
    movie = movies[int(movie_)]

    # If movie is selected, show an alert
    await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)

    # Get search results for the selected movie
    files, offset, total_results = await get_search_results(movie, offset=0, filter=True)

    if files:
        # If files are found, call the pm_AutoFilter function
        k = (movie, files, offset, total_results)
        await pm_AutoFilter(bot, query, k)
    else:
        # If no files are found, edit the message to show an error and delete after 10 seconds
        k = await query.message.edit(script.MVE_NT_FND)
        await asyncio.sleep(10)
        await k.delete()

   
async def pm_AutoFilter(client, msg, pmspoll=False):
    if not pmspoll:
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
                    return await pm_spoll_choker(client, msg)
                return
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = pmspoll
        settings = await get_settings(message.chat.id)

    temp.KEYWORD[message.from_user.id] = search

    pre = 'pmfilep' if settings['file_secure'] else 'pmfile'

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
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/Adultship_films')])
    except KeyError:
        await save_group_settings(message.chat.id, 'auto_delete', True)
        btn.insert(0, [InlineKeyboardButton(text="🔞 CLICK HERE FOR OUR ADULT CHANNEL", url='https://t.me/Adultship_films')])

    if offset:
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [InlineKeyboardButton(text=f"📑 ᴩᴀɢᴇꜱ 1/{math.ceil(int(total_results) / 6)}", callback_data="pages"),
            InlineKeyboardButton(text="𝕹𝖊𝖝𝖙 »»", callback_data=f"pmnext_{req}_{key}_{offset}")]
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

    if pmspoll:
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

async def pm_spoll_choker(client, msg):
    mv_id = msg.id  # Get the message ID
    mv_rqst = msg.text  # Get the message text

    # Get chat settings
    settings = await get_settings(msg.chat.id)

    # Remove common words from the query
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE
    )
    query = query.strip() + " movie"

    # Search for results using the processed query
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    gs_parsed = []

    # If no results found, reply with a message and delete after 10 seconds
    if not g_s:
        k = await msg.reply(
            script.I_CUDNT.format(mv_rqst),
            reply_markup=InlineKeyboardMarkup(btn)
        )
        await asyncio.sleep(10)
        await k.delete()
        return

    # Filter results for IMDb or Wikipedia links
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)
    gs = list(filter(regex.match, g_s))

    # Remove unnecessary parts from the filtered results
    gs_parsed = [
        re.sub(
            r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)', 
            '', i, flags=re.IGNORECASE
        ) 
        for i in gs
    ]

    # If still no parsed results, use a different regex to match certain patterns
    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*", re.IGNORECASE)
        for mv in g_s:
            match = reg.match(mv)
            if match:
                gs_parsed.append(match.group(1))

    # Get the user ID
    user = msg.from_user.id if msg.from_user else 0

    # Remove duplicate results
    gs_parsed = list(dict.fromkeys(gs_parsed))

    # Limit the number of results to 3
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]

    # Search IMDb for each keyword and collect movie titles
    movielist = []
    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)
            if imdb_s:
                movielist += [movie.get('title') for movie in imdb_s]

    # Further clean up the movie titles
    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))

    # If no movie titles found, reply with a message and delete after 30 seconds
    if not movielist:
        k = await msg.reply(
            script.I_CUDNT.format(mv_rqst),
            reply_markup=InlineKeyboardMarkup(btn)
        )
        await asyncio.sleep(30)
        await k.delete()
        return

    # Store the movie list in a temporary dictionary
    temp.PM_SPELL[str(msg.id)] = movielist

    # Create inline keyboard buttons for each movie title
    btn = [
        [InlineKeyboardButton(text=movie.strip(), callback_data=f"pmspolling#{user}#{k}")]
        for k, movie in enumerate(movielist)
    ]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f'pmspolling#{user}#close_spellcheck')])

    # Reply with the spell check results and buttons
    spell_check_del = await msg.reply(
        script.CUDNT_FND.format(mv_rqst),
        reply_markup=InlineKeyboardMarkup(btn),
        quote=True
    )

    # Auto delete the spell check message if auto_delete is enabled
    try:
        if settings['auto_delete']:
            await asyncio.sleep(10)
            await spell_check_del.delete()
    except KeyError:
        grpid = await active_connection(str(msg.from_user.id))
        await save_group_settings(grpid, 'auto_delete', True)
        settings = await get_settings(msg.chat.id)
        if settings['auto_delete']:
            await asyncio.sleep(10)
            await spell_check_del.delete()

