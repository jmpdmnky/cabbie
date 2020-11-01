# General AWS/boto3 helpers

import boto3

def session(profile_name, region='us_east_1'):
    return boto3.session.Session(profile_name=profile_name, region_name=region)