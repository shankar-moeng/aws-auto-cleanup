import boto3
import datetime
import dateutil.parser
import json
import logging
import os
import sys

from helper import *
from cloudformation_handler import *
from dynamodb_handler import *
from ec2_handler import *
from lambda_handler import *
from rds_handler import *
from s3_handler import *

# enable logging
root = logging.getLogger()

if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

logging.getLogger('boto3').setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.basicConfig(format="[%(levelname)s] %(message)s (%(filename)s, %(funcName)s(), line %(lineno)d)", level=os.environ.get('LOGLEVEL', 'WARNING').upper())


def handler(event, context):
    if first_run():
        return "Default values inserted into DynamoDB tables. Add resources to the whitelist table to prevent unwanted deletion of resources."
    else:
        whitelist = {}
        settings = {}
        
        # build list of whitelisted resources
        for record in boto3.client('dynamodb').scan(TableName=os.environ['WHITELISTTABLE'])['Items']:
            parsed_resource_id = Helper.parse_resource_id(record['resource_id']['S'])
            
            whitelist.setdefault(
                parsed_resource_id.get('service'), {}).setdefault(
                    parsed_resource_id.get('resource_type'), []).append(
                        parsed_resource_id.get('resource'))
        
        # build dictionary of settings
        for record in boto3.client('dynamodb').scan(TableName=os.environ['SETTINGSTABLE'])['Items']:
            setting = record['key']['S']
            value = record['value']['S']
            settings[setting] = value
        
        helper_class = Helper(settings)

        # CloudFormation
        cloudformation_class = CloudFormation(helper_class, whitelist, settings)
        cloudformation_class.run()

        # DynamoDB
        dynamodb_class = DynamoDB(helper_class, whitelist, settings)
        dynamodb_class.run()
        
        # EC2
        ec2_class = EC2(helper_class, whitelist, settings)
        ec2_class.run()
        
        # Lambda
        lambda_class = Lambda(helper_class, whitelist, settings)
        lambda_class.run()
        
        # RDS
        rds_class = RDS(helper_class, whitelist, settings)
        rds_class.run()

        # S3
        s3_class = S3(helper_class, whitelist, settings)
        s3_class.run()

        return "Auto Cleanup completed"


def first_run():
    """
    The first time the function runs it'll insert all the default
    settings and whitelist data into their respective DynamoDB tables.
    """
    
    SETTINGSTABLE = boto3.client('dynamodb').describe_table(
        TableName=os.environ['SETTINGSTABLE'])
    
    settings_table_count = SETTINGSTABLE.get('Table').get('ItemCount')
    if settings_table_count == 0:
        try:
            data = open('data/auto-cleanup-settings.json')
            boto3.client('dynamodb').batch_write_item(
                RequestItems=json.loads(data.read().replace('SETTINGSTABLE', os.environ['SETTINGSTABLE'])))
            data.close()

            logging.info("Settings table is empty and has been populated with default values.")
        except ValueError as e:
            logging.critical(str(e))
        except:
            logging.critical(str(sys.exc_info()))
    
    WHITELISTTABLE = boto3.client('dynamodb').describe_table(
        TableName=os.environ['WHITELISTTABLE'])
    
    whitelist_table_count = WHITELISTTABLE.get('Table').get('ItemCount')
    if whitelist_table_count == 0:
        try:
            data = open('data/auto-cleanup-whitelist.json')
            boto3.client('dynamodb').batch_write_item(
                RequestItems=json.loads(data.read().replace('WHITELISTTABLE', os.environ['WHITELISTTABLE'])))
            data.close()

            logging.info("Whitelist table is empty and has been populated with default values.")
        except ValueError as e:
            logging.critical(str(e))
        except:
            logging.critical(str(sys.exc_info()))
    
    if settings_table_count == 0 or whitelist_table_count == 0:
        return True
    else:
        return False