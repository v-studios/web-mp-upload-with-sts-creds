#!/usr/bin/env python3
"""Reference existing Role allowing S3 MultiPart Upload, return temp creds."""

import datetime
import json
import os
from pprint import pprint

import boto3

ROLE_ARN = "arn:aws:iam::%s:role/cshenton-multipart-upload-sts"


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()


class Context:
    def __init__(self, aws_account):
        self.invoked_function_arn = f"arn:aws:svc:reg:{aws_account}:res"


def get(event, context):
    """Lambda entrypoint for GET /."""
    aws_account = context.invoked_function_arn.split(":")[4]
    print(aws_account)
    creds = boto3.client("sts").assume_role(
        RoleArn=ROLE_ARN % aws_account,
        RoleSessionName="cshenton-multipart-upload-sts-session",
        # RegionName
        # DurationSeconds
    )
    return {
        "statusCode": 200,
        "body": json.dumps({"res": creds}, cls=Encoder, indent=2),
    }


if __name__ == "__main__":
    aws_account = boto3.client('sts').get_caller_identity().get('Account')
    context = Context(aws_account)
    res = get({}, context)
    pprint(json.loads(res["body"])["res"])
