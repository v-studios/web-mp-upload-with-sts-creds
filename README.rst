===========================================
 Web Multipart Upload with STS Credentials
===========================================

We have a S3-resident Web UI that talks to a backend API. Users who
are authorize by the app need to be able to upload to S3. For files
under 5GB we use API-generated presigned-URLs which include temporary
credentials, easy.

But for files larger than 5GB like video, we must use S3 multipart
upload. The web client will need some credentials to be permitted to do
the upload.

Our web client authenticates to our API and uses JWTs in maintain
session. It should request temporary STS credentials from the API, and
use those when doing the multipart upload.

The Serverless Framework created a Lambda Execution Role
`role/multipart-upload-sts-dev-us-east-1-lambdaRole` which allows
logging to CloudWatch, all standard stuff, and built-in to
Serverless::

  {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "logs:CreateLogStream",
                "logs:CreateLogGroup"
            ],
            "Resource": [
                "arn:aws:logs:us-east-1:AWS_ACCT:log-group:/aws/lambda/multipart-upload-sts-dev*:*"
            ],
            "Effect": "Allow"
        },
        {
            "Action": [
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:logs:us-east-1:AWS_ACCT:log-group:/aws/lambda/multipart-upload-sts-dev*:*:*"
            ],
            "Effect": "Allow"
        }
    ]
  }

We have to ensure the Lambda Execution Role also has a Trust
Relationship allowing Lambda to do the AssumeRole (TODO is this done
automatically by Serverless, and not something we need to worry about
at all?)::

  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }

Now we create an IAM Role that we will want to get STS creds for, with
the permissions needed for the S3 multipart upload; we should be able
to do this in `serverless.yml` with `Resources`. Our role is
`role/cshenton-multipart-upload-sts` with Permissions::

  {
      "Version": "2012-10-17",
      "Statement": [
          {
              "Sid": "MultipartUploadToSpecificS3Bucket",
              "Effect": "Allow",
              "Action": [
                  "s3:PutObject",
                  "s3:GetObject",
                  "s3:AbortMultipartUpload",
                  "s3:ListMultipartUploadParts"
              ],
              "Resource": "arn:aws:s3:::cshenton-multipart-upload-sts-test/*"
          },
          {
              "Sid": "AssumeRoleSTS",
              "Effect": "Allow",
              "Action": "sts:AssumeRole",
              "Resource": "*"
          }
      ]
  }

TODO is the second set with AssumeRole needed?

We also have to add to this role a Trust Relationship which allows our
Lambda to assume it. Here, the first line (TODO is this needed?) was
added by Serverless (?) and I've added one with our Lambda Role's ARN,
and also for my AWS user so I can invoke `getsts.py` from the CLI::

  {
      "Version": "2012-10-17",
      "Statement": [
          {
              "Sid": "MultipartUploadToSpecificS3Bucket",
              "Effect": "Allow",
              "Action": [
                  "s3:PutObject",
                  "s3:GetObject",
                  "s3:AbortMultipartUpload",
                  "s3:ListMultipartUploadParts"
              ],
              "Resource": "arn:aws:s3:::cshenton-multipart-upload-sts-test/*"
          },
          {
              "Sid": "AssumeRoleSTS",
              "Effect": "Allow",
              "Action": "sts:AssumeRole",
              "Resource": "*"
          }
      ]
  }  


Lambda to get and return STS credentials: getsts.py
===================================================

The `getsts.py` code which the Lambda uses does an `assume_role` with
our Role's ARN::

  ROLE_ARN = "arn:aws:iam::%s:role/cshenton-multipart-upload-sts"

You can run this from the CLI (after setting your AWS_PROFILE) and it
will return the creds it got from the `asseume_role`. It looks for a
role based on your AWS Account number and you'll have to change the
name to match the one you created.  It emits the creds it got::

  {'AssumedRoleUser':
    {'Arn': 'arn:aws:sts::AWS_ACCOUNT:assumed-role/cshenton-multipart-upload-sts/cshenton-multipart-upload-sts-session',
     'AssumedRoleId': 'AROAVFNXBLR7A5554DJFR:cshenton-multipart-upload-sts-session'},
   'Credentials': {'AccessKeyId': 'KEYVALUE',
                   'Expiration': '2020-01-28T22:42:22+00:00',
                   'SecretAccessKey': 'SECRETVALUE',
                   'SessionToken': 'ALONGSESSIONTOKEN'}}

