"""
    This will be a service that the client program will instantiate to then call methods
    passing buckets
"""
import boto3 # TODO: Limit import to just boto3.client, probably
from s3Bucket import s3Bucket, BucketExists, Permission, s3BucketObject
from botocore.exceptions import ClientError
import botocore.session
from botocore import UNSIGNED
from botocore.client import Config
import datetime


class S3Service:
    def __init__(self):
        # Check for AWS credentials
        session = botocore.session.get_session()
        if session.get_credentials() is None or session.get_credentials().access_key is None:
            self.aws_creds_configured = False
            self.s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        else:
            self.aws_creds_configured = True
            self.s3_client = boto3.client('s3')

        del session  # No longer needed

    def check_bucket_exists(self, bucket):
        if not isinstance(bucket, s3Bucket):
            raise ValueError("Passed object was not type s3Bucket")

        bucket_exists = True

        try:
            self.s3_client.head_bucket(Bucket=bucket.name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                bucket_exists = False

        bucket.exists = BucketExists.YES if bucket_exists else BucketExists.NO

    def check_perm_read_acl(self, bucket):
        """
            Check for the READACP permission on the bucket by trying to get the bucket ACL.

            Exceptions:
                ValueError
                ClientError
        """
        if bucket.exists != BucketExists.YES:
            raise ValueError("Bucket might not exist")  # TODO: Create custom exception for easier handling

        read_acl_perm_allowed = True
        try:
            self.s3_client.get_bucket_acl(Bucket=bucket.name)
        except ClientError as e:
            if e.response['Error']['Code'] == "AccessDenied":
                read_acl_perm_allowed = False
            else:
                raise e

        # TODO: If we can read ACLs, we know the rest of the permissions
        if self.aws_creds_configured:
            bucket.AllUsersReadACP = Permission.ALLOWED if read_acl_perm_allowed is True else Permission.DENIED
        else:
            bucket.AnonUsersReadACP = Permission.ALLOWED if read_acl_perm_allowed is True else Permission.DENIED

    def check_perm_read(self, bucket):
        """
            Checks for the READ permission on the bucket by attempting to list the objects.

            Exceptions:
                ValueError
                ClientError
        """
        if bucket.exists != BucketExists.YES:
            raise ValueError("Bucket might not exist")  # TODO: Create custom exception for easier handling

        list_bucket_perm_allowed = True
        try:
            self.s3_client.list_objects_v2(Bucket=bucket.name, MaxKeys=0)  # TODO: Compare this to doing a HeadBucket
        except ClientError as e:
            if e.response['Error']['Code'] == "AccessDenied":
                list_bucket_perm_allowed = False
            else:
                raise e
        if self.aws_creds_configured:
            bucket.AllUsersRead = Permission.ALLOWED if list_bucket_perm_allowed else Permission.DENIED
        else:
            bucket.AnonUsersRead = Permission.ALLOWED if list_bucket_perm_allowed else Permission.DENIED

    def check_perm_write(self, bucket):
        if bucket.exists != BucketExists.YES:
            raise ValueError("Bucket might not exist")  # TODO: Create custom exception for easier handling

        perm_write = Permission.UNKNOWN
        timestamp_file = str(datetime.datetime.now().timestamp()) + '.txt'

        try:
            # Try to create a new empty file with a key of the timestamp
            self.s3_client.put_object(Bucket=bucket.name, Key=timestamp_file, Body=b'')
            perm_write = Permission.ALLOWED

            # Delete the temporary file
            self.s3_client.delete_object(Bucket=bucket.name, Key=timestamp_file)
        except ClientError as e:
            if e.response['Error']['Code'] == "AccessDenied":
                perm_write = Permission.DENIED
            else:
                raise e
        finally:
            pass

        if self.aws_creds_configured:
            bucket.AllUsersWrite = perm_write
        else:
            bucket.AnonUserWrite = perm_write


    def enumerate_bucket_objects(self, bucket):
        if bucket.exists == BucketExists.UNKNOWN:
            self.check_bucket_exists(bucket)
        if bucket.exists == BucketExists.NO:
            raise Exception("Bucket doesn't exist")

        for page in self.s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket.name):
            if 'Contents' not in page:  # No items in this bucket
                bucket.objects_enumerated = True
                return
            for item in page['Contents']:
                obj = s3BucketObject(key=item['Key'], last_modified=item['LastModified'], size=item['Size'])
                bucket.addObject(obj)
        bucket.objects_enumerated = True
