import logging
from struct import pack, unpack
from typing import Tuple
import base64
import re
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from marshmallow.exceptions import ValidationError
from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER, MAX_B_TN, SECONDDB_URI
from utils import get_settings, save_group_settings
from sample_info import tempDict 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#some basic variables needed
saveMedia = None

# Primary DB
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = {'file_name': {'unique': True}}
        collection_name = COLLECTION_NAME

# Secondary DB
client2 = AsyncIOMotorClient(SECONDDB_URI)
db2 = client2[DATABASE_NAME]
instance2 = Instance.from_db(db2)

@instance2.register
class Media2(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = {'file_name': {'unique': True}}
        collection_name = COLLECTION_NAME

async def choose_mediaDB():
    """This Function chooses which database to use based on the value of indexDB key in the dict tempDict."""
    global saveMedia
    if tempDict['indexDB'] == DATABASE_URI:
        logger.info("Using first db (Media)")
        saveMedia = Media
    else:
        logger.info("Using second db (Media2)")
        saveMedia = Media2

async def save_file(media):
    """Save file in the chosen database (Media or Media2)"""
    # Decode and unpack the new file ID into file_id and file_ref
    file_id, file_ref = unpack_new_file_id(media.file_id)
    
    # Normalize the file name
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))

    # Choose the appropriate database
    await choose_mediaDB()
    
    try:
        # Check if the file already exists in the primary database (Media)
        if await Media.count_documents({'file_id': file_id}, limit=1):
            logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in primary DB!')
            return False, 0
        
        # Check if the file already exists in the secondary database (Media2)
        if await Media2.count_documents({'file_id': file_id}, limit=1):
            logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in secondary DB!')
            return False, 0

        # Create a new file document
        file = saveMedia(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
        
        # Commit file to the chosen database
        await file.commit()
    except DuplicateKeyError:
        logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in database')
        return False, 0
    except ValidationError:
        logger.exception('Error occurred while saving file in database')
        return False, 2
    else:
        logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
        return True, 1

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query, return (results, next_offset, total_results)."""
    
    # Adjust max_results based on group settings if chat_id is provided
    if chat_id is not None:
        try:
            settings = await get_settings(int(chat_id))
            max_btn = settings.get('max_btn', False)
            max_results = 10 if max_btn else int(max_btn)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            max_btn = settings.get('max_btn', False)
            max_results = 10 if max_btn else int(max_btn)

    query = query.strip()
    
    # Construct regular expression pattern based on query
    raw_pattern = (
        r'.' if not query else  # Match anything if query is empty
        rf'(\b|[.\+\-_]){re.escape(query)}(\b|[.\+\-_])' if ' ' not in query else  # Match exact words
        query.replace(' ', r'.*[\s\.\+\-_()]')  # Match words with spaces replaced by any separator
    )

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        logger.exception('Invalid regular expression pattern')
        return [], '', 0

    # Build the filter query
    filter_query = {'$or': [{'file_name': regex}]}
    if filter and USE_CAPTION_FILTER:
        filter_query['$or'].append({'caption': regex})
    if file_type:
        filter_query['file_type'] = file_type

    # Calculate total results by summing counts from both databases
    total_results = await Media.count_documents(filter_query) + await Media2.count_documents(filter_query)

    # Ensure max_results is even
    if max_results % 2 != 0:
        logger.info(f"Since max_results is an odd number ({max_results}), bot will use {max_results + 1} as max_results to make it even.")
        max_results += 1

    # Fetch results from both collections
    cursor1 = Media.find(filter_query).sort('$natural', -1).skip(offset).limit(max_results)
    cursor2 = Media2.find(filter_query).sort('$natural', -1).skip(offset).limit(max_results)
    
    # Combine the results
    files1 = await cursor1.to_list(length=max_results)
    files2 = await cursor2.to_list(length=max_results)
    files = files1[:max_results // 2] + files2[:max_results // 2]

    # Calculate next offset
    next_offset = offset + len(files)
    if next_offset >= total_results:
        next_offset = ''  # Reset next_offset if it exceeds total results

    return files, next_offset, total_results

async def get_bad_files(query: str, file_type: str = None, filter: bool = False):
    """For given query, return (results, total_results)."""
    query = query.strip()

    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_()]')

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        logger.exception('Invalid regular expression pattern')
        return []

    filter_query = {'$or': [{'file_name': regex}]}
    if USE_CAPTION_FILTER:
        filter_query['$or'].append({'caption': regex})

    if file_type:
        filter_query['file_type'] = file_type

    # Querying both collections and merging results
    cursor1 = Media.find(filter_query).sort('$natural', -1)
    cursor2 = Media2.find(filter_query).sort('$natural', -1)
    
    files1 = await cursor1.to_list(length=await Media.count_documents(filter_query))
    files2 = await cursor2.to_list(length=await Media2.count_documents(filter_query))
    files = files1 + files2

    total_results = len(files)

    return files, total_results

async def get_file_details(query):
    """Fetch file details from MongoDB based on file_id."""
    filter_query = {'file_id': query}  # Define filter based on file_id query

    # Attempt to find file details in the primary MongoDB collection (Media)
    filedetails = await Media.find_one(filter_query)

    # If file details are not found in the primary collection, try the secondary collection (Media2)
    if not filedetails:
        filedetails = await Media2.find_one(filter_query)

    return filedetails  # Return the fetched file details (None if not found)

def encode_file_id(s: bytes) -> str:
    """Encode bytes to a URL-safe base64 string."""
    result_bytes = b""
    consecutive_zeros = 0

    for byte in s + bytes([22]) + bytes([4]):
        if byte == 0:
            consecutive_zeros += 1
        else:
            if consecutive_zeros:
                # Append a zero byte followed by the count of consecutive zeros
                result_bytes += b"\x00" + bytes([consecutive_zeros])
                consecutive_zeros = 0
            
            result_bytes += bytes([byte])  # Append the current byte to the result

    # Encode the result bytes using URL-safe base64 encoding, decode to UTF-8, and strip trailing '=' characters
    encoded_str = base64.urlsafe_b64encode(result_bytes).decode().rstrip("=")
    
    return encoded_str
    
def encode_file_ref(file_ref: bytes) -> str:
    """Encode file reference bytes to a URL-safe base64 string."""
    # Encode the file_ref using URL-safe base64 encoding
    encoded = base64.urlsafe_b64encode(file_ref)
    
    # Decode the bytes to UTF-8 string and remove trailing '=' characters
    encoded_str = encoded.decode().rstrip("=")
    
    return encoded_str

def unpack_new_file_id(new_file_id: bytes) -> Tuple[bytes, bytes]:
    """Decode and unpack a new_file_id into file_id and file_ref."""
    try:
        # Decoding the new_file_id using a custom function (decode_file_id)
        decoded = decode_file_id(new_file_id)
        
        # Encoding the decoded parts into a new file_id using pack function
        file_id = encode_file_id(pack("<iiqq",
                                      int(decoded.file_type),
                                      decoded.dc_id,
                                      decoded.media_id,
                                      decoded.access_hash))
        
        # Encoding the file reference part using a custom function (encode_file_ref)
        file_ref = encode_file_ref(decoded.file_reference)
        
        # Returning the encoded file_id and file_ref as a tuple
        return file_id, file_ref
    
    except Exception as e:
        # Handling exceptions that might occur during decoding or encoding
        print(f"Error decoding new_file_id: {e}")
        return b'', b''  # Returning empty bytes objects or handle the error as needed

