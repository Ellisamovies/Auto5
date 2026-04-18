import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN
from utils import get_settings, save_group_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]


# ---------------- SAVE FILE ---------------- #
async def save_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)

    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    for char in ['[', ']', '(', ')']:
        file_name = file_name.replace(char, '')

    file_name = ' '.join(filter(lambda x: not x.startswith('@'), file_name.split()))

    file = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }

    if col.find_one({'file_id': file_id}) or col.find_one({'file_name': file_name}):
        return False, 0

    if MULTIPLE_DATABASE:
        if sec_col.find_one({'file_id': file_id}) or sec_col.find_one({'file_name': file_name}):
            return False, 0

        result = db.command('dbstats')
        if result['dataSize'] > 503316480:
            try:
                sec_col.insert_one(file)
                return True, 1
            except DuplicateKeyError:
                return False, 0
        else:
            try:
                col.insert_one(file)
                return True, 1
            except DuplicateKeyError:
                return False, 0
    else:
        try:
            col.insert_one(file)
            return True, 1
        except DuplicateKeyError:
            return False, 0


# ---------------- SEARCH (FIXED SORTING) ---------------- #
async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):

    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings['max_btn'] else int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            max_results = 10 if settings['max_btn'] else int(MAX_B_TN)

    query = query.strip()

    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')

    try:
        regex = re.compile(raw_pattern, re.IGNORECASE)
    except:
        return [], "", 0

    if USE_CAPTION_FILTER:
        db_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        db_filter = {'file_name': regex}

    # 🔥 NEW FILES FIRST
    if MULTIPLE_DATABASE:
        files = list(col.find(db_filter).sort("_id", -1)) + list(sec_col.find(db_filter).sort("_id", -1))
    else:
        files = list(col.find(db_filter).sort("_id", -1))

    total_results = len(files)
    files = files[offset: offset + max_results]

    next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ""

    return files, next_offset, total_results


# ---------------- BAD FILES ---------------- #
async def get_bad_files(query, file_type=None, filter=False):

    query = query.strip()

    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')

    try:
        regex = re.compile(raw_pattern, re.IGNORECASE)
    except:
        return [], 0

    if USE_CAPTION_FILTER:
        db_filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        db_filter = {'file_name': regex}

    if MULTIPLE_DATABASE:
        files = list(col.find(db_filter)) + list(sec_col.find(db_filter))
    else:
        files = list(col.find(db_filter))

    return files, len(files)


# ---------------- FILE DETAILS ---------------- #
async def get_file_details(query):
    filedetails = col.find_one({'file_id': query})
    if not filedetails:
        filedetails = sec_col.find_one({'file_id': query})
    return filedetails


# ---------------- FILE ID UTILS ---------------- #
def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)

    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )

    file_ref = encode_file_ref(decoded.file_reference)

    return file_id, file_ref
