'''
Created on May 21, 2025

@author: lmgar
'''


class Standards:

    TMP_DIR="~/tmp/"
    DATA_DIR="~/data/"
    LOGS_DIR="~/logs/"
    EXPORT_DIR="~/export/"
    BIN_DIR="./bin/"
    DEVICES_DIR="./devices/"

    COORDINATOR_PORT=9012
    BUFFER_PORT=9013
    BROADCAST_FREQUENCY=1000*5

    CAPTURE_FREQUENCY=1000
    BUFFER_LENGTH=1000*60*15
    DEFAULT_AFTER=1000*10
    DEFAULT_BEFORE=1000*50

    GC_FREQUENCY=1000*60
    FILE_BUFFER_SIZE=1024*64
    SOCKET_BUFFER_SIZE=1024*8
    USE_BROADCAST=True
    USE_LOCAL_IP=True
    CONFIG_EXTENSION=".properties"
    RECORDS_FILENAME="ClipData.json"
