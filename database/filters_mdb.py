import pymongo
from pyrogram import enums
from info import DATABASE_URI, DATABASE_NAME, SECONDDB_URI
from sample_info import tempDict
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Initialize MongoDB clients and databases
myclient = pymongo.MongoClient(DATABASE_URI)
mydb = myclient[DATABASE_NAME]

myclient2 = pymongo.MongoClient(SECONDDB_URI)
mydb2 = myclient2[DATABASE_NAME]

async def add_filter(grp_id, text, reply_text, btn, file, alert):
    """
    Add or update a filter in the appropriate MongoDB collection based on tempDict['indexDB'].
    """
    if tempDict['indexDB'] == DATABASE_URI:
        mycol = mydb[str(grp_id)]
    else:
        mycol = mydb2[str(grp_id)]

    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }

    try:
        mycol.update_one({'text': str(text)},  {"$set": data}, upsert=True)
    except Exception:
        logger.exception('Error occurred while adding/updating filter!', exc_info=True)


async def find_filter(group_id, name):
    """
    Find a filter by name in the appropriate MongoDB collection.
    """
    mycol = mydb[str(group_id)]
    mycol2 = mydb2[str(group_id)]

    query = mycol.find({"text": name})
    query2 = mycol2.find({"text": name})

    try:
        for file in query:
            reply_text = file['reply']
            btn = file['btn']
            fileid = file['file']
            alert = file.get('alert')  # Use .get() to safely retrieve 'alert'
        return reply_text, btn, alert, fileid
    except Exception:
        try:
            for file in query2:
                reply_text = file['reply']
                btn = file['btn']
                fileid = file['file']
                alert = file.get('alert')
            return reply_text, btn, alert, fileid
        except Exception:
            return None, None, None, None


async def get_filters(group_id):
    """
    Retrieve all filters from both MongoDB collections for a given group_id.
    """
    mycol = mydb[str(group_id)]
    mycol2 = mydb2[str(group_id)]

    texts = []
    try:
        for file in mycol.find():
            text = file['text']
            texts.append(text)
    except Exception:
        pass

    try:
        for file in mycol2.find():
            text = file['text']
            texts.append(text)
    except Exception:
        pass

    return texts


async def delete_filter(message, text, group_id):
    """
    Delete a filter by text from the appropriate MongoDB collection.
    """
    mycol = mydb[str(group_id)]
    mycol2 = mydb2[str(group_id)]

    myquery = {'text': text}
    query = mycol.count_documents(myquery)
    query2 = mycol2.count_documents(myquery)

    if query == 1:
        mycol.delete_one(myquery)
        await message.reply_text(
            f"'{text}' deleted. I'll not respond to that filter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    elif query2 == 1:
        mycol2.delete_one(myquery)
        await message.reply_text(
            f"'{text}' deleted. I'll not respond to that filter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("Couldn't find that filter!", quote=True)


async def del_all(message, group_id, title):
    """
    Delete all filters from both MongoDB collections for a given group_id.
    """
    if str(group_id) not in mydb.list_collection_names() and str(group_id) not in mydb2.list_collection_names():
        await message.edit_text(f"Nothing to remove in {title}!")
        return

    mycol = mydb[str(group_id)]
    mycol2 = mydb2[str(group_id)]
    try:
        mycol.drop()
        mycol2.drop()
        await message.edit_text(f"All filters from {title} have been removed")
    except Exception:
        await message.edit_text("Couldn't remove all filters from group!")


async def count_filters(group_id):
    """
    Count the total number of filters in both MongoDB collections for a given group_id.
    """
    mycol = mydb[str(group_id)]
    mycol2 = mydb2[str(group_id)]

    count = mycol.count_documents({}) + mycol2.count_documents({})
    return count if count != 0 else False


async def filter_stats():
    """
    Retrieve statistics about filters from both MongoDB collections.
    """
    collections = mydb.list_collection_names()
    collections2 = mydb2.list_collection_names()

    # Remove special collections if present
    if "CONNECTION" in collections:
        collections.remove("CONNECTION")
    elif "CONNECTION" in collections2:
        collections2.remove("CONNECTION")

    total_count = 0

    # Calculate total count of filters across all collections
    for collection in collections:
        total_count += mydb[collection].count_documents({})

    for collection in collections2:
        total_count += mydb2[collection].count_documents({})

    total_collections = len(collections) + len(collections2)

    return total_collections, total_count
