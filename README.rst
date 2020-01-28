=======================================
 Multipart Upload with STS Credentials
=======================================

We have a S3-resident Web UI that talks to a backend API. Users who
are authorize by the app need to be able to upload to S3. For files
under 5GB we can use presigned-URLs which include temporary
credentials.

But for large files like video, we must use S3 multipart upload. The
client will need some credentials to be permitted to do the upload.

We hope to have the authenticated web client request temporary STS
credentials from the API, and use those when making the multipart
upload.

We create an IAM Role which we will want the client to "assume", and
attach a policy statement which gives it the permissions to do the
multipart upload:

* s3:GetObject
* s3:ListMultpartUploadParts
* s3:PutObject
* s3:AbortMultipartUpload

(insert policy here when we figure it out)

I had to Edit Trust Relationship on the Role I created to allow the
Lambda execution role (multipart-upload-sts-dev-us-east-1-lambdaRole)
Trust Relationships to assume the new Role I create which allows S3
operations.  The auto-generated part is the first statement, I added
the second which allowed the lambda, and the third which allowed me to
run it from CLI::

  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      },
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::AWS_ACCOUNT:role/multipart-upload-sts-dev-us-east-1-lambdaRole"
        },
        "Action": "sts:AssumeRole"
      },
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::AWS_ACCOUNT:user/chris"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }


The Trust Relatinships are distinct from the Permissions Policies, which are
needed for the assumed role to be able to do stuff to S3 that I want,
multipart upload.


I'm not sure how we're going to define these with Infrastructure As
Code, since the Lambda Execution Role's Trust has to specify the
Lambda ARN, and it seems we have to spec the execution role in the
Lambda definition -- circular dependency. More later.

TODO

Our lambda now can assume the role and emit creds, but we'll need some
code to take those creds and try to do a simple upload then a
multipart upload.
