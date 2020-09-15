#!/usr/bin/env python3
"""Reference existing Role allowing S3 MultiPart Upload, return temp creds."""

import datetime
import json
import os

import boto3

ROLE_ARN = os.environ['ROLE_ARN']
BUCKET_NAME = os.environ['BUCKET_NAME']
BUCKET_ARN = os.environ['BUCKET_ARN']
# print(f'GLOBAL ROLE_ARN={ROLE_ARN} S3={BUCKET_NAME} S3ARN={BUCKET_ARN}')


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()


class Context:
    def __init__(self, aws_account):
        self.invoked_function_arn = f"arn:aws:svc:reg:{aws_account}:res"


def get(event, context):
    """Lambda entrypoint for GET /."""

    policy = {"Version": "2012-10-17",
              "Statement": [
                  {"Sid": "RestrictToSpecificBucketPrefix",
                   "Effect": "Allow",
                   "Action": [
                       "s3:PutObject",  # initiate, upload part, complete
                       "s3:AbortMultipartUpload",  # only to stop
                   ],
                   "Resource": f"{BUCKET_ARN}/uploads/*",
                   },
              ]}
    res = boto3.client("sts").assume_role(
        # TODO can the RoleArn be S3:AllowAllAccess?
        RoleArn=ROLE_ARN,  # role created in serverless
        RoleSessionName="cshenton-multipart-upload-sts-session",
        Policy=json.dumps(policy),
        # WTF? DurationSeconds exceeds the MaxSessionDuration set for this role
        # DurationSeconds=4200,  # default is 60 minutes, limits 15m-12h
    )
    creds = res['Credentials']
    user = res['AssumedRoleUser']
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"creds": creds,
             "user": user,
             "envcmd": (f"AWS_ACCESS_KEY_ID={creds['AccessKeyId']}"
                        f" AWS_SECRET_ACCESS_KEY={creds['SecretAccessKey']}"
                        f" AWS_SESSION_TOKEN={creds['SessionToken']}"
                        f" ./upload.py")},
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
