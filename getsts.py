#!/usr/bin/env python3
"""Reference existing Role allowing S3 MultiPart Upload, return temp creds."""

import datetime
import json
import os

import boto3

# From Serverless Resource fails WHY?? WHAT FAILURE??
ROLE_ARN = "arn:aws:iam::%s:role/lambda-multipart-upload-sts"
UPLOAD_ROLE_ARN = os.environ['UPLOAD_ROLE_ARN']
UPLOAD_BUCKET = os.environ['UPLOAD_BUCKET']


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()


class Context:
    def __init__(self, aws_account):
        self.invoked_function_arn = f"arn:aws:svc:reg:{aws_account}:res"


def create_sts():
    """Create STS with dynamic policy limiting to bucket and upload path.

    We have to restrict to our request-specific path to prevent caller from
    getting a generic write-anywyer policy.

    Since our GET is currently not expecting a path param,
    we'll simulate by requiring them to use /uploads/*

    Later, we'll get the client's filename and MIME from the request, then
    generate a policy that may restrict like:
    /uploads/$username/$jobid/filename.sfx
    """
    policy = {"Version": "2012-10-17",
              "Statement": [
                  {"Sid": "Restrict to specific dir/file",
                   "Effect": "Allow",
                   "Action": "s3:*",
                   "Resource": "*",
                   },
              ]}
    sts_client = boto3.client('sts')
    res = sts_client.assume_role(
        # Should RoleArn already exist?
        # Can we use S3-all-access as the base, then limit with our Policy?
        RoleArn="arn:aws:iam::MYACCOUNT/role/cshenton-sts-dynamic",
        RoleSessionName="cshenton AVAIL Upload dynamic session",
        # The resulting session's permissions are the intersection of the
        # role's identity-based policy and the session policies.
        Policy=json.dumps(policy),
        DurationSeconds=3600,
    )
    print(f"# assume_role res={res}")
    return res


def get(event, context):

    """Lambda entrypoint for GET /."""
    policy = {"Version": "2012-10-17",
              "Statement": [
                  {"Sid": "Restrict to specific dir/file",
                   "Effect": "Allow",
                   "Action": "s3:*",
                   "Resource": "*",
                   },
              ]}
    res = boto3.client("sts").assume_role(
        # TODO can the RoleArn be S3:AllowAllAccess?
        RoleArn=UPLOAD_ROLE_ARN,  # role created in serverless
        RoleSessionName="cshenton-multipart-upload-sts-session",
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
