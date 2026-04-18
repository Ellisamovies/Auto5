async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""

    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)

    query = query.strip()

    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return [], "", 0

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    # 🔥 FIXED SORTING (NEW FILES FIRST)
    if MULTIPLE_DATABASE:
        cursor1 = col.find(filter).sort("_id", -1)
        cursor2 = sec_col.find(filter).sort("_id", -1)

        files1 = list(cursor1)
        files2 = list(cursor2)

        files_ = files1 + files2
    else:
        cursor = col.find(filter).sort("_id", -1)
        files_ = list(cursor)

    # 🔥 FIXED PAGINATION
    total_results = len(files_)
    files = files_[offset: offset + max_results]

    next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ""

    return files, next_offset, total_results
