import datetime, time, os, asyncio, logging 
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong, PeerIdInvalid
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from info import ADMINS

# Initialize client and other configurations
# Assuming `Client` is properly initialized with appropriate settings

# Function to check for cancellation
async def check_cancel(message, sts):
    cancel_button = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_broadcast")]])
    await sts.edit("Broadcasting Your Messages...", reply_markup=cancel_button)

    # Wait for cancel callback for up to 5 seconds
    try:
        for _ in range(50):  # 50 iterations with 0.1 sec sleep each = 5 sec
            await asyncio.sleep(0.1)
            if await db.check_cancel_broadcast():
                await sts.edit("Broadcast Cancelled!")
                await sts.delete()
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking cancel: {e}")
        return False

# Broadcast function with cancellation support
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)        
async def broadcast(bot, message):
    sts = await message.reply_text('Broadcasting Your Messages...')
    b_msg = message.reply_to_message
    
    try:
        if await check_cancel(message, sts):
            return
        
        start_time = time.time()
        total_users = await db.total_users_count()
        done = 0
        blocked = 0
        deleted = 0
        failed = 0
        success = 0
        
        async for user in db.get_all_users():
            if await db.check_cancel_broadcast():
                await sts.edit("Broadcast Cancelled!")
                return

            try:
                pti, sh = await broadcast_messages(int(user['id']), b_msg)
                if pti:
                    success += 1
                elif pti is False:
                    if sh == "Blocked":
                        blocked += 1
                    elif sh == "Deleted":
                        deleted += 1
                    elif sh == "Error":
                        failed += 1
                done += 1

                if not done % 20:
                    await sts.edit(f"Broadcast In Progress:\n\nTotal Users: {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")
            
            except Exception as e:
                logging.error(f"Failed to broadcast to user {user['id']}: {e}")
                failed += 1

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        await sts.edit(f"Broadcast Completed:\nTime Taken: {time_taken} Sec\n\nTotal Users: {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")

    except Exception as e:
        await sts.edit(f"Error: {e}")
        logging.error(f"Error in broadcast function: {e}")

    finally:
        await sts.delete()

# Group broadcast function with cancellation support
@Client.on_message(filters.command("group_broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_group(bot, message):
    groups = await db.get_all_chats()
    b_msg = message.reply_to_message
    sts = await message.reply_text(text='Broadcasting your messages To Groups...')
    start_time = time.time()
    total_groups = await db.total_chat_count()
    done = 0
    failed = ""
    success = 0
    deleted = 0
    
    try:
        if await check_cancel(message, sts):
            return

        async for group in groups:
            if await db.check_cancel_broadcast():
                await sts.edit("Broadcast Cancelled!")
                return

            pti, sh, ex = await broadcast_messages_group(int(group['id']), b_msg)
            if pti == True:
                if sh == "Succes":
                    success += 1
            elif pti == False:
                if sh == "deleted":
                    deleted += 1 
                    failed += ex 
                    try:
                        await bot.leave_chat(int(group['id']))
                    except Exception as e:
                        logging.error(f"{e} > {group['id']}")  
            done += 1
            if not done % 20:
                await sts.edit(f"Broadcast in progress:\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nSuccess: {success}\nDeleted: {deleted}")    
        
        time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
        await sts.delete()
        await message.reply_text(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nSuccess: {success}\nDeleted: {deleted}\n\nFiled Reson:- {failed}")

    except MessageTooLong:
        with open('reason.txt', 'w+') as outfile:
            outfile.write(failed)
        await message.reply_document('reason.txt', caption=f"Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nSuccess: {success}\nDeleted: {deleted}")
        os.remove("reason.txt")

    except Exception as e:
        logging.error(f"Error in group broadcast function: {e}")
        await sts.edit(f"Error: {e}")

async def broadcast_messages_group(chat_id, message):
    try:
        await message.copy(chat_id=chat_id)
        return True, "Succes", 'mm'
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages_group(chat_id, message)
    except Exception as e:
        await db.delete_chat(int(chat_id))       
        logging.info(f"{chat_id} - PeerIdInvalid")
        return False, "deleted", f'{e}\n\n'

async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Blocked the bot. Removed from Database.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception as e:
        logging.error(f"Error broadcasting message to {user_id}: {e}")
        return False, "Error"

