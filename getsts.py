#!/usr/bin/env python3
"""Reference existing Role allowing S3 MultiPart Upload, return temp creds."""

import datetime
import json
import os

import boto3


class Encoder(json.JSONEncoder):
    """For JSON, render datetime objects as their ISO strings."""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()


class Context:
    def __init__(self, aws_account):
        self.invoked_function_arn = f"arn:aws:svc:reg:{aws_account}:res"


def get(event, context):
    """Lambda entrypoint for GET /."""
    try:
        ROLE_ARN = os.environ['ROLE_ARN']
    except KeyError:
        return {
            "statusCode": 500,
            "body": json.dumps({"msg": "No ROLE_ARN found"}, cls=Encoder, indent=2),
        }

    res = boto3.client("sts").assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="cshenton-multipart-upload-sts-session",
        # RegionName
        # DurationSeconds, default is 60 minutes, limits 15m-12h
    )
    creds = res['Credentials']
    user = res['AssumedRoleUser']
    return {
        "statusCode": 200,
        "body": json.dumps({"creds": creds, "user": user}, cls=Encoder, indent=2),
    }


if __name__ == "__main__":
    """Test by executing locally, fake Lambda context and environment vars."""
    aws_account = boto3.client('sts').get_caller_identity().get('Account')
    context = Context(aws_account)
    ROLE_ARN = "arn:aws:iam::%s:role/lambda-multipart-upload-sts" % aws_account
    os.environ['ROLE_ARN'] = ROLE_ARN

    res = get({}, context)
    if res['statusCode'] != 200:
        exit(1)

    creds_user = json.loads(res['body'])
    creds = creds_user['creds']
    user = creds_user['user']
    print(f"user={user}")
    print(f"Use like:")
    print(f"  AWS_ACCESS_KEY_ID={creds['AccessKeyId']} \\")
    print(f"  AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']} \\")
    print(f"  AWS_SESSION_TOKEN={creds['SessionToken']} \\")
    print(f"  ./upload.py")
