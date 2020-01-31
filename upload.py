#!/usr/bin/env python3
"""Upload a file to S3 using STS creds from `getsts` lambda."""

from datetime import datetime
import logging
import os
import sys

import boto3
from boto3.s3.transfer import TransferConfig

GB5 = 5 * 1024 ** 3
BUCKET = "cshenton-multipart-upload-sts-test"
S3R = boto3.resource(
    's3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    aws_session_token=os.environ['AWS_SESSION_TOKEN'],
)


def show_bytes(count):
    # This just spews too much for long files
    # print(count)
    pass


def upload(path, multipart=False):
    """Use TransferManager for MP upload if size > threhold or > 5GB.

    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html
    """
    threshold = GB5
    if multipart:
        threshold = 1           # so low it forces multipart
        print('Using multipart...')
    config = TransferConfig(multipart_threshold=threshold)
    S3R.Bucket(BUCKET).upload_file(path,
                                   datetime.now().isoformat() + "_" + os.path.basename(path),
                                   Callback=show_bytes,
                                   Config=config)
    print("Uploaded OK")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)  # use DEBUG to see MultipartUpload messages
    path = sys.argv[0]
    if len(sys.argv) > 1:
        path = sys.argv[1]
    upload(path, multipart=True)
