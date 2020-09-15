#!/usr/bin/env python3
"""Reference existing Role allowing S3 MultiPart Upload, return temp creds."""

import datetime
import json
from pprint import pprint

import boto3

# From Serverless Resource fails
ROLE_ARN = "arn:aws:iam::%s:role/lambda-multipart-upload-sts"


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()


class Context:
    def __init__(self, aws_account):
        self.invoked_function_arn = f"arn:aws:svc:reg:{aws_account}:res"


# TODO: Add policy restricting to just the S3 target path
# e.g., /uploads/username/jobid/...
# we could test by getting the dest-filename from the request
# then resturct to /uploads/dest-filename.suf
def get(event, context):
    """Lambda entrypoint for GET /."""
    aws_account = context.invoked_function_arn.split(":")[4]
    res = boto3.client("sts").assume_role(
        RoleArn=ROLE_ARN % aws_account,
        RoleSessionName="cshenton-multipart-upload-sts-session",
        # RegionName
        # DurationSeconds, default is 60 minutes, limits 15m-12h
    )
    creds = res['Credentials']
    user = res['AssumedRoleUser']
    return {
        "statusCode": 200,
        "body": json.dumps({"creds": creds,
                            "user": user,
                            "envcmd": f"AWS_ACCESS_KEY_ID={creds['AccessKeyId']} AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']} AWS_SESSION_TOKEN={creds['SessionToken']} ./upload.py"},
                           cls=Encoder,
                           indent=2),
    }


if __name__ == "__main__":
    aws_account = boto3.client('sts').get_caller_identity().get('Account')
    context = Context(aws_account)
    creds_user = json.loads(get({}, context)['body'])
    creds = creds_user['creds']
    user = creds_user['user']
    print(f"user={user}")
    print(f"Use like:")
    print(f"  AWS_ACCESS_KEY_ID={creds['AccessKeyId']}")
    print(f"  AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']}")
    print(f"  AWS_SESSION_TOKEN={creds['SessionToken']}")
    print(f"  ./upload.py")
