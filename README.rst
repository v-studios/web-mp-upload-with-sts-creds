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
                "arn:aws:logs:us-east-1:AWS_ACCT:log-group:/aws/lambda/multipart-upload-sts-dev\*:\*"
            ],
            "Effect": "Allow"
        },
        {
            "Action": [
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:logs:us-east-1:AWS_ACCT:log-group:/aws/lambda/multipart-upload-sts-dev\*:\*:\*"
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
              "Resource": "arn:aws:s3:::cshenton-multipart-upload-sts-test/\*"
          },
          {
              "Sid": "AssumeRoleSTS",
              "Effect": "Allow",
              "Action": "sts:AssumeRole",
              "Resource": "\*"
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
              "Resource": "arn:aws:s3:::cshenton-multipart-upload-sts-test/\*"
          },
          {
              "Sid": "AssumeRoleSTS",
              "Effect": "Allow",
              "Action": "sts:AssumeRole",
              "Resource": "\*"
          }
      ]
  }


Lambda to get and return STS credentials: getsts.py
===================================================

The `getsts.py` code which the Lambda uses does an `assume_role` with
our ROLE_ARN of the role we created in serverless.yml.

You can run this from the CLI (after setting your AWS_PROFILE)::

  ./getsts.py

It will return the creds it got from the `assume_role`. It will return
results, with a cut-n-paste-able command like::

  user={'AssumedRoleId': 'ABCDEFGHIJK:cshenton-multipart-upload-sts-session',
        'Arn': 'arn:aws:sts::AWS_ACCOUNT:assumed-role/lambda-multipart-upload-sts/cshenton-multipart-upload-sts-session'}
  Use like:
      AWS_ACCESS_KEY_ID=ABCDEFGHIJK \
      AWS_SECRET_ACCESS_KEY=somekey \
      AWS_SESSION_TOKEN=somelongtoken \
      ./upload.py

To prevent anyone on the interwebs from accessing the GetSts and
getting creds which would allow them to assume a role and write to my
S3 (or other resources defined on the Role), we will require an API
key.  In the `serverless.yml` we make the GET private, define a couple
API keys, and say we'll pass these in the HEADER. When we deploy,
CloudFormation tells us our key values, then we can pass them in our
"curl" request:

  curl -H "x-api-key: FROM_SLS_DEPLOY" https://ENDPOINT.execute-api.us-east-1.amazonaws.com/dev/

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

Then we can uplaod a file to our specific bucket, and no other::

  res = s3r.Bucket(BUCKET).upload_file(FILE, os.path.basename(FILE) + datetime.now().isoformat())

The ``upload.py`` uses ``upload_file`` from ``boto3``, and we've
forced it to use multipart in the code by setting a minimal
threshhold::

  config = TransferConfig(multipart_threshold=threshold)
  S3R.Bucket(BUCKET).upload_file(path,
                                 datetime.now().isoformat() + "_" + os.path.basename(path),
                                 Config=config)

The DEBUG logs confirm we've uploaded with multpart::

  DEBUG:s3transfer.tasks:CompleteMultipartUploadTask(transfer_id=0,
    {'bucket': 'BUCKETNAME', 'key': '2020-07-17T14:16:02.872690_upload.py', 'extra_args': {}})
  done waiting for dependent futures

TODO
====

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

We'll use AngularEvaporate, which is a wrapper around AngularJS (not
NG2+); it's what we use now for images.nasa.gov so it should be a good test.

TODO: we are still going to need a cryptographic signer for each part,
running in the cloud as an API.

Why doesn't my CLI upload.py need me
to specify a signer? It's calculating signatures behind the scenes::

  DEBUG:botocore.auth:CanonicalRequest:
  POST
  /2020-07-17T14%3A55%3A31.005620_upload.py
  uploads=
  host:cshenton-multipart-upload-sts-test.s3.amazonaws.com
  x-amz-content-sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  x-amz-date:20200717T185531Z
  x-amz-security-token:...

  host;x-amz-content-sha256;x-amz-date;x-amz-security-token
  [e3... 64 hex chars]
  DEBUG:botocore.auth:StringToSign:
  AWS4-HMAC-SHA256
  20200717T185531Z
  20200717/us-east-1/s3/aws4_request
  [00a5... 64 hex chard]
  DEBUG:botocore.auth:Signature:
  5d2d5c34c20bd0e4ddbf0f83780f4917c2ce414bdd75aa22c3db18a964e48e27

AWS SDK for HTML+JS?
--------------------

AngularEvaporate hasn't been touched in 4 years or so.

`EvaporateJS <https://github.com/TTLabs/EvaporateJS>`_ is mostly
dormant for the past 3 years, but has some activity for README.md and
Examples recently.

Is there an AWS SDK for JavaScript we can use from our post AngularJS,
now NG2+ front-end?

Infrastructures as Code
-----------------------

I'm not sure how we're going to define these with Infrastructure As
Code, since the Lambda Execution Role's Trust has to specify the
Lambda ARN, and it seems we have to spec the execution role in the
Lambda definition -- circular dependency. More later.

I THINK THIS IS OK NOW.

Security Concerns
-----------------

A policy specifying write access to `bucketname/\*` is too broad, it
would allow anyone with the creds to write anywhere in our bucket,
perhaps overwriting other users' uploads. The `docs suggest it may be
possible to submit a inline "session policy"
<https://docs.aws.amazon.com/cli/latest/reference/sts/assume-role.html>`_. If
so, we could at runtime return a restricted S3 location like
`bucketname/upload/USERNAME/FILENAME` to limit where they can write,
similar to S3 presigned URLs do.
