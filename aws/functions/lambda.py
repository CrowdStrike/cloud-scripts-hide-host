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
import subprocess
import os
import sys
import base64
from botocore.exceptions import ClientError


# pip install falconpy package to /tmp/ and add to path
subprocess.call('pip install crowdstrike-falconpy -t /tmp/ --no-cache-dir'.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(1, '/tmp/')
try:
    from falconpy import Hosts
except ImportError as no_falconpy:
    raise SystemExit("Unable to import CrowdStrike SDK. Check automation layer contents.") from no_falconpy


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

def get_ssm_params(ssm_client_name, ssm_secret_name, secret_store_region):
    """Retrieve the stored configuration parameters from SSM Parameter Store."""
    ssm = boto3.client('ssm', region_name=secret_store_region)

    print('Fetching APIGatewayClientIDKey')
    apiGatewayClientIDResponse = ssm.get_parameter(Name=ssm_client_name, WithDecryption=True)
    if apiGatewayClientIDResponse['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise ValueError(f"Required property {ssm_client_name} not found")

    cust_id = apiGatewayClientIDResponse['Parameter']['Value']

    print('Fetching APIGatewayClientSecretKey')
    apiGatewayClientSecretResponse = ssm.get_parameter(Name=ssm_secret_name, WithDecryption=True)
    if apiGatewayClientSecretResponse['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise ValueError(f"Required property {ssm_secret_name} not found")

    cust_secret = apiGatewayClientSecretResponse['Parameter']['Value']

    return cust_id, cust_secret
    
ssm_client_name = os.environ['SsmClientName']
ssm_secret_name = os.environ['SsmSecretName']
use_secret_store = os.environ['UseSecretStore']
secret_store_name = os.environ['SecretName']
secret_store_region = os.environ['SecretRegion']
cs_cloud = os.environ['CSCloud']

VERSION = "1.0.0"
name = "cloud-hide-host"
useragent = ("%s/%s" % (name, VERSION))

if use_secret_store == "true":
    print("Retrieving API keys from secrets...")
    secret_str = get_secret(secret_store_name, secret_store_region)
    secrets_dict = json.loads(secret_str)
    FalconClientId = secrets_dict['FalconClientId']
    FalconSecret = secrets_dict['FalconSecret']
elif ssm_client_name:
    print("Retrieving API keys from parameter store...")
    FalconClientId, FalconSecret = get_ssm_params(ssm_client_name, ssm_secret_name, secret_store_region)

def lambda_handler(event, context):
    print(event)
    instance = event['detail']['instance-id']
    print('Hiding Instance ID: ' + instance)

    """Hide the host from the Falcon Console."""
    try:
        print("Hiding terminated instance in Falcon")
        hosts = Hosts(client_id=FalconClientId,
                    client_secret=FalconSecret,
                    base_url=cs_cloud,
                    user_agent=useragent
                    )

        host_aid = hosts.query_devices_by_filter(filter=f"instance_id:'{instance}'")

        if host_aid["status_code"] != 200:
            returned = f"AWS instance: {instance} was not found in your Falcon tenant"

        if host_aid["body"]["resources"]:
            falcon_host_id = host_aid["body"]["resources"][0]
            hide_result = hosts.perform_action(action_name="hide_host", ids=falcon_host_id)
            if hide_result["status_code"] == 202:
                returned = (
                    f"AWS Instance: {instance} | Falcon Resource ID: {falcon_host_id} was "
                    "successfully hidden"
                )
            elif hide_result["status_code"] == 404:
                returned = (
                    f"AWS Instance: {instance} does not have a sensor installed."
                )
            else:
                err_detail = hide_result["body"]["errors"][0]
                code = err_detail["code"]
                msg = err_detail["message"]
                raise ValueError(f"Received non success response {code} while attempting to hide host. Error: {msg}")

        else:
            returned = f"AWS instance: {instance} was not found in your Falcon tenant"

        return returned
    except Exception as err:
        raise ValueError(f"Failure while interacting with CrowdStrike backend. Error {err}") from err
