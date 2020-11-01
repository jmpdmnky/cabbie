import boto3

from common.dicts import safe_dict_val

from aws.resources import s3

from core import cloud_app


# TODO should other scripts be in subfolders?

# if true, delete all orphan resources
delete = False

# by default, does not delte logs or backups
delete_logs = False
delete_backups = False

active_stage = 'dev'

print("initializing cabbie")
app = cloud_app(active_stage)

session = boto3.session.Session(profile_name=app.aws_profile)

# TODO: move this somewhere?
available_services = [
    s3.bucket,
]


live_resources = app.live_resources()
tracked_resource_names = [safe_dict_val(data, 'name') for res, data in live_resources.items() if safe_dict_val(data, 'name')]


orphaned_resources = []
# get a list of all resources not tracked as a part of app, save to json as we go
for service in available_services:
    orphaned_resources += [ resource for resource in service.list_resources(session=session) if resource.name() not in tracked_resource_names ]


# optionally delete all resources TODO
for resource in orphaned_resources:
    print(resource.live_data())



