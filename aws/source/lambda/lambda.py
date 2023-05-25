"""
CrowdStrike Hide Host Lambda Function

______                         __ _______ __         __ __
|      |.----.-----.--.--.--.--|  |     __|  |_.----.|__|  |--.-----.
|   ---||   _|  _  |  |  |  |  _  |__     |   _|   _||  |    <|  -__|
|______||__| |_____|________|_____|_______|____|__|  |__|__|__|_____|

Falcon Hide Host Lambda Function v1.0

Creation date: 05.01.23 - ryanjpayne@CrowdStrike
"""

import json
import boto3
import os
import base64
import logging
import traceback
import sys
from botocore.exceptions import ClientError
import falconpy

class CrowdStrikeApiError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"Received non-success response {code} while calling API. Error: {message}")

def get_secret(secret_name, secret_region):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=secret_region
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            raise e
    else:
        # Decrypts secret using the associated KMS key.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = base64.b64decode(get_secret_value_response['SecretBinary'])
        return secret

def get_ssm_params(SSM_CLIENT_NAME, SSM_SECRET_NAME, SECRET_REGION):
    """Retrieve the stored configuration parameters from SSM Parameter Store."""
    ssm = boto3.client('ssm', region_name=SECRET_REGION)

    logger.info(f'Fetching Systems Manager Parameter: ' + SSM_CLIENT_NAME)
    apiGatewayClientIDResponse = ssm.get_parameter(Name=SSM_CLIENT_NAME, WithDecryption=True)
    if apiGatewayClientIDResponse['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise ValueError(f"Required property {SSM_CLIENT_NAME} not found")

    cust_id = apiGatewayClientIDResponse['Parameter']['Value']

    logger.info(f'Fetching Systems Manager Parameter: ' + SSM_SECRET_NAME)
    apiGatewayClientSecretResponse = ssm.get_parameter(Name=SSM_SECRET_NAME, WithDecryption=True)
    if apiGatewayClientSecretResponse['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise ValueError(f"Required property {SSM_SECRET_NAME} not found")

    cust_secret = apiGatewayClientSecretResponse['Parameter']['Value']

    return cust_id, cust_secret

def get_env(key):
    """Get the value of an environment variable.
    Args:
        key (str): The name of the environment variable.
    Returns:
        str: The value of the environment variable.
    Raises:
        KeyError: If the environment variable is not set.
    """
    value = os.environ.get(key)
    if value is None:
        raise KeyError(f"Required environment variable: {key} is not set.")
    return value

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VERSION = "1.0.0"
name = "crowdstrike-cloud-hide-host"
useragent = ("%s/%s" % (name, VERSION))

USE_SECRET_STORE = get_env("USE_SECRET_STORE")
SECRET_REGION = get_env("SECRET_REGION")
CS_CLOUD = get_env("CS_CLOUD")

if USE_SECRET_STORE == "true":
    logger.info(f'Retrieving API keys from secrets...')
    SECRET_STORE_NAME = get_env("SECRET_STORE_NAME")
    secret_str = get_secret(SECRET_STORE_NAME, SECRET_REGION)
    secrets_dict = json.loads(secret_str)
    FalconClientId = secrets_dict['FalconClientId']
    FalconSecret = secrets_dict['FalconSecret']
elif USE_SECRET_STORE == "false":
    logger.info(f'Retrieving API keys from parameter store...')
    SSM_CLIENT_NAME = get_env("SSM_CLIENT_NAME")
    SSM_SECRET_NAME = get_env("SSM_SECRET_NAME")
    FalconClientId, FalconSecret = get_ssm_params(SSM_CLIENT_NAME, SSM_SECRET_NAME, SECRET_REGION)

def lambda_handler(event, context):
    
    hosts = falconpy.Hosts(client_id=FalconClientId,
                client_secret=FalconSecret,
                base_url=CS_CLOUD,
                user_agent=useragent
                )
    
    try:
        logger.info(f'event: {event}')
        instance = event['detail']['instance-id']
        logger.info(f'Hiding Instance ID: {instance}')
        
        host_aid = hosts.query_devices_by_filter(filter=f"instance_id:'{instance}'")
        query_status = host_aid["status_code"]
        if query_status == 401:
            returned = f"{query_status} Access denied, authorization failed. Please ensure the Falcon API Key is valid."
        elif query_status == 403:
            returned = f"{query_status} Access denied, authorization failed. Please ensure the Falcon API Key has scope: Hosts Read & Write"
        elif query_status == 200:
            if host_aid["body"]["resources"]:    
                falcon_host_id = host_aid["body"]["resources"][0]
                hide_result = hosts.perform_action(action_name="hide_host", ids=falcon_host_id)
                hide_status = hide_result["status_code"]
                if hide_status == 202:
                    returned = (
                        f"AWS Instance: {instance} | Falcon Resource ID: {falcon_host_id} was "
                        "successfully hidden"
                    )
                elif hide_status == 404:
                    returned = (
                        f"AWS Instance: {instance} does not have a sensor installed."
                    )
                else:
                    err_detail = hide_result["body"]["errors"][0]
                    code = err_detail["code"]
                    msg = err_detail["message"]
                    raise CrowdStrikeApiError(code,msg)
            else:
                returned = f"AWS instance: {instance} was not found in your Falcon tenant"
            
        logger.info(returned)
    except Exception as exp:
            exception_type, exception_value, exception_traceback = sys.exc_info()
            traceback_string = traceback.format_exception(exception_type, exception_value, exception_traceback)
            err_msg = json.dumps({
                "errorType": exception_type.__name__,
                "errorMessage": str(exception_value),
                "stackTrace": traceback_string
            })
            logger.error(err_msg)
