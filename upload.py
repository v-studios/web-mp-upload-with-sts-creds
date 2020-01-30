#!/usr/bin/env python3
"""Upload a file to S3 using STS creds from `getsts` lambda."""

from datetime import datetime
import os
import sys

import boto3


BUCKET="cshenton-multipart-upload-sts-test"
#BUCKET="cshenton-test-presigned"
FILE = sys.argv[0]              # this file, we know it exists :-)


s3r = boto3.resource('s3',
                     aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                     aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                     aws_session_token=os.environ['AWS_SESSION_TOKEN'],
)
# Returns none, throws Exception on failure (e.g., bad creds)
res = s3r.Bucket(BUCKET).upload_file(FILE, os.path.basename(FILE) + datetime.now().isoformat())