To prevent anyone on the interwebs from accessing the GetSts and
getting creds which would allow them to assume a role and write to my
S3 (or other resources defined on the Role), we will require an API
key.  In the `serverless.yml` we make the GET private, define a couple
API keys, and say we'll pass these in the HEADER. When we deploy,
CloudFormation tells us our key values, then we can pass them in our
"curl" request:

  curl -H "x-api-key: API_KEY_FROM_SLS_DEPLOY" https://MY_ENDPOINT.execute-api.us-east-1.amazonaws.com/dev/

If we don't pass a valid key, we get an HTTP 403 with response::

  {"message": "Forbidden"}


Using the STS credentials to upload: upload.py
==============================================

We can quickly test with a CLI script that uses the STS creds from the
environment to create a Boto session with access to the S3 bucket::

  s3r = boto3.resource('s3',
                       aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                       aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                       aws_session_token=os.environ['AWS_SESSION_TOKEN'],
  )

Then we can upload a file to our specific bucket, and no other::

  res = s3r.Bucket(BUCKET).upload_file(FILE, os.path.basename(FILE) + datetime.now().isoformat())



TODO
====

STS for MP Upload with Restrictions
-----------------------------------

I think the STS solution will be easiest, since modern AWS SDK for JS
supports MP uploads directly. The "trick" will be restricting the
Role/Permissions attached to the Token so they can ONLY upload to the
target URL, not everywhere in the S3 bucket

We may have to give the Lambda privs to create new Roles on the fly,
with a Policy that has the path restrictions we need, then build that
into the STS token.

Presigned URLs for Multipart Upload
-----------------------------------

A recent trawling found a couple good resources for using Presigned
URLs for MP Upload. There's a `GitHub ticket #1603
<https://github.com/aws/aws-sdk-js/issues/1603#issuecomment-441926007>`_
for the ``aws-sdk-js`` that talks about diffenent way to do this.

In the commnents, Preston posted a `link to FE and BE
<https://github.com/prestonlimlianjie/aws-s3-multipart-presigned-upload>`_
to do MP uploads where each part gets its own Presigned URL, rather than STS.

CLI with Multipart Upload
-------------------------

Replace the simple S3 upload with a boto3 multipart upload with our STS creds.

WebUI with Multipart Upload
---------------------------

Make a WebUI using a JS client like EvaporateJS and our STS creds.

This is more complicated because you have to initiate the upload, then
uplod many parts and track the returned ETags, and finally finish the
upload by supplying a list of all the parts' ETags. Each of the
uploads must have a checksum computed on it, and this is a pain if you
don't have a library to do the work for you like `EvaporateJS
<https://github.com/TTLabs/EvaporateJS>`_.

We may also need to calculate AWS V4 crypto signatures, which we could
implement as a Lambda.

2020-09-15 We should be able to do this now directly with the AWS SDK for Javascript.


Infrastructures as Code
-----------------------

I'm not sure how we're going to define these with Infrastructure As
Code, since the Lambda Execution Role's Trust has to specify the
Lambda ARN, and it seems we have to spec the execution role in the
Lambda definition -- circular dependency. More later.

Security Concerns
-----------------

A policy specifying write access to `bucketname/*` is too broad, it
would allow anyone with the creds to write anywhere in our bucket,
perhaps overwriting other users' uploads. The `docs suggest it may be
possible to submit a inline "session policy"
<https://docs.aws.amazon.com/cli/latest/reference/sts/assume-role.html>`_. If
so, we could at runtime return a restricted S3 location like
`bucketname/upload/USERNAME/FILENAME` to limit where they can write,
similar to S3 presigned URLs do.

Too Many Roles, Who Created?
----------------------------

In Console our stack creates
* IamRoleCusomResourcesLambdaExecution: multiprt-upload-sts-dev-IamRoleCustomResourcesLam-F494D65621DH (AttachRolePolicy, apig:Get/Patch)
* LamRoleLambdaExecution: multipart-upload-sts-dev-us-east-1-lambdaRole (createLogGroup/Stream)
* MultipartUploadRole:	lambda-multipart-upload-sts (Policy=S3-multipart-uploads assumerole, Putobject ourS3.../*)
