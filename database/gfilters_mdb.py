import pymongo
from pyrogram import enums  # Assuming pyrogram is used elsewhere
from sample_info import tempDict
from info import DATABASE_URI, DATABASE_NAME, SECONDDB_URI
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Initialize MongoDB clients and databases
myclient = pymongo.MongoClient(DATABASE_URI)
mydb = myclient[DATABASE_NAME]

myclient2 = pymongo.MongoClient(SECONDDB_URI)
mydb2 = myclient2[DATABASE_NAME]

async def add_gfilter(gfilters, text, reply_text, btn, file, alert):
    """
    Add or update a gfilter in the appropriate MongoDB collection based on tempDict['indexDB'].
    """
    if tempDict['indexDB'] == DATABASE_URI:
        mycol = mydb[str(gfilters)]
    else:
        mycol = mydb2[str(gfilters)]

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
        logger.exception('Error occurred while adding/updating gfilter!', exc_info=True)
             
     
async def find_gfilter(gfilters, name):
    """
    Find a gfilter by name in the appropriate MongoDB collection.
    """
    mycol = mydb[str(gfilters)]
    mycol2 = mydb2[str(gfilters)]
    
    query = mycol.find({"text": name})
    if query.count() == 0:
        query = mycol2.find({"text": name})
    
    try:
        for file in query:
            reply_text = file['reply']
            btn = file['btn']
            fileid = file['file']
            alert = file.get('alert')  # Use .get() to safely retrieve 'alert'
        
        return reply_text, btn, alert, fileid
    except Exception:
        return None, None, None, None


async def get_gfilters(gfilters):
    """
    Retrieve all gfilters from both MongoDB collections.
    """
    mycol = mydb[str(gfilters)]
    mycol2 = mydb2[str(gfilters)]

    texts = []
    try:
        for file in mycol.find():
            texts.append(file['text'])
    except Exception:
        pass
    
    try:
        for file in mycol2.find():
            texts.append(file['text'])
    except Exception:
        pass
    
    return texts


async def delete_gfilter(message, text, gfilters):
    """
    Delete a gfilter by text from the appropriate MongoDB collection.
    """
    mycol = mydb[str(gfilters)]
    mycol2 = mydb2[str(gfilters)]
    
    myquery = {'text': text}
    query = mycol.count_documents(myquery)
    query2 = mycol2.count_documents(myquery)
    
    if query == 1:
        mycol.delete_one(myquery)
        await message.reply_text(
            f"'{text}' deleted. I'll not respond to that gfilter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    elif query2 == 1:
        mycol2.delete_one(myquery)
        await message.reply_text(
            f"'{text}' deleted. I'll not respond to that gfilter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("Couldn't find that gfilter!", quote=True)


async def del_allg(message, gfilters):
    """
    Delete all gfilters from both MongoDB collections for a given gfilters collection.
    """
    if str(gfilters) not in mydb.list_collection_names() and str(gfilters) not in mydb2.list_collection_names():
        await message.edit_text("Nothing to remove!")
        return

    mycol = mydb[str(gfilters)]
    mycol2 = mydb2[str(gfilters)]
    
    try:
        mycol.drop()
        mycol2.drop()
        await message.edit_text("All gfilters have been removed!")
    except Exception:
        await message.edit_text("Couldn't remove all gfilters!")


async def count_gfilters(gfilters):
    """
    Count the total number of gfilters in both MongoDB collections for a given gfilters collection.
    """
    mycol = mydb[str(gfilters)]
    mycol2 = mydb2[str(gfilters)]

    count = mycol.count_documents({}) + mycol2.count_documents({})
    return count if count != 0 else False


async def gfilter_stats():
    """
    Retrieve statistics about gfilters from both MongoDB collections.
    """
    collections = mydb.list_collection_names()
    collections2 = mydb2.list_collection_names()

    # Remove special collections if present
    if "CONNECTION" in collections:
        collections.remove("CONNECTION")
    elif "CONNECTION" in collections2:
        collections2.remove("CONNECTION")

    total_count = 0

    # Calculate total count of gfilters across all collections
    for collection in collections:
        total_count += mydb[collection].count_documents({})

    for collection in collections2:
        total_count += mydb2[collection].count_documents({})

    total_collections = len(collections) + len(collections2)

    return total_collections, total_count
