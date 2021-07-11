import hashlib, uuid

def MD5(
        plain: str
):
    return hashlib.md5(plain.encode(encoding='UTF-8')).hexdigest()


def getNewUUID():
    return str(uuid.uuid4())

