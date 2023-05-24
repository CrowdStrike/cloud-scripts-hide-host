![image](/images/cs-logo.png)
# CrowdStrike Cloud Scripts - Hide Host for AWS

## Introduction

Event driven solution to automatically remove AWS Instances from CrowdStrike upon termination.

## Architectural Overview

The solution infrastructure is deployed via AWS SAM templates. The solution will automatically launch AWS CloudFormation StackSets in each of the desired regions.

The following architectural diagram illustrates the resources deployed in an AWS account.

![image](/images/aws-diagram.png)

### Workflow
1. An AWS EC2 Instance is terminated.
2. The EC2 Instance State-change notification triggers an EventBridge Rule in the same Region.
3. The EventBridge rule targets a custom Event Bus.
4. The custom Event Bus applies to another EventBridge Rule which targets Lambda.
5. The Lambda function receives and processes the event.
6. The Lambda function retrieves Falcon API Keys from either Secrets Manager or Parameter Store.
7. The Lambda function calls the Falcon API to hide the terminated instance-id from the Falcon console.

## Prerequisites

### CrowdStrike Falcon API Keys
Create Falcon API Keys with the following scope: Hosts Read & Write

### AWS SAM CLI
Your client must have AWS SAM CLI Installed.  For details see: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

### Secret Storage
You may store your Falcon API Keys in AWS Secrets Manager or Systems Manager Parameter Store.  Consider the requirements for each option:
- Secrets Manager: This solution will create the secret for you. You will provide FalconClientId and FalconSecret in the appropriate samconfig.toml parameters.
- Parameter Store: You must create the Systems Manager parameters BEFORE using this solution. Please create SecureString paramters for each of Falcon CLient ID and Falcon Secret Key.  You will provide the Paramter Store Paramter Names in the appropriate samconfig.toml parameters.

## How to set Parameters

Parameters must be set in samconfig.toml

**CrowdStrike Falcon API Keys**
| Parameter|Description|
|---|---|
|SecretStorageMethod| Allowed values: SecretsManager or ParameterStore|
|CrowdStrikeCloud| The CrowdStrike Cloud for your CID: us-1, us-2 or eu-1|
|FalconClientId| Your Falcon API Client ID if SecretStorageMethod = SecretsManager|
|FalconSecret| only provide if Create Secret for API Keys = true|
|SSMClientID|Name of SSM Parameter in which Falcon API Client ID is stored. |
|SSMClientID|Name of SSM Parameter in which Falcon API Client Secret is stored. |

**Activate Regions**
| Parameter|Description|
|---|---|
|ActivateRegions| Comma delimited list of AWS regions to enroll with CrowdStrike Hide Host|

**Define Resource Names** 
These parameters have predefined values, but may be modified if your Organization requires.
| Parameter|Default Value|
|---|---|
|SecretName|cs-hide-host-secret|
|LambdaFunctionName|cs-hide-host-function|
|EventBusName|cs-hide-host-bus|
|EventBridgeRuleName|cs-hide-host-rule|
|EventBridgeRoleName|cs-hide-host-role|
|StackSetName|cs-hide-host-stackset|
|StackSetAdminRole|cs-hide-host-stackset-admin-role|
|StackSetExecRole|cs-hide-host-stackset-exec-role|

## How to Deploy
==Before you deploy please ensure the samconfig.toml parameters are set.==  A Makefile is included to simplify the deployment process.  
### To deploy the solution:
- Download this repository
- In your terminal change to the newly downloaded directory
- In your terminal run `make`

### To delete the solution:
- In your terminal change to the downloaded directory
- In your terminal run `make clean`

## Contribution Notes

> **Note** <br>
> For ease of deployment via CloudFormation and not introducing any custom resources or manual steps to seed the package in an S3 bucket, the code is embedded in the CloudFormation template and is zip'ed automatically by CloudFormation. This is mentioned to remind any contributors to update both references of the Lambda code where applicable.